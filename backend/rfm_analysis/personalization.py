"""Rule-based personalization: match a customer to their eligible offers.

The customer's identity always comes from the authenticated session (never a
frontend-supplied id), and eligibility is decided purely against persisted,
admin-published campaigns: a K-Means campaign by the coupon assignments it was
published with, the historical rule-segment campaigns by the segment read from
the latest *successfully completed* analysis. Nothing here auto-creates or
auto-publishes anything.

If no completed analysis exists yet, a customer simply has no segment and so
sees no personalized offers; the code never fabricates a segment or falls back
to a partial run.
"""

from bisect import bisect_left
from functools import lru_cache
import re

from django.utils import timezone

from . import cache_manager, campaign_engine, segment_store, utils
from .models import CampaignRedemption

# Customer-facing redemption state of an offer. The labels are what My Profile,
# Member Privileges and Your Offers show; they are derived from the campaign's
# dates and that customer's own redemption rows.
STATUS_AVAILABLE = 'AVAILABLE'
STATUS_USED = 'USED'
STATUS_EXPIRED = 'EXPIRED'


def _find_record(customer_ids, records, customer_id):
    """Binary search the snapshot's customer-sorted records for one id.

    Records and their `customer_ids` are stored sorted at publish time, so
    locating a single buyer is O(log n) instead of a linear scan over ~100k
    rows on every dashboard request.
    """
    if not customer_ids:
        return None
    index = bisect_left(customer_ids, customer_id)
    if index < len(records) and records[index]['customer_id'] == customer_id:
        return records[index]
    return None


def get_customer_segment(customer_id):
    """Return (segment, tags, record, version) for one authenticated buyer.

    The durable one-row-per-buyer store is read first: a single primary-key
    lookup, no snapshot deserialization, and it stays valid across server
    restarts and cache TTLs, so opening a customer page never recomputes the
    analysis. Only when no analysis has ever been stored does this fall back to
    the cached snapshot (the dashboard's own view of the same completed run).

    `segment` is None when the customer has no eligible purchase
    (Never Purchased), in which case there are no personalized offers.
    """
    row = segment_store.get(customer_id)
    if row is not None:
        return row.segment, row.tags or [], None, row.version

    state = segment_store.get_state()
    if state is not None:
        # A completed analysis is stored and this customer is simply not in it:
        # they have no eligible purchase, which is a real answer, not a pending
        # one - so no recompute is triggered.
        return None, [], None, state.version

    version = cache_manager.get_latest_version()
    if version is None:
        return None, [], None, None
    records, customer_ids = cache_manager.get_records(version)
    if records is None:
        return None, [], None, None

    record = _find_record(customer_ids, records, customer_id)
    if not record:
        return None, [], None, version
    return record.get('segment'), record.get('tags') or [], record, version


@lru_cache(maxsize=1)
def _segment_prefix_pattern():
    """Regex matching a leading "<Segment>: " (or "-"/"–") label on a campaign name.

    Admins author campaigns as "Champions: VIP 15% OFF" so the segment is obvious
    in the back office. A customer must never see that label, so the customer-
    facing payload strips it. The stored campaign (and its target_segments) is
    untouched - eligibility and targeting keep using the real assignment.
    """
    labels = '|'.join(re.escape(label) for label in utils.ALL_SEGMENTS)
    return re.compile(rf'^\s*(?:{labels})\s*[:\-–—]\s*', re.IGNORECASE)


def customer_facing_name(name):
    """Offer title without any RFM segment prefix, for every segment alike."""
    if not name:
        return ''
    return _segment_prefix_pattern().sub('', name, count=1).strip()


def _newest_first_key(campaign):
    """Sort key putting the most recently published campaign first."""
    return (campaign.start_date, campaign.campaign_id)


def _offer_payload(campaign, redemption=None, now=None):
    from . import benefits
    return {
        'campaign_id': campaign.campaign_id,
        'name': customer_facing_name(campaign.name),
        'coupon_code': campaign.coupon_code,
        'description': campaign.description,
        'offer_category': campaign.offer_category,
        'offer_summary': benefits.offer_summary(campaign),
        'discount_type': campaign.discount_type,
        'discount_value': float(campaign.discount_value),
        'max_discount': float(campaign.max_discount) if campaign.max_discount is not None else None,
        'min_order_amount': float(campaign.min_order_amount or 0),
        'usage_type': campaign.usage_type,
        'start_date': campaign.start_date.isoformat(),
        'end_date': campaign.end_date.isoformat(),
        'target_segments': campaign.target_segments,
        'target_tags': campaign.target_tags,
        # Which segmentation this offer was aimed at, and - for a K-Means offer -
        # the four-label group it belongs to. Displayed as the offer's own
        # wording, never as an internal RFM term.
        'targeting_mode': campaign.targeting_mode,
        'target_cluster_ids': campaign.target_cluster_ids,
        'target_cluster_labels': campaign.target_cluster_labels,
        # Redemption state, decided from the audit table (never from the
        # frontend): AVAILABLE / USED / EXPIRED.
        'status': offer_status(campaign, redemption, now),
        'used_at': (redemption['redeemed_at'].isoformat() if redemption else None),
        'used_on_order': (redemption['order_id'] if redemption else None),
    }


def offer_status(campaign, redemption=None, now=None):
    """AVAILABLE, USED (this customer already redeemed it) or EXPIRED."""
    if redemption:
        return STATUS_USED
    now = now or timezone.now()
    if campaign.end_date < now:
        return STATUS_EXPIRED
    return STATUS_AVAILABLE


def eligible_offers(customer_id):
    """Every visible, personalized offer for this authenticated customer.

    The list is exactly the campaigns whose audience contains this customer and
    that are live right now, plus the ones this customer has already redeemed (a
    Used offer stays visible, it never becomes redeemable again and its row is
    never deleted). Paused and draft campaigns stay hidden, and a campaign of
    another audience is never included - neither a K-Means campaign the customer
    was not issued a coupon by, nor a legacy campaign of a segment the customer
    does not belong to.

    Still-usable offers come first (newest campaign first), so every customer
    surface - the home feature, Your Offers and Member Privileges - leads with
    the same offer and reads the same list in the same order.

    ``syncing`` is True when no completed analysis exists in this process yet:
    the snapshot lives only in the shared cache, so a freshly started server can
    legitimately have published campaigns but no segment data. A background run
    is requested (lock-guarded, never blocking this request) and the client is
    told to retry, instead of being shown a false "no offers" empty state.
    """
    segment, tags, _record, version = get_customer_segment(customer_id)

    if version is None:
        from . import engine
        if cache_manager.try_offer_self_heal():
            engine.ensure_latest()
        return {'version': None, 'segment': None, 'tags': [], 'offers': [],
                'syncing': True}

    if not segment:
        return {'version': version, 'segment': None, 'tags': [], 'offers': [],
                'syncing': False}

    live = campaign_engine.live_campaigns_for(customer_id, segment, tags)
    live_ids = {campaign.campaign_id for campaign in live}

    # Redemptions decide the Used state, and also keep a campaign visible after
    # it has been consumed (one query for both).
    redemptions = {}
    history = []
    for row in (CampaignRedemption.objects
                .filter(customer_id=customer_id)
                .select_related('campaign')
                .order_by('redemption_id')):
        campaign = row.campaign
        if not campaign or not campaign_engine.is_eligible(
                campaign, customer_id, segment, tags):
            continue
        redemptions[campaign.campaign_id] = {
            'campaign_id': campaign.campaign_id,
            'order_id': row.order_id,
            'redeemed_at': row.redeemed_at,
            'discount_applied': row.discount_applied,
        }
        if campaign.campaign_id not in live_ids:
            history.append(campaign)

    now = timezone.now()
    live_used = [c for c in live if c.campaign_id in redemptions]
    available = sorted((c for c in live if c.campaign_id not in redemptions),
                       key=_newest_first_key, reverse=True)
    consumed = sorted(live_used + history, key=_newest_first_key, reverse=True)

    offers = [
        _offer_payload(campaign, redemptions.get(campaign.campaign_id), now)
        for campaign in available + consumed
    ]
    return {'version': version, 'segment': segment, 'tags': tags, 'offers': offers,
            'syncing': False}
