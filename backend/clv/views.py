"""HTTP endpoints for the CLV module (admin-only, on-demand results).

Same API conventions as the RFM admin dashboard: DRF APIViews, the shared
IsAuthenticatedUser + IsAdmin permission pair, manual page/search/sort query
parameters served from the snapshot cache (no recalculation per request), and
a safe 503 on database failure. Nothing here persists CLV results; GETs read
the on-demand state and POST recalculate rebuilds it from current data.
"""

import bisect
import logging

from django.core.cache import cache
from django.db import DatabaseError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsAdmin, IsAuthenticatedUser
from rfm_analysis import segment_store
from rfm_analysis import utils as rfm_utils

from . import calc, queries, service, utils

logger = logging.getLogger(__name__)


def _attach_names(page_rows):
    """Resolve customer names for just the current page (one bulk query).

    Names are not stored in the RFM result table or the CLV snapshot, so they are
    fetched for the ~25 returned rows only - never the whole population. Guarded
    because `public.customers` is an unmanaged dataset table.
    """
    ids = [r['customer_id'] for r in page_rows if r.get('customer_name') is None]
    if not ids:
        return page_rows
    try:
        from accounts.models import Customer
        names = {c.customer_id: c.customer_name
                 for c in Customer.objects.filter(customer_id__in=ids)}
    except Exception:  # noqa: BLE001 - names are display-only
        return page_rows
    for row in page_rows:
        if row.get('customer_name') is None:
            row['customer_name'] = names.get(row['customer_id'])
    return page_rows

# Whitelist of sortable customer-table fields (everything else falls back).
SORTABLE_FIELDS = {
    'customer_id', 'customer_name', 'historical_clv', 'future_clv', 'total_clv',
    'aov', 'order_count', 'tenure_days', 'annual_frequency',
}


def _safe_db_error(request, exc):
    logger.error('clv dashboard database error (%s)', type(exc).__name__)
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


def _parse_money_param(raw):
    """Future-CLV range filter bound as a number, or None when absent/invalid."""
    try:
        return float(raw) if raw not in (None, '') else None
    except (TypeError, ValueError):
        return None


class AdminCLVView(APIView):
    """Shared base for admin-only CLV endpoints."""
    permission_classes = [IsAuthenticatedUser, IsAdmin]


class ClvSummaryView(AdminCLVView):
    """GET /api/clv/summary -> the four overview cards + cutoff metadata.

    Reading it also drives freshness: a background build is scheduled when no
    usable snapshot exists or the stored RFM analysis changed, while the
    response always reflects a fully built state (never a partial run).
    """

    def get(self, request):
        freshness = service.ensure_state()
        meta = service.get_meta()
        if not meta:
            return Response({
                'available': False,
                'refreshing': True,
                'run_status': freshness['run_status'],
                'message': 'Preparing the Customer Lifetime Value analysis. '
                           'This runs automatically in the background.',
            }, status=status.HTTP_200_OK)

        return Response({
            'available': True,
            'refreshing': freshness['refreshing'],
            'run_status': service.get_run_status(),
            'cutoff_date': meta['cutoff_date'],
            'computed_at': meta.get('computed_at'),
            'rfm_version': meta.get('rfm_version'),
            'monetary_source': meta.get('monetary_source'),
            'buyer_count': meta['buyer_count'],
            'totals': meta['totals'],
            'future_clv_status': meta['future_clv_status'],
            'future_clv_message': meta.get('future_clv_message'),
            'assumptions': meta.get('assumptions'),
            'compute_ms': meta.get('compute_ms'),
        }, status=status.HTTP_200_OK)


class ClvCustomersView(AdminCLVView):
    """GET /api/clv/customers -> paginated per-customer CLV table.

    One indexed page is read straight from the persisted RFM result table
    (server-side filter/sort/pagination over the FULL dataset, never just the
    loaded page), and only that page's ~25 rows get their derived CLV fields
    computed in Python. The population is never loaded, so opening or paging
    the list never scans the orders table nor transfers 100k rows. Fully
    serialized pages are cached under the snapshot token: while the analysis
    version is unchanged a repeated page read is a pure in-process cache hit.
    """

    def get(self, request):
        freshness = service.ensure_state()
        meta = service.get_meta()
        page, page_size = _parse_pagination(request)
        if meta is None:
            return Response({
                'available': False,
                'refreshing': True,
                'run_status': freshness['run_status'],
                'count': 0, 'page': page, 'page_size': page_size, 'total_pages': 1,
                'results': [],
            }, status=status.HTTP_200_OK)

        search = (request.query_params.get('search') or '').strip()
        tier = (request.query_params.get('tier') or '').strip()
        segment = (request.query_params.get('segment') or '').strip()
        sort = (request.query_params.get('sort') or 'historical_clv').lower()
        if sort not in SORTABLE_FIELDS:
            sort = 'historical_clv'
        direction = ('desc' if (request.query_params.get('dir') or 'desc').lower() == 'desc'
                     else 'asc')
        future_state = (request.query_params.get('future_state') or '').strip().lower()
        if future_state not in ('available', 'insufficient'):
            future_state = ''
        future_min = _parse_money_param(request.query_params.get('future_min'))
        future_max = _parse_money_param(request.query_params.get('future_max'))

        token = meta.get('token')
        cache_key = (utils.page_cache_key('|'.join(str(part)
                                                   for part in (token, page, page_size,
                                                               segment, tier, search, sort,
                                                               direction, future_min,
                                                               future_max, future_state)))
                     if token else None)
        if cache_key:
            cached = cache.get(cache_key)
            if cached is not None:
                return Response(cached, status=status.HTTP_200_OK)

        boundaries = meta.get('tier_boundaries') or {}
        retention = meta.get('cohorts')
        cutoff = calc.parse_iso_date(meta.get('cutoff_date'))

        # The per-customer Future CLV is a placeholder-free SQL expression over
        # the stored columns, so range/availability filters and sorting on it
        # run server-side against exactly the numbers each row displays.
        future_sql = calc.future_clv_sql(
            retention, monetary_col='cs.monetary',
            first_col='cs.first_purchase_date', orders_col='cs.frequency')

        rows, total = queries.fetch_customer_page(
            segment=segment, tier=tier, search=search, order_by=sort,
            direction=direction, limit=page_size, offset=(page - 1) * page_size,
            future_sql=future_sql, future_min=future_min, future_max=future_max,
            future_state=future_state or None)
        results = [calc.derive_page_row(
            r, cutoff, boundaries.get('high'), boundaries.get('medium'), retention)
            for r in rows]
        results = _attach_names(results)

        payload = {
            'available': True,
            'cutoff_date': meta.get('cutoff_date'),
            'future_clv_status': meta.get('future_clv_status'),
            'count': total,
            'page': page,
            'page_size': page_size,
            'total_pages': (total + page_size - 1) // page_size if page_size else 1,
            'results': results,
        }
        if cache_key:
            cache.set(cache_key, payload, utils.READ_CACHE_TTL_SECONDS)
        return Response(payload, status=status.HTTP_200_OK)


class ClvCustomerDetailView(AdminCLVView):
    """GET /api/clv/customers/{customer_id} -> one customer's CLV details.

    When a built state exists, the row is a direct index hit (no full-population
    recomputation). Otherwise the endpoint answers from a cheap single-customer
    aggregate over the orders table plus the stored RFM row - the value tier is
    only claimed when the population percentile boundaries are available.
    """

    def get(self, request, customer_id):
        meta = service.get_meta() if service.state_is_current() else None

        # Detail payloads are cached under the snapshot token: re-opening the
        # same customer's popup while the analysis version is unchanged is a
        # pure cache read (the fetch-on-click itself stays lazy).
        token = (meta or {}).get('token')
        cache_key = (utils.detail_cache_key(token, customer_id)
                     if token else None)
        if cache_key:
            cached = cache.get(cache_key)
            if cached is not None:
                return Response(cached, status=status.HTTP_200_OK)

        stored = segment_store.get(customer_id)
        if stored is not None and stored.monetary is not None:
            # One indexed PK read of the persisted RFM result, plus the cached
            # population boundaries - no order scan, no population load.
            cutoff = (calc.parse_iso_date(meta['cutoff_date']) if meta
                      else stored.last_purchase_date)
            boundaries = (meta or {}).get('tier_boundaries') or {}
            retention = (meta or {}).get('cohorts')
            page_row = {
                'customer_id': stored.customer_id,
                'segment': stored.segment,
                'monetary': stored.monetary,
                'frequency': stored.frequency,
                'first_purchase_date': stored.first_purchase_date,
                'last_purchase_date': stored.last_purchase_date,
            }
            derived = calc.derive_page_row(
                page_row, cutoff, boundaries.get('high'),
                boundaries.get('medium'), retention)
            _attach_names([derived])
            derived['historical_revenue'] = derived['historical_clv']
            derived['calculation_status'] = {
                'future_clv': (meta or {}).get('future_clv_status'),
                'message': (meta or {}).get('future_clv_message'),
                'assumptions': (meta or {}).get('assumptions'),
                'cutoff_date': (cutoff.isoformat()
                                if hasattr(cutoff, 'isoformat') else None),
            }
            if cache_key:
                cache.set(cache_key, derived, utils.READ_CACHE_TTL_SECONDS)
            return Response(derived, status=status.HTTP_200_OK)

        # No usable persisted result for this buyer (legacy row without Monetary,
        # or they simply have no eligible orders): derive from the orders table.
        try:
            metrics = queries.fetch_single_customer_metrics(customer_id)
        except DatabaseError as exc:
            return _safe_db_error(request, exc)
        if metrics is None:
            return Response({'detail': 'Customer not found or has no valid orders.'},
                            status=status.HTTP_404_NOT_FOUND)

        history = calc.derive_history(
            order_count=metrics['order_count'],
            revenue=metrics['revenue'],
            stored_monetary=None,
            first_date=calc.parse_iso_date(metrics['first_purchase_date']),
            last_date=calc.parse_iso_date(metrics['last_purchase_date']),
            cutoff=calc.parse_iso_date(metrics['cutoff_date']),
        )
        stored = segment_store.get(customer_id)
        boundaries = (meta or {}).get('tier_boundaries') or {}
        retention = (meta or {}).get('cohorts')
        # The population survival curve is available even before this buyer's
        # row is persisted: use it, otherwise report the estimate as pending.
        remaining, future, total = calc.future_for_customer(
            historical_clv=history['historical_clv'], aov=history['aov'],
            order_count=history['order_count'],
            first_purchase_date=metrics['first_purchase_date'],
            retention=retention)
        detail = {
            'customer_id': customer_id,
            'customer_name': None,
            'historical_clv': history['historical_clv'],
            'historical_revenue': history['historical_clv'],
            'aov': history['aov'],
            'order_count': history['order_count'],
            'first_purchase_date': metrics['first_purchase_date'],
            'last_purchase_date': metrics['last_purchase_date'],
            'tenure_days': history['tenure_days'],
            'tenure_years': history['tenure_years'],
            'annual_frequency': history['annual_frequency'],
            'rfm_segment': stored.segment if stored else None,
            'clv_tier': (calc.classify_tier(history['historical_clv'],
                                            boundaries.get('high'),
                                            boundaries.get('medium'))
                         if boundaries.get('high') is not None else None),
            'remaining_lifespan_years': remaining,
            'future_clv': future,
            'total_clv': total,
            'calculation_status': {
                'future_clv': (retention or {}).get('status')
                              or utils.STATUS_INSUFFICIENT_DATA,
                'message': (meta or {}).get('future_clv_message')
                           if future is None else None,
                'cutoff_date': metrics.get('cutoff_date'),
            },
        }
        # Same one-row name lookup as the paginated list, so the detail popup
        # can always identify the customer it belongs to.
        _attach_names([detail])
        return Response(detail, status=status.HTTP_200_OK)


def _find_record(records, customer_id):
    """Index hit in the customer_id-sorted snapshot list (O(log n))."""
    lo = bisect.bisect_left(_sorted_ids(records), customer_id)
    if lo < len(records) and records[lo]['customer_id'] == customer_id:
        return records[lo]
    return None


_ID_MEMO = {}


def _sorted_ids(records):
    """Memoized id list for the current record list (identity-keyed)."""
    key = id(records)
    cached = _ID_MEMO.get('key')
    if cached != key:
        _ID_MEMO['key'] = key
        _ID_MEMO['ids'] = [r['customer_id'] for r in records]
    return _ID_MEMO['ids']


class ClvCohortsView(AdminCLVView):
    """GET /api/clv/cohorts -> cohort sizes, annual retention, maturity.

    Every cell carries an explicit mature flag; incomplete observation periods
    are excluded (never extrapolated), the reporting cutoff is always shown and
    an insufficient-data status is returned when the history cannot support a
    survival estimate.
    """

    def get(self, request):
        freshness = service.ensure_state()
        meta = service.get_meta()
        if not meta:
            return Response({
                'available': False,
                'refreshing': True,
                'run_status': freshness['run_status'],
                'cohorts': None,
            }, status=status.HTTP_200_OK)
        return Response({
            'available': True,
            'cutoff_date': meta['cutoff_date'],
            'cohorts': meta['cohorts'],
            'future_clv_status': meta['future_clv_status'],
            'assumptions': meta.get('assumptions'),
        }, status=status.HTTP_200_OK)


class ClvSegmentsView(AdminCLVView):
    """GET /api/clv/segments -> value tier distribution + RFM segment analysis.

    High / Medium / Low are percentile tiers of historical CLV; At Risk is the
    existing RFM engagement segment reported as an overlay (its count overlaps
    the value tiers by design - the two classification systems stay separate).
    Segment analysis attributes buyers to their CURRENT RFM segment (no
    historical segment snapshots exist).
    """

    def get(self, request):
        freshness = service.ensure_state()
        meta = service.get_meta()
        if not meta:
            return Response({
                'available': False,
                'refreshing': True,
                'run_status': freshness['run_status'],
                'tiers': [], 'rfm_segments': [],
            }, status=status.HTTP_200_OK)
        return Response({
            'available': True,
            'buyer_count': meta['buyer_count'],
            'tiers': meta['tiers'],
            'at_risk': {
                'segment': rfm_utils.SEGMENT_AT_RISK,
                'count': meta['at_risk_count'],
                'note': 'RFM engagement overlay; overlaps the value tiers.',
            },
            'tier_boundaries': meta['tier_boundaries'],
            'rfm_segments': meta['segments'],
            'future_clv_status': meta['future_clv_status'],
        }, status=status.HTTP_200_OK)


class ClvRecalculateView(AdminCLVView):
    """POST /api/clv/recalculate -> rebuild CLV from current source data.

    Admin-only. Recalculation is on demand only: nothing is persisted, the
    rebuilt state lives solely in the short-lived snapshot cache. A GET on the
    same path polls the build status.
    """

    def post(self, request):
        accepted, run_status = service.start_background_build(force=True)
        if not accepted:
            return Response({
                'message': 'A CLV recalculation is already running.',
                'status': run_status,
            }, status=status.HTTP_409_CONFLICT)
        return Response({
            'message': 'CLV recalculation started.',
            'status': run_status,
        }, status=status.HTTP_202_ACCEPTED)

    def get(self, request):
        return Response({'status': service.get_run_status()},
                        status=status.HTTP_200_OK)
