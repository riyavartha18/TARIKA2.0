"""Live audience size for a campaign's targeting.

Two audience definitions have to be counted, because both exist in the campaign
table and neither may be reinterpreted:

* A K-Means campaign (`targeting_mode = KMEANS`) is counted from the persisted
  cluster assignments of the clustering run it references. While it is still a
  draft that is the number of buyers the publish step would issue a coupon to;
  once it has been published the answer is the coupons actually issued, so the
  figure shown for a live campaign is the frozen audience and never moves when
  clustering is re-run later.
* A legacy rule-segment campaign is counted from the most recently *completed*
  RFM analysis (the snapshot cache), never from a stored assignment: when a
  fresh run moves a customer out of Champions they stop counting towards
  Champions campaigns. When a campaign only names primary segments the answer is
  a metadata sum (no row scan); the Big Spender secondary tag needs the segment
  buckets, which the cache already keeps grouped, so it stays cheap.
"""

from django.db.models import Count

from . import cache_manager, cluster_targeting, utils
from .models import CampaignAudience, CampaignRedemption


def audience_count(segments, tags):
    """Eligible customer count for these legacy targets, or None if no analysis yet."""
    meta = cache_manager.get_meta()
    if not meta:
        return None
    segments = [s for s in (segments or []) if s in utils.ALL_SEGMENTS]
    if not segments:
        return 0
    tags = [t for t in (tags or []) if t in utils.SECONDARY_TAGS]

    if not tags:
        counts = meta['segment_counts']
        return sum(int(counts.get(s, 0)) for s in segments)

    total = 0
    for segment in segments:
        rows, _version = cache_manager.get_segment_base(segment)
        if not rows:
            continue
        total += sum(1 for r in rows
                     if set(tags) & set(r.get('tags') or []))
    return total


def campaign_audience_count(campaign):
    """How many customers this campaign reaches (None = not computable yet)."""
    if not campaign.targets_clusters:
        return audience_count(campaign.target_segments, campaign.target_tags)
    if not campaign.target_cluster_ids:
        return 0
    issued = CampaignAudience.objects.filter(campaign=campaign).count()
    if issued:
        # Published (or re-published): the audience is the coupons issued to it.
        return issued
    return cluster_targeting.audience_size(campaign.target_cluster_ids)


def audience_summary(campaign, issued=None, redeemed=None):
    """The coupon figures the campaign dashboard reports.

    ``issued`` / ``redeemed`` may be passed in by a list view that counted both
    for the whole page in one query each; on their own they are two cheap
    indexed counts.
    """
    if issued is None:
        if campaign.targets_clusters:
            issued = CampaignAudience.objects.filter(campaign=campaign).count()
        else:
            # A legacy campaign issues no per-customer coupons: its audience is
            # whoever currently matches its segments, so nothing is "issued"
            # until a customer actually redeems.
            issued = campaign_audience_count(campaign) or 0
    if redeemed is None:
        redeemed = campaign.redemptions.count()
    remaining = max(int(issued) - int(redeemed), 0)
    if campaign.global_usage_limit:
        remaining = min(remaining, max(int(campaign.global_usage_limit) - int(redeemed), 0))
    return {
        'coupons_issued': int(issued),
        'coupons_redeemed': int(redeemed),
        'coupons_remaining': remaining,
    }


def bulk_audience_summaries(campaigns):
    """``{campaign_id: audience_summary}`` for a page, in two queries total."""
    campaign_ids = [c.campaign_id for c in campaigns]
    issued_by_campaign = cluster_targeting.coupons_issued(campaign_ids)
    redeemed_by_campaign = {
        row['campaign_id']: row['count']
        for row in CampaignRedemption.objects
        .filter(campaign_id__in=campaign_ids)
        .values('campaign_id')
        .annotate(count=Count('redemption_id'))
    }

    summaries = {}
    for campaign in campaigns:
        issued = issued_by_campaign.get(campaign.campaign_id)
        if issued is None and not campaign.targets_clusters:
            issued = audience_count(campaign.target_segments, campaign.target_tags)
        summaries[campaign.campaign_id] = audience_summary(
            campaign,
            issued=issued or 0,
            redeemed=redeemed_by_campaign.get(campaign.campaign_id, 0))
    return summaries
