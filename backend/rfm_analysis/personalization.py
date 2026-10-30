"""Rule-based personalization: match a customer to their eligible offers.

The customer's identity always comes from the authenticated session (never a
frontend-supplied id), their segment is read from the latest *successfully
completed* snapshot, and eligibility is decided purely against persisted, admin-
published campaigns. Nothing here auto-creates or auto-publishes anything.

If no completed analysis exists yet, a customer simply has no segment and so
sees no personalized offers; the code never fabricates a segment or falls back
to a partial run.
"""

from bisect import bisect_left

from . import cache_manager, campaign_engine


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
    """Return (segment, tags, record, version) from the latest completed run.

    `segment` is None when no analysis has run or the customer has no eligible
    purchase (Never Purchased), in which case there are no personalized offers.
    """
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


def _offer_payload(campaign):
    return {
        'campaign_id': campaign.campaign_id,
        'name': campaign.name,
        'coupon_code': campaign.coupon_code,
        'description': campaign.description,
        'discount_type': campaign.discount_type,
        'discount_value': float(campaign.discount_value),
        'max_discount': float(campaign.max_discount) if campaign.max_discount is not None else None,
        'min_order_amount': float(campaign.min_order_amount or 0),
        'usage_type': campaign.usage_type,
        'start_date': campaign.start_date.isoformat(),
        'end_date': campaign.end_date.isoformat(),
        'target_segments': campaign.target_segments,
        'target_tags': campaign.target_tags,
    }


def eligible_offers(customer_id):
    """Every currently-visible, personalized offer for this authenticated customer."""
    segment, tags, _record, version = get_customer_segment(customer_id)
    if not segment:
        return {'version': version, 'segment': None, 'tags': [], 'offers': []}

    campaigns = campaign_engine.fetch_published_campaigns()
    offers = [
        _offer_payload(campaign)
        for campaign in campaigns
        if campaign_engine.matches_customer(campaign, segment, tags)
    ]
    return {'version': version, 'segment': segment, 'tags': tags, 'offers': offers}
