"""HTTP endpoints for the RFM system, split by role.

Admin endpoints (analysis run/summary/segments and campaign CRUD) require the
ADMIN role; customer endpoints read only the authenticated customer's own
segment and offers (their id comes from the verified session, never the body).
Segment customer lists are served from the published snapshot with server-side
search, sorting and pagination, so the browser never receives all ~100k rows.
"""

import logging

from django.db import DatabaseError
from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.serializers import ValidationError as DRFValidationError

from accounts.permissions import IsAdmin, IsAuthenticatedUser, IsCustomer
from cart.models import CartItem
from cart.services import CustomerResolver
from catalog.pricing import get_product_selling_price_map

from . import (cache_manager, campaign_audience, coupon_validation, engine,
               personalization, queries, utils)
from .models import Campaign, CampaignStatus
from .serializers import CampaignSerializer

logger = logging.getLogger(__name__)

# Whitelist of sortable record fields for the segment detail table.
SORTABLE_FIELDS = {
    'customer_id', 'recency_days', 'frequency', 'monetary',
    'r_percentile', 'f_percentile', 'm_percentile',
    'r_score', 'f_score', 'm_score',
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


class RfmSummaryView(AdminRFMView):
    """GET /api/analytics/rfm/summary -> aggregate KPIs and segment cards.

    Reading this endpoint also drives the automatic refresh (Section 2): a
    background run is started when no analysis exists or the latest one is
    older than the threshold, but the response always reflects the latest
    successfully completed snapshot (never a partial run).
    """

    def get(self, request):
        freshness = engine.ensure_latest()
        meta = cache_manager.get_meta()
        if not meta:
            return Response({
                'available': False,
                'refreshing': True,
                'run_status': freshness['run_status'],
                'message': 'Preparing the RFM analysis. This runs automatically in the background.',
            }, status=status.HTTP_200_OK)

        counts = meta['segment_counts']
        totals = meta['totals']
        segment_cards = [
            {'segment': label, 'count': counts.get(label, 0)}
            for label in utils.PRIMARY_SEGMENTS
        ]
        segment_cards.append({
            'segment': utils.SEGMENT_NEVER_PURCHASED,
            'count': totals.get('never_purchased_customers', 0),
        })

        return Response({
            'available': True,
            'version': meta['version'],
            'analysis_date': meta['analysis_date'],
            'computed_at': meta.get('computed_at'),
            'refreshing': freshness['refreshing'],
            'run_status': cache_manager.get_run_status(),
            'totals': totals,
            'buyer_count': meta['buyer_count'],
            'big_spender_count': meta['big_spender_count'],
            'segments': segment_cards,
            'compute_ms': meta.get('compute_ms'),
        }, status=status.HTTP_200_OK)


class RfmSegmentsView(AdminRFMView):
    """GET /api/analytics/rfm/segments -> segment counts only."""

    def get(self, request):
        meta = cache_manager.get_meta()
        if not meta:
            return Response({'available': False, 'segments': []},
                            status=status.HTTP_200_OK)
        counts = meta['segment_counts']
        return Response({
            'available': True,
            'version': meta['version'],
            'segments': [{'segment': label, 'count': counts.get(label, 0)}
                         for label in utils.PRIMARY_SEGMENTS],
            'never_purchased': meta['totals'].get('never_purchased_customers', 0),
            'big_spender_count': meta['big_spender_count'],
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
        search = (request.query_params.get('search') or '').strip().lower()
        sort = (request.query_params.get('sort') or 'customer_id').lower()
        direction = (request.query_params.get('dir') or 'asc').lower()
        if sort not in SORTABLE_FIELDS:
            sort = 'customer_id'

        # Big Spenders is a secondary tag, not a primary segment: its list is
        # the buyers who carry the tag, regardless of their primary segment.
        if segment == utils.TAG_BIG_SPENDER:
            rows, version = cache_manager.get_segment_base(segment, sort, direction)
            if rows is None:
                return Response({'available': False, 'results': [], 'count': 0},
                                status=status.HTTP_200_OK)
            return self._respond(segment, rows, page, page_size, search, version)

        if segment not in utils.ALL_SEGMENTS:
            return Response({'detail': 'Unknown segment.'},
                            status=status.HTTP_404_NOT_FOUND)

        if segment == utils.SEGMENT_NEVER_PURCHASED:
            return self._never_purchased_page(request, page, page_size, search)

        rows, version = cache_manager.get_segment_base(segment, sort, direction)
        if rows is None:
            return Response({'available': False, 'results': [], 'count': 0},
                            status=status.HTTP_200_OK)
        return self._respond(segment, rows, page, page_size, search, version)

    def _respond(self, label, base_rows, page, page_size, search, version):
        rows = base_rows
        if search:
            rows = [
                r for r in base_rows
                if search in str(r['customer_id']).lower()
                or search in str(r.get('customer_name') or '').lower()
            ]
        total = len(rows)
        start = (page - 1) * page_size
        page_rows = [cache_manager.project_row(r) for r in rows[start:start + page_size]]
        return Response({
            'available': True,
            'segment': label,
            'version': version,
            'count': total,
            'page': page,
            'page_size': page_size,
            'total_pages': (total + page_size - 1) // page_size if page_size else 1,
            'results': page_rows,
        }, status=status.HTTP_200_OK)

    def _never_purchased_page(self, request, page, page_size, search):
        version = cache_manager.get_latest_version()
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


class CampaignListCreateView(AdminRFMView):
    """GET/POST /api/campaigns/ -> filterable list or author a campaign.

    The list supports the admin filters (status, target segment, offer type,
    free-text search over name/coupon code) with server-side pagination, and
    every row carries its live eligible-audience count from the latest RFM
    snapshot, so the table always answers "who actually receives this?".
    """

    # Pseudo-statuses the UI filter offers beyond the stored values.
    STATUS_FILTERS = {'ACTIVE', 'DRAFT', 'PAUSED', 'EXPIRED', 'PUBLISHED', 'ALL'}
    OFFER_TYPES = {'DISCOUNT', 'BUY_GET', 'COMBINED', 'ALL'}

    def get(self, request):
        rows = self._apply_filters(request, Campaign.objects.all())

        # Segment targeting lives in a JSON list, so that one filter is
        # evaluated in Python (campaign tables stay small by nature; every
        # other filter and the pagination are done server-side).
        segment = (request.query_params.get('segment') or '').strip()
        if segment and segment != 'ALL':
            rows = [c for c in rows if segment in (c.target_segments or [])]

        total = len(rows)
        page, page_size = _parse_pagination(request)
        offset = (page - 1) * page_size
        page_rows = rows[offset:offset + page_size]

        results = []
        for campaign in page_rows:
            data = CampaignSerializer(campaign).data
            data['eligible_audience_count'] = campaign_audience.audience_count(
                campaign.target_segments, campaign.target_tags)
            results.append(data)
        return Response({
            'count': total,
            'page': page,
            'page_size': page_size,
            'total_pages': (total + page_size - 1) // page_size if page_size else 1,
            'results': results,
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
        serializer.save()
        # Customers must see a new campaign immediately, not after the brief
        # per-customer offer cache has expired.
        cache_manager.bump_campaign_epoch()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class CampaignDetailView(AdminRFMView):
    """GET/PUT/DELETE /api/campaigns/{id}/ -> read, edit or remove a campaign."""

    def get(self, request, campaign_id):
        campaign = Campaign.objects.filter(campaign_id=campaign_id).first()
        if not campaign:
            return Response({'detail': 'Campaign not found.'}, status=status.HTTP_404_NOT_FOUND)
        data = CampaignSerializer(campaign).data
        data['eligible_audience_count'] = campaign_audience.audience_count(
            campaign.target_segments, campaign.target_tags)
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
        serializer.save()
        cache_manager.bump_campaign_epoch()
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, campaign_id):
        deleted, _ = Campaign.objects.filter(campaign_id=campaign_id).delete()
        if not deleted:
            return Response({'detail': 'Campaign not found.'}, status=status.HTTP_404_NOT_FOUND)
        cache_manager.bump_campaign_epoch()
        return Response({'message': 'Campaign deleted.'}, status=status.HTTP_200_OK)


class CampaignStatusView(AdminRFMView):
    """POST /api/campaigns/{id}/status/ -> publish, pause, resume, draft, expire.

    Publishing is an explicit admin action; nothing auto-publishes. Resuming
    or publishing re-checks the campaign end to end first: a campaign without
    a target segment, with no valid offer, or whose dates have already lapsed
    is refused, so a "Published" row is always one customers may actually see.
    Pausing keeps every campaign row and its redemption history untouched -
    it only flips availability.
    """

    def post(self, request, campaign_id):
        new_status = (request.data.get('status') or '').strip().upper()
        allowed = {CampaignStatus.DRAFT, CampaignStatus.PUBLISHED,
                   CampaignStatus.PAUSED, CampaignStatus.EXPIRED}
        if new_status not in allowed:
            return Response({'errors': {'status': f'Status must be one of {sorted(allowed)}.'}},
                            status=status.HTTP_400_BAD_REQUEST)
        campaign = Campaign.objects.filter(campaign_id=campaign_id).first()
        if not campaign:
            return Response({'detail': 'Campaign not found.'}, status=status.HTTP_404_NOT_FOUND)
        if new_status == CampaignStatus.PUBLISHED:
            error = self._publish_blocker(campaign)
            if error:
                return Response({'detail': error}, status=status.HTTP_400_BAD_REQUEST)
        campaign.status = new_status
        campaign.save(update_fields=['status', 'updated_at'])
        cache_manager.bump_campaign_epoch()
        data = CampaignSerializer(campaign).data
        data['eligible_audience_count'] = campaign_audience.audience_count(
            campaign.target_segments, campaign.target_tags)
        return Response(data, status=status.HTTP_200_OK)

    @staticmethod
    def _publish_blocker(campaign):
        if not campaign.target_segments:
            return ('Publish this campaign to at least one RFM segment first - '
                    'offers must never go to all customers.')
        now = timezone.now()
        if campaign.end_date <= now:
            return ('This campaign\'s validity has already ended. '
                    'Update its dates before publishing.')
        serializer = CampaignSerializer(campaign, data={}, partial=True)
        # Re-run the full offer validation against the stored configuration,
        # so a campaign edited before the rules tightened cannot be published
        # half-configured.
        try:
            serializer.is_valid(raise_exception=True)
        except DRFValidationError as exc:
            return _flatten_error(exc)
        return None


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
