"""HTTP endpoints for the RFM system, split by role.

Admin endpoints (analysis run/summary/segments and campaign CRUD) require the
ADMIN role; customer endpoints read only the authenticated customer's own
segment and offers (their id comes from the verified session, never the body).
Segment customer lists are served from the published snapshot with server-side
search, sorting and pagination, so the browser never receives all ~100k rows.
"""

import logging
import time

from django.db import DatabaseError, connection
from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.serializers import ValidationError as DRFValidationError

from accounts.permissions import IsAdmin, IsAuthenticatedUser, IsCustomer
from accounts.models import Customer
from cart.models import CartItem
from cart.services import CustomerResolver
from catalog.pricing import get_product_selling_price_map

from . import (cache_manager, campaign_engine, campaign_publishing,
               cluster_targeting, clustering, campaign_audience,
               coupon_validation, dashboard_cache, engine, personalization,
               queries, segment_store, utils)
from .models import Campaign, CampaignStatus, CustomerSegment
from .serializers import CampaignSerializer

logger = logging.getLogger(__name__)

# Whitelist of sortable record fields for the segment detail table.
SORTABLE_FIELDS = {
    'customer_id', 'recency_days', 'frequency', 'monetary',
    'r_percentile', 'f_percentile', 'm_percentile',
    'r_score', 'f_score', 'm_score',
}

# Sortable columns of the persisted RFM *results* table (physical model fields,
# each backed by an index or the primary key so filter + order stays a scan).
RESULTS_SORT_FIELDS = {
    'customer_id': 'customer_id',
    'recency': 'recency',
    'frequency': 'frequency',
    'monetary': 'monetary',
    'r_score': 'r_score',
    'f_score': 'f_score',
    'm_score': 'm_score',
    'rfm_score': 'rfm_score',
    'segment': 'segment',
}

# Frontend drill-down sort keys mapped onto persisted result columns (the table
# stores the 1-5 band scores, not raw percentiles; the detail table only ever
# sorts by these stored fields).
SEGMENT_SORT_FIELDS = {
    'customer_id': 'customer_id', 'recency': 'recency', 'recency_days': 'recency',
    'frequency': 'frequency', 'monetary': 'monetary',
    'r_score': 'r_score', 'f_score': 'f_score', 'm_score': 'm_score',
}


def _safe_db_error(request, exc):
    logger.error('rfm dashboard database error (%s)', type(exc).__name__)
    return Response(
        {'detail': 'Service temporarily unavailable. Please try again later.'},
        status=status.HTTP_503_SERVICE_UNAVAILABLE,
    )


def _parse_pagination(request):
    try:
        page = max(1, int(request.query_params.get('page', 1) or 1))
        page_size = int(request.query_params.get('page_size', 25) or 25)
    except (TypeError, ValueError):
        page, page_size = 1, 25
    page_size = min(max(page_size, 1), 200)
    return page, page_size


# Cap on how many name matches a search may expand into. The id branch of the
# same search is unbounded, so an unusual broad query can never turn into a
# multi-thousand-value IN list.
NAME_SEARCH_LIMIT = 2000

# Whether the unmanaged `customers` table exists on the connected database,
# remembered after the first check. Probing it by table listing (instead of
# catching a failed query) matters: a raised database error inside a test's or
# an ATOMIC_REQUESTS transaction would mark the transaction for rollback and
# break every later query in it.
_names_table_ok = None


def _customer_names_available():
    global _names_table_ok
    if _names_table_ok is None:
        try:
            tables = connection.introspection.table_names()
        except Exception:  # noqa: BLE001 - a probe failure is not remembered
            return False
        _names_table_ok = Customer._meta.db_table in tables
    return _names_table_ok


def _segment_search_q(search):
    """Q matching a customer id, and (best effort) a real name via the mapping.

    `public.customers` is an unmanaged dataset table with no counterpart on the
    SQLite test database, so the name branch is only attempted when that table
    exists, and its matches are resolved here rather than as a subquery so a
    missing table can never surface later while the paged rows execute.
    """
    q = Q(customer_id__icontains=search)
    if not _customer_names_available():
        return q
    try:
        matched = list(Customer.objects.filter(
            customer_name__icontains=search).values_list('customer_id', flat=True)[:NAME_SEARCH_LIMIT])
    except Exception:  # noqa: BLE001 - names are a display enhancement only
        matched = []
    if matched:
        q |= Q(customer_id__in=matched)
    return q


def _names_for(customer_ids):
    """{customer_id: customer_name} for one page (single bulk query)."""
    if not customer_ids or not _customer_names_available():
        return {}
    try:
        return {c.customer_id: c.customer_name
                for c in Customer.objects.filter(customer_id__in=customer_ids)}
    except Exception:  # noqa: BLE001 - names are display-only
        return {}


def _segment_row(row, names):
    """Project a persisted CustomerSegment into the drill-down table shape."""
    return {
        'customer_id': row.customer_id,
        'customer_name': names.get(row.customer_id),
        'segment': row.segment,
        'tags': row.tags or [],
        'r_score': row.r_score,
        'f_score': row.f_score,
        'm_score': row.m_score,
    }


class AdminRFMView(APIView):
    """Shared base for admin-only RFM endpoints."""
    permission_classes = [IsAuthenticatedUser, IsAdmin]


class RfmRunView(AdminRFMView):
    """POST /api/analytics/rfm/run -> start a background analysis.

    A repeated request while a run is in flight is answered with 409 and the
    current status instead of launching a second full-population computation.
    """

    def post(self, request):
        accepted, run_status = engine.start_background_run()
        if not accepted:
            return Response({
                'message': 'An RFM analysis is already running.',
                'status': run_status,
            }, status=status.HTTP_409_CONFLICT)
        return Response({
            'message': 'RFM analysis started.',
            'status': run_status,
        }, status=status.HTTP_202_ACCEPTED)

    def get(self, request):
        # Lets the dashboard poll run progress without a POST.
        return Response({'status': cache_manager.get_run_status()},
                        status=status.HTTP_200_OK)


def _kmeans_compact(kmeans):
    """Only the fields the dashboard paints immediately, never the profiles.

    The bars need label, count, share and whether the label is supported. The
    per-cluster unscaled profiles, the confidence, the run bookkeeping and the
    ambiguity report are the *detailed* analytics, served by
    `RfmAnalyticsDetailView` after the first paint.
    """
    keep = ('cluster_id', 'category', 'customer_count', 'percent', 'supported',
            'cautions')
    return {
        'available': kmeans['available'],
        'clustered': kmeans['clustered'],
        'total': kmeans['total'],
        'clusters': [{key: cluster.get(key) for key in keep} for cluster in kmeans['clusters']],
    }


def _dashboard_bundle(version):
    """The dashboard aggregate, from the fastest place that has it.

    In-process cache -> durable per-version snapshot -> one grouped SQL pass
    (which then refreshes both caches). `timing` records which one answered and
    how long the query cost, so the measured numbers are in the API response
    rather than assumed: a warm read performs no database query at all.
    """
    started = time.perf_counter()
    run_id = dashboard_cache.current_clustering_run_id()
    bundle, source = dashboard_cache.load(version, run_id)
    lookup_ms = round((time.perf_counter() - started) * 1000, 2)
    if bundle is not None:
        return bundle, {'bundle_source': source, 'lookup_ms': lookup_ms, 'query_ms': 0}
    try:
        bundle, timing = dashboard_cache.build(version=version, run_id=run_id)
    except DatabaseError:
        raise
    timing['bundle_source'] = 'query'
    timing['lookup_ms'] = lookup_ms
    return bundle, timing


class RfmSummaryView(AdminRFMView):
    """GET /api/analytics/rfm/summary -> the KPIs and the four cluster bars.

    This is the fast path: everything comes from the *persisted* RFM result
    table's already-assembled aggregate (in-process cache, then the durable
    per-version snapshot, and only then one grouped SQL statement which is
    cached for everyone after it). K-Means is never fitted here - the page reads
    the stored assignment of the latest completed clustering run - and no
    customer rows are loaded, aggregated or shipped by this endpoint.

    The freshness check runs on a background thread (`engine.nudge_latest`), so
    opening the page never waits on a state read: it always shows the latest
    successfully completed analysis immediately and reports `refreshing` when a
    run is genuinely in flight. The heavier analytics (cluster profiles, run
    bookkeeping, ambiguity report, segment distribution) are a separate lazy
    call, and the customer lists are server-side paginated elsewhere.
    """

    def get(self, request):
        started = time.perf_counter()
        freshness = engine.nudge_latest()
        # A clustering run persisted before the current four-category vocabulary
        # would otherwise still show its old label strings (the chart aggregates
        # the persisted `kmeans_category`). Re-derive them from the run's stored
        # profiles - no K-Means rerun, no buyer reassignment - before the cached
        # bundle is assembled, so the dashboard always renders current labels.
        clustering.reconcile_stored_labels()
        # The analysis version/dates come from a memoized lookup: warm it is a
        # cache read with no database round trip, which is the point of the
        # whole summary path against a remote database.
        state = segment_store.get_cached_state()
        if state is None:
            return Response({
                'available': False,
                'refreshing': True,
                'run_status': freshness['run_status'],
                'kmeans': _kmeans_compact(clustering.summarize_clusters([], state=None)),
                'message': 'Preparing the RFM analysis. This runs automatically in the background.',
            }, status=status.HTTP_200_OK)

        version = state['version']
        try:
            bundle, timing = _dashboard_bundle(version)
        except DatabaseError as exc:
            return _safe_db_error(request, exc)

        totals = bundle['totals']
        buyer_count = totals['buyer_count'] or 0
        total_customers = bundle['total_customers']
        never_purchased = max(total_customers - buyer_count, 0)
        kmeans = clustering.summarize_clusters(bundle['kmeans_clusters'],
                                               total=buyer_count)
        timing['assemble_ms'] = round((time.perf_counter() - started) * 1000, 2)

        return Response({
            'available': True,
            'version': version,
            'analysis_date': state['analysis_date'],
            'computed_at': state['completed_at'],
            'refreshing': freshness['refreshing'],
            'nudging': freshness.get('nudging', False),
            'run_status': cache_manager.get_run_status(),
            'source': 'cached_aggregate' if timing['bundle_source'] != 'query' else 'persisted_results',
            'timing': timing,
            'totals': {
                'total_customers': total_customers,
                'total_eligible_buyers': buyer_count,
                'never_purchased_customers': never_purchased,
                'total_eligible_orders': totals['total_orders'],
                'total_eligible_revenue': (round(float(totals['total_revenue'] or 0), 2)),
            },
            'buyer_count': buyer_count,
            'big_spender_count': totals['big_spender_count'] or 0,
            # K-Means++ (k=4) is the RFM page's segmentation: the four business
            # categories of the stored clustering run, with their counts and
            # shares. The old rule-based distribution is not served here any more
            # - the persisted `segment` column survives only as the internal label
            # CLV reads and as the audience definition of the campaigns that were
            # published against it before the Campaign page moved to clusters.
            'kmeans': _kmeans_compact(kmeans),
        }, status=status.HTTP_200_OK)


class RfmAnalyticsDetailView(AdminRFMView):
    """GET /api/analytics/rfm/analytics -> the heavy analytics, loaded lazily.

    The first paint only needs the KPIs and the four bars; the profile detail
    behind each label (unscaled Recency / Frequency / Monetary, medians, tenure,
    one-time-buyer share, mapping confidence), the honesty report, the run
    bookkeeping and the legacy segment distribution are read by the page after
    it has rendered, from the same cached bundle. So this costs no additional
    database query on a warm cache and never delays what the admin sees first.
    """

    def get(self, request):
        clustering.reconcile_stored_labels()
        state = segment_store.get_cached_state()
        if state is None:
            return Response({'available': False, 'refreshing': True,
                             'message': 'Preparing the RFM analysis.'},
                            status=status.HTTP_200_OK)
        version = state['version']
        try:
            bundle, timing = _dashboard_bundle(version)
        except DatabaseError as exc:
            return _safe_db_error(request, exc)
        buyer_count = bundle['totals']['buyer_count'] or 0
        kmeans = clustering.summarize_clusters(bundle['kmeans_clusters'],
                                              total=buyer_count)
        return Response({
            'available': True,
            'version': version,
            'buyer_count': buyer_count,
            'big_spender_count': bundle['totals']['big_spender_count'] or 0,
            'timing': timing,
            'distribution': bundle['distribution'],
            'kmeans': kmeans,
        }, status=status.HTTP_200_OK)


class RfmClustersView(AdminRFMView):
    """GET/POST /api/analytics/rfm/clusters -> K-Means++ segmentation.

    GET reads the current stored clustering (four business categories with
    counts, percentages and unscaled RFM profiles) straight from
    `rfm_customer_segments` plus the single stored run-state row, so it is cheap,
    never recomputes the model and survives a restart. POST runs the actual
    K-Means++ pipeline over the RFM values already persisted - it never
    recomputes RFM, never overwrites the original metrics or the rule-based
    segment, and updates each buyer's existing row instead of inserting
    duplicates. A second POST while a run is in flight is refused (409) so one
    ~100k-row population is never clustered twice at the same time.
    """

    def get(self, request):
        # Keep the standalone clusters read consistent with the dashboard: heal a
        # legacy persisted run's labels from its stored profiles first (no rerun).
        clustering.reconcile_stored_labels()
        return Response(clustering.clustering_summary(),
                        status=status.HTTP_200_OK)

    def post(self, request):
        if not cache_manager.acquire_kmeans_run_lock():
            return Response(
                {'detail': 'A clustering run is already in progress.'},
                status=status.HTTP_409_CONFLICT)
        try:
            result = clustering.run_clustering(save=True)
        finally:
            cache_manager.release_kmeans_run_lock()
        if not result.get('available'):
            return Response(result, status=status.HTTP_409_CONFLICT)
        return Response(result, status=status.HTTP_200_OK)


class RfmClusterCustomersView(AdminRFMView):
    """GET /api/analytics/rfm/clusters/customers -> one cluster's actual buyers.

    Paging the cluster drill-down straight off the persisted labels
    (`rfm_customer_segments.kmeans_cluster_id` / `kmeans_category`), which are
    the latest completed K-Means assignment: the same rows the distribution
    counts are aggregated from, so a bar's count and its list can never disagree.
    Server-side search, sorting and pagination only - with ~100k buyers the
    browser never receives more than one page, and no order-table scan happens.

    `category` is required (the business label of the clicked bar) and
    `cluster_id` is honored as well when supplied, so the list is always exactly
    the members of that one numeric cluster.
    """

    def get(self, request):
        category = (request.query_params.get('category') or '').strip()
        if category not in utils.KMEANS_CATEGORIES:
            return Response({'detail': 'Unknown cluster category.'},
                            status=status.HTTP_404_NOT_FOUND)

        cluster_id = (request.query_params.get('cluster_id') or '').strip()
        if cluster_id:
            try:
                cluster_id = int(cluster_id)
            except (TypeError, ValueError):
                return Response({'detail': 'Unknown cluster id.'},
                                status=status.HTTP_404_NOT_FOUND)
        else:
            cluster_id = None

        page, page_size = _parse_pagination(request)
        search = (request.query_params.get('search') or '').strip()
        sort = (request.query_params.get('sort') or 'customer_id').lower()
        direction = (request.query_params.get('dir') or 'asc').lower()
        order_col = SEGMENT_SORT_FIELDS.get(sort, 'customer_id')

        queryset = CustomerSegment.objects.exclude(
            kmeans_cluster_id__isnull=True).filter(kmeans_category=category)
        if cluster_id is not None:
            queryset = queryset.filter(kmeans_cluster_id=cluster_id)
        if search:
            queryset = queryset.filter(_segment_search_q(search))
        # Stable tie-break so paging never repeats or skips a row.
        if order_col != 'customer_id':
            queryset = queryset.order_by(order_col, 'customer_id') if direction != 'desc' \
                else queryset.order_by(f'-{order_col}', 'customer_id')
        else:
            queryset = queryset.order_by(f'-{order_col}' if direction == 'desc' else order_col)

        total = queryset.count()
        start = (page - 1) * page_size
        rows = list(queryset[start:start + page_size])
        names = _names_for([r.customer_id for r in rows])
        return Response({
            'available': total > 0 or page == 1,
            'category': category,
            'cluster_id': cluster_id if cluster_id is not None
            else (rows[0].kmeans_cluster_id if rows else None),
            'count': total,
            'page': page,
            'page_size': page_size,
            'total_pages': (total + page_size - 1) // page_size if page_size else 1,
            'results': [self._row(r, names) for r in rows],
        }, status=status.HTTP_200_OK)

    def _row(self, row, names):
        """Cluster members show their identity, the cluster they belong to and
        their ORIGINAL (unscaled) Recency / Frequency / Monetary.

        The three metrics come straight from the persisted RFM row for this
        exact customer and run, so the popup never fabricates or substitutes a
        value; they are the same unscaled numbers the clustering was computed
        from (the standardized values are never stored or shown).
        """
        return {
            'customer_id': row.customer_id,
            'customer_name': names.get(row.customer_id),
            'cluster_id': row.kmeans_cluster_id,
            'category': row.kmeans_category,
            'recency': row.recency,
            'frequency': row.frequency,
            'monetary': float(row.monetary) if row.monetary is not None else None,
        }


class RfmSegmentsView(AdminRFMView):
    """GET /api/analytics/rfm/segments -> segment counts only.

    Same persisted-table aggregation as the summary (shares the cached payload),
    so it never triggers a recalculation and stays correct after a restart.
    """

    def get(self, request):
        state = segment_store.get_cached_state()
        if state is None:
            return Response({'available': False, 'segments': []},
                            status=status.HTTP_200_OK)

        # Shares the summary's cached bundle (same version + clustering epoch),
        # so opening the segments endpoint after the dashboard is a pure cache
        # read with no database round trip.
        version = state['version']
        try:
            bundle, _timing = _dashboard_bundle(version)
        except DatabaseError as exc:
            return _safe_db_error(request, exc)

        counts = {row['segment']: row['count'] for row in bundle['distribution']}
        return Response({
            'available': True,
            'version': version,
            'segments': [{'segment': label, 'count': counts.get(label, 0)}
                         for label in utils.PRIMARY_SEGMENTS],
            'never_purchased': max(bundle['total_customers']
                                   - (bundle['totals']['buyer_count'] or 0), 0),
            'big_spender_count': bundle['totals']['big_spender_count'] or 0,
        }, status=status.HTTP_200_OK)


class RfmSegmentDetailView(AdminRFMView):
    """GET /api/analytics/rfm/segments/{segment} -> one paginated segment.

    Pages are served entirely from the in-memory snapshot index (no RFM
    recalculation and no order-table scan per request): the segment's bucket is
    already ordered by customer_id, only the requested page and only the table
    columns leave the server. The Never Purchased population (no RFM metrics)
    is a small anti-join result fetched once per analysis and cached.
    """

    def get(self, request, segment):
        # The frontend sends the exact label, URL-encoded (spaces -> %20).
        segment = (segment or '').strip()

        page, page_size = _parse_pagination(request)
        search = (request.query_params.get('search') or '').strip()
        sort = (request.query_params.get('sort') or 'customer_id').lower()
        direction = (request.query_params.get('dir') or 'asc').lower()
        order_col = SEGMENT_SORT_FIELDS.get(sort, 'customer_id')

        state = segment_store.get_state()
        version = state.version if state else None

        if segment == utils.SEGMENT_NEVER_PURCHASED:
            return self._never_purchased_page(request, page, page_size, search, version)

        # Big Spenders is a secondary tag, not a primary segment: its list is
        # the buyers who carry the tag, regardless of their primary segment.
        if segment == utils.TAG_BIG_SPENDER:
            queryset = CustomerSegment.objects.filter(
                tags__contains=[utils.TAG_BIG_SPENDER])
        elif segment in utils.ALL_SEGMENTS:
            queryset = CustomerSegment.objects.filter(segment=segment)
        else:
            return Response({'detail': 'Unknown segment.'},
                            status=status.HTTP_404_NOT_FOUND)

        if search:
            queryset = queryset.filter(_segment_search_q(search))
        ordering = f'-{order_col}' if direction == 'desc' else order_col
        if order_col != 'customer_id':
            queryset = queryset.order_by(ordering, 'customer_id')
        else:
            queryset = queryset.order_by(ordering)

        total = queryset.count()
        start = (page - 1) * page_size
        rows = list(queryset[start:start + page_size])
        names = _names_for([r.customer_id for r in rows])
        return Response({
            'available': state is not None,
            'segment': segment,
            'version': version,
            'count': total,
            'page': page,
            'page_size': page_size,
            'total_pages': (total + page_size - 1) // page_size if page_size else 1,
            'results': [_segment_row(r, names) for r in rows],
        }, status=status.HTTP_200_OK)

    def _never_purchased_page(self, request, page, page_size, search, version=None):
        version = version if version is not None else cache_manager.get_latest_version()
        rows = cache_manager.get_never_purchased(version)
        if rows is None:
            try:
                total = queries.count_never_purchased()
                raw = queries.fetch_never_purchased_page(max(total, 1), 0)
            except DatabaseError as exc:
                return _safe_db_error(request, exc)
            rows = [
                {
                    'customer_id': r['customer_id'],
                    'customer_name': r.get('customer_name'),
                    'segment': utils.SEGMENT_NEVER_PURCHASED,
                    'tags': [],
                }
                for r in raw
            ]
            cache_manager.set_never_purchased(version, rows)

        if search:
            rows = [
                r for r in rows
                if search in str(r['customer_id']).lower()
                or search in str(r.get('customer_name') or '').lower()
            ]

        total = len(rows)
        start = (page - 1) * page_size
        return Response({
            'available': True,
            'segment': utils.SEGMENT_NEVER_PURCHASED,
            'version': version,
            'count': total,
            'page': page,
            'page_size': page_size,
            'total_pages': (total + page_size - 1) // page_size if page_size else 1,
            'results': rows[start:start + page_size],
        }, status=status.HTTP_200_OK)


class RfmResultsView(AdminRFMView):
    """GET /api/analytics/rfm/results -> paginated latest persisted RFM results.

    Read straight from the durable result table (`rfm_customer_segments`), not
    the cache snapshot: it is server-side paginated, filtered by segment and
    searched by customer id, and sorted on indexed columns - so the browser
    never receives all ~100k rows and no order-table scan happens per request.
    Each row is the customer's latest successfully calculated result.
    """

    def get(self, request):
        page, page_size = _parse_pagination(request)
        segment = (request.query_params.get('segment') or '').strip()
        search = (request.query_params.get('search') or '').strip()
        sort = (request.query_params.get('sort') or 'customer_id').lower()
        direction = (request.query_params.get('dir') or 'asc').lower()
        order_field = RESULTS_SORT_FIELDS.get(sort, 'customer_id')
        ordering = f'-{order_field}' if direction == 'desc' else order_field

        queryset = CustomerSegment.objects.all()
        if segment and segment != 'ALL':
            queryset = queryset.filter(segment=segment)
        if search:
            queryset = queryset.filter(customer_id__icontains=search)
        # Stable tie-break so paging never repeats or skips a row.
        if order_field != 'customer_id':
            queryset = queryset.order_by(ordering, 'customer_id')
        else:
            queryset = queryset.order_by(ordering)

        total = queryset.count()
        start = (page - 1) * page_size
        rows = [_project_result(r) for r in queryset[start:start + page_size]]

        state = segment_store.get_state()
        return Response({
            'available': state is not None,
            'version': state.version if state else None,
            'analysis_date': (state.analysis_date.isoformat()
                              if state and state.analysis_date else None),
            'calculated_at': (state.completed_at.isoformat()
                              if state else None),
            'buyer_count': state.buyer_count if state else 0,
            'count': total,
            'page': page,
            'page_size': page_size,
            'total_pages': (total + page_size - 1) // page_size if page_size else 1,
            'results': rows,
        }, status=status.HTTP_200_OK)


def _project_result(row):
    """Serialize one persisted RFM result row for the results endpoint."""
    return {
        'customer_id': row.customer_id,
        'recency': row.recency,
        'frequency': row.frequency,
        'monetary': (float(row.monetary) if row.monetary is not None else None),
        'r_score': row.r_score,
        'f_score': row.f_score,
        'm_score': row.m_score,
        'rfm_score': row.rfm_score,
        'segment': row.segment,
        'tags': row.tags or [],
        'first_purchase_date': (row.first_purchase_date.isoformat()
                                if row.first_purchase_date else None),
        'last_purchase_date': (row.last_purchase_date.isoformat()
                               if row.last_purchase_date else None),
        'calculation_version': row.version,
        'calculated_at': (row.computed_at.isoformat() if row.computed_at else None),
        'updated_at': (row.updated_at.isoformat() if row.updated_at else None),
    }


class RfmRecalculateView(AdminRFMView):
    """POST /api/analytics/rfm/recalculate -> admin-only FULL refresh.

    Runs the complete pipeline over the live order history and UPSERTs every
    eligible customer's result, updating the calculation state only after the
    whole run commits (a second in-flight request is refused with 409). Use it
    for a manual refresh, a methodology/version change, or a reconciliation.
    """

    def post(self, request):
        accepted, run_status = engine.start_background_run(full=True)
        if not accepted:
            return Response({
                'message': 'An RFM analysis is already running.',
                'status': run_status,
            }, status=status.HTTP_409_CONFLICT)
        return Response({
            'message': 'Full RFM recalculation started.',
            'mode': 'full',
            'status': run_status,
        }, status=status.HTTP_202_ACCEPTED)

    def get(self, request):
        return Response({'status': cache_manager.get_run_status()},
                        status=status.HTTP_200_OK)


class RfmIncrementalRefreshView(AdminRFMView):
    """POST /api/analytics/rfm/incremental-refresh -> synchronize changed data.

    Recalculates and re-persists only affected customers: it first compares a cheap
    fingerprint of the eligible order data against the last completed run. When
    nothing changed it is an immediate no-op (200 'up_to_date'); when it did, a
    refresh is scheduled whose conditional UPSERT inserts new buyers and updates
    only buyers whose metrics/segment/monetary actually changed (unchanged rows
    are left untouched). A full scan is still required to keep the population-
    wide percentile scores correct - a documented consequence of quantile
    scoring, so this endpoint is the admin/internal synchronization hook.
    """

    def post(self, request):
        if not engine.source_changed_since_last_run():
            return Response({
                'message': 'No source changes since the last completed analysis.',
                'status': 'up_to_date',
                'version': segment_store.latest_version(),
            }, status=status.HTTP_200_OK)

        accepted, run_status = engine.start_background_run(full=False)
        if not accepted:
            return Response({
                'message': 'An RFM analysis is already running.',
                'status': run_status,
            }, status=status.HTTP_409_CONFLICT)
        return Response({
            'message': 'Incremental RFM refresh started.',
            'mode': 'incremental',
            'status': run_status,
        }, status=status.HTTP_202_ACCEPTED)

    def get(self, request):
        return Response({'status': cache_manager.get_run_status()},
                        status=status.HTTP_200_OK)


def _campaign_payload(campaign, detailed=False):
    """One campaign as the admin page reads it, plus its audience and coupons.

    `detailed` adds the per-cluster breakdown and the full clustering-run
    description; a list page leaves it off so it stays two counted queries for
    the whole page instead of a handful per row.
    """
    data = CampaignSerializer(campaign, context={'include_audience': detailed}).data
    data['eligible_audience_count'] = campaign_audience.campaign_audience_count(
        campaign)
    data.update(campaign_audience.audience_summary(campaign))
    return data


class CampaignClusterOptionsView(AdminRFMView):
    """GET /api/campaigns/clusters/ -> the customer groups a campaign may target.

    The Campaign page asks this instead of the RFM dashboard so authoring reads
    exactly the same numbers the dashboard shows: the four clusters of the
    latest persisted K-Means++ run, each with its business label (never assumed
    from the numeric id), how many customers are actually assigned to it and the
    unscaled RFM profile that label was derived from - plus the run they come
    from, which the campaign stores alongside its audience.
    """

    def get(self, request):
        # A run persisted before the current label vocabulary would otherwise be
        # offered with its old labels; heal them from the stored profiles first
        # (no re-clustering, no buyer moved) exactly like the dashboard reads do.
        clustering.reconcile_stored_labels()
        return Response(cluster_targeting.available_clusters(),
                        status=status.HTTP_200_OK)


class CampaignListCreateView(AdminRFMView):
    """GET/POST /api/campaigns/ -> filterable list or author a campaign.

    The list supports the admin filters (status, target customer group, offer
    type, free-text search over name/coupon code) with server-side pagination,
    and every row carries its audience and coupon figures - the eligible
    customer count plus coupons issued / redeemed / still valid - so the table
    answers "who actually receives this, and what did they do with it?".
    """

    # Pseudo-statuses the UI filter offers beyond the stored values.
    STATUS_FILTERS = {'ACTIVE', 'DRAFT', 'PAUSED', 'EXPIRED', 'PUBLISHED', 'ALL'}
    OFFER_TYPES = {'DISCOUNT', 'BUY_GET', 'COMBINED', 'ALL'}

    def get(self, request):
        rows = self._apply_filters(request, Campaign.objects.all())

        # Segment / cluster targeting lives in JSON lists, so those two filters
        # are evaluated in Python (campaign tables stay small by nature; every
        # other filter and the pagination are done server-side).
        segment = (request.query_params.get('segment') or '').strip()
        if segment and segment != 'ALL':
            rows = [c for c in rows
                    if not c.targets_clusters and segment in (c.target_segments or [])]
        cluster = (request.query_params.get('cluster') or '').strip()
        if cluster and cluster != 'ALL':
            rows = [c for c in rows
                    if c.targets_clusters and cluster in (c.target_cluster_labels or [])]

        total = len(rows)
        page, page_size = _parse_pagination(request)
        offset = (page - 1) * page_size
        page_rows = rows[offset:offset + page_size]

        summaries = campaign_audience.bulk_audience_summaries(page_rows)
        results = []
        for campaign in page_rows:
            data = CampaignSerializer(campaign).data
            data['eligible_audience_count'] = campaign_audience.campaign_audience_count(
                campaign)
            data.update(summaries.get(campaign.campaign_id, {}))
            results.append(data)
        return Response({
            'count': total,
            'page': page,
            'page_size': page_size,
            'total_pages': (total + page_size - 1) // page_size if page_size else 1,
            'results': results,
            # So the page can tell the admin why old campaigns are listed but no
            # longer reaching customers (nothing about them is deleted).
            'legacy_audience': {
                'visible_to_customers': campaign_engine.legacy_reachable(),
                'campaign_count': sum(1 for c in rows if not c.targets_clusters),
            },
        }, status=status.HTTP_200_OK)

    def _apply_filters(self, request, queryset):
        status_filter = (request.query_params.get('status') or 'ALL').strip().upper()
        if status_filter == 'ACTIVE':
            # "Active" for the admin means what customers can actually see
            # right now: published and inside its validity window.
            now = timezone.now()
            queryset = queryset.filter(status=CampaignStatus.PUBLISHED,
                                       start_date__lte=now, end_date__gte=now)
        elif status_filter == 'EXPIRED':
            now = timezone.now()
            queryset = queryset.filter(Q(status=CampaignStatus.EXPIRED)
                                       | Q(status=CampaignStatus.PUBLISHED,
                                           end_date__lt=now))
        elif status_filter in self.STATUS_FILTERS and status_filter != 'ALL':
            queryset = queryset.filter(status=status_filter)

        offer_type = (request.query_params.get('offer_type') or 'ALL').strip().upper()
        if offer_type in ('DISCOUNT', 'BUY_GET', 'COMBINED'):
            queryset = queryset.filter(offer_category=offer_type)

        search = (request.query_params.get('search') or '').strip()
        if search:
            queryset = queryset.filter(Q(name__icontains=search)
                                       | Q(coupon_code__icontains=search))
        return list(queryset)

    def post(self, request):
        serializer = CampaignSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except DRFValidationError:
            return Response({'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        campaign = serializer.save()
        # Customers must see a new campaign immediately, not after the brief
        # per-customer offer cache has expired.
        cache_manager.bump_campaign_epoch()
        return Response(_campaign_payload(campaign, detailed=True),
                        status=status.HTTP_201_CREATED)


class CampaignDetailView(AdminRFMView):
    """GET/PUT/DELETE /api/campaigns/{id}/ -> read, edit or remove a campaign."""

    def get(self, request, campaign_id):
        campaign = Campaign.objects.filter(campaign_id=campaign_id).first()
        if not campaign:
            return Response({'detail': 'Campaign not found.'}, status=status.HTTP_404_NOT_FOUND)
        data = _campaign_payload(campaign, detailed=True)
        data['redemption_count'] = campaign.redemptions.count()
        return Response(data, status=status.HTTP_200_OK)

    def put(self, request, campaign_id):
        campaign = Campaign.objects.filter(campaign_id=campaign_id).first()
        if not campaign:
            return Response({'detail': 'Campaign not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = CampaignSerializer(campaign, data=request.data, partial=True)
        try:
            serializer.is_valid(raise_exception=True)
        except DRFValidationError:
            return Response({'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        # Remember whether this edit deliberately restated the audience: only
        # then is a live campaign's coupon list extended. An untouched audience
        # keeps the customers it was published to, whatever clustering does
        # afterwards.
        audience_restated = (
            request.data.get('target_cluster_ids') is not None
            and list(campaign.target_cluster_ids or [])
            != list(serializer.validated_data.get('target_cluster_ids') or []))
        saved = serializer.save()
        cache_manager.bump_campaign_epoch()
        if audience_restated and saved.status == CampaignStatus.PUBLISHED:
            cluster_targeting.materialize_audience(saved)
        return Response(_campaign_payload(saved, detailed=True),
                        status=status.HTTP_200_OK)

    def delete(self, request, campaign_id):
        """Delete a campaign - drafts only.

        A campaign that has been published has issued coupons and a redemption
        history; deleting its row would cascade and destroy those records. The
        requirement is the opposite (history is kept forever), so the correct
        action there is Deactivate, which hides the offer and blocks redemption
        while keeping every issued coupon and redemption row.
        """
        campaign = Campaign.objects.filter(campaign_id=campaign_id).first()
        if not campaign:
            return Response({'detail': 'Campaign not found.'}, status=status.HTTP_404_NOT_FOUND)
        issued = (campaign.status != CampaignStatus.DRAFT
                  or campaign.redemptions.exists()
                  or cluster_targeting.has_audience(campaign))
        if issued:
            return Response({'detail': (
                'This campaign has been published, so it cannot be deleted - that '
                'would remove the coupons it issued and its redemption records. '
                'Deactivate it instead: customers can then no longer claim or use '
                'it, and the history stays intact.')},
                status=status.HTTP_409_CONFLICT)
        campaign.delete()
        cache_manager.bump_campaign_epoch()
        return Response({'message': 'Campaign deleted.'}, status=status.HTTP_200_OK)


class CampaignStatusView(AdminRFMView):
    """POST /api/campaigns/{id}/status/ -> publish, deactivate, reactivate, draft, expire.

    Thin HTTP layer over `campaign_publishing`, the one workflow the admin
    endpoint and the seed command share: publishing re-checks the audience, the
    dates and the offer end to end, issues the coupon to the customers of the
    campaign's own clustering run, and reports how many were targeted and issued.
    Deactivating (stored as PAUSED, shown as "Deactivated") only flips
    availability - every campaign row, issued coupon and redemption record stays.
    """

    def post(self, request, campaign_id):
        new_status = (request.data.get('status') or '').strip().upper()
        if new_status not in campaign_publishing.ALLOWED_STATUSES:
            return Response({'errors': {'status': (
                f'Status must be one of {sorted(campaign_publishing.ALLOWED_STATUSES)}.')}},
                status=status.HTTP_400_BAD_REQUEST)
        campaign = Campaign.objects.filter(campaign_id=campaign_id).first()
        if not campaign:
            return Response({'detail': 'Campaign not found.'}, status=status.HTTP_404_NOT_FOUND)
        audience, error = campaign_publishing.change_status(campaign, new_status)
        if error:
            return Response({'detail': error}, status=status.HTTP_400_BAD_REQUEST)
        data = _campaign_payload(campaign, detailed=True)
        if audience is not None:
            data['audience'] = audience
        return Response(data, status=status.HTTP_200_OK)


class CustomerOffersView(APIView):
    """GET /api/customer/me/offers -> this customer's eligible offers.

    The customer is resolved from the authenticated session, so one customer
    can never read another's offers. The list itself is cached per customer
    under the campaign + analysis epochs, so opening the home page, Your Offers
    or Member Privileges again is a pure cache read with no offer query at all -
    and any campaign change, coupon redemption or new completed analysis moves
    an epoch and is therefore visible on the very next request.
    """
    permission_classes = [IsAuthenticatedUser, IsCustomer]

    def get(self, request):
        customer = CustomerResolver.get_customer_for_user(request.user)
        cached = cache_manager.get_cached_offers(customer.customer_id)
        if cached is not None:
            return Response(cached, status=status.HTTP_200_OK)

        result = personalization.eligible_offers(customer.customer_id)
        cache_manager.set_cached_offers(customer.customer_id, result)
        return Response(result, status=status.HTTP_200_OK)


class CustomerCouponsView(CustomerOffersView):
    """GET /api/customer/me/coupons -> same offers, coupon-focused alias."""


class CheckoutCouponValidateView(APIView):
    """POST /api/checkout/validate-coupon -> backend coupon check + reprice.

    The payable amount and every benefit (discount, Buy X Get Y, cashback,
    free shipping, gift) are recomputed here from the customer's own stored
    cart rows with authoritative prices - the cart value or product quantities
    sent by the frontend are never trusted.
    """
    permission_classes = [IsAuthenticatedUser, IsCustomer]

    def post(self, request):
        customer = CustomerResolver.get_customer_for_user(request.user)
        code = request.data.get('coupon_code')
        cart_lines, cart_subtotal = _server_cart_lines(customer)
        try:
            result = coupon_validation.validate_coupon(
                customer.customer_id, code, cart_subtotal, cart_lines=cart_lines
            )
        except DRFValidationError as exc:
            return Response(
                {'detail': _flatten_error(exc)}, status=status.HTTP_400_BAD_REQUEST
            )
        return Response({'valid': True, **result}, status=status.HTTP_200_OK)


def _server_cart_lines(customer):
    """(cart lines, subtotal) read straight from the customer's cart rows."""
    items = list(CartItem.objects.filter(customer=customer).select_related('product'))
    price_map = get_product_selling_price_map(
        item.product_id for item in items if item.product)
    lines = []
    for item in items:
        if not item.product:
            continue
        lines.append({
            'product_id': str(item.product_id),
            'name': item.product.product_name or '',
            'category': item.product.main_category or '',
            'quantity': int(item.quantity or 1),
            'unit_price': float(price_map.get(str(item.product_id)) or 0),
        })
    subtotal = round(sum(l['unit_price'] * l['quantity'] for l in lines), 2)
    return lines, subtotal


def _flatten_error(exc):
    detail = exc.detail
    if isinstance(detail, dict):
        for value in detail.values():
            if isinstance(value, (list, tuple)):
                return str(value[0])
            return str(value)
    if isinstance(detail, (list, tuple)):
        return str(detail[0])
    return str(detail)
