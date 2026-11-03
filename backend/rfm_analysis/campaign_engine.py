"""Campaign fetching and evaluation against a customer's audience.

Campaigns are authored, approved and published by an admin (Section 11): the
personalization engine never invents or auto-publishes a campaign, it only
reads persisted ones and decides which are currently visible to a customer.

A campaign is *active* only when it is PUBLISHED and the current time is within
its start/end window. An expired-but-still-PUBLISHED row is reported as expired
rather than silently treated as live.

Two audience definitions coexist, and a campaign declares which one it uses:

* K-Means campaigns (`targeting_mode = KMEANS`, every campaign authored from
  the Campaign page from now on) are matched against the coupon assignments
  materialized for them - the customers of their selected clusters, frozen at
  publish time.
* Legacy rule-segment campaigns are still matched from the customer's current
  segment and tags, exactly as before, so a campaign published before the
  switch keeps its original audience and its issued coupons keep redeeming.
"""

from django.utils import timezone

from . import cluster_targeting, utils
from .models import Campaign, CampaignStatus


def fetch_published_campaigns(now=None):
    """Every currently live PUBLISHED campaign.

    The status and the validity window are filtered in SQL (backed by the
    `campaign_live_window` index) instead of loading every campaign and
    filtering in Python, so a customer request reads only the small live set.
    """
    now = now or timezone.now()
    return list(Campaign.objects.filter(
        status=CampaignStatus.PUBLISHED,
        start_date__lte=now,
        end_date__gte=now,
    ))


def legacy_reachable():
    """Can a campaign built on the previous rule-based segments still reach a
    customer? Only when the operator explicitly re-enables it.

    Personalised coupons are chosen from the four K-Means clusters now, and a
    customer must be able to see - and use - only the offer of the group they
    belong to. The segments a legacy campaign names are not those groups, so a
    live segment campaign would show a customer offers from clusters they are not
    in. This gates visibility at read time only: the campaign rows, the coupons
    they issued and every redemption record are untouched.
    """
    return utils.LEGACY_CAMPAIGNS_VISIBLE_TO_CUSTOMERS


def matches_customer(campaign, segment, tags):
    """Legacy rule-based targeting: segment and (optionally) secondary tags.

    Only ever consulted for a campaign whose `targeting_mode` is `LEGACY_RFM`.

    * The customer's primary segment must be one of the campaign's target
      segments (a campaign targeting no segment matches no one).
    * If the campaign requires secondary tags, the customer must carry at least
      one of them; a campaign with no tag requirement ignores tags entirely.
    """
    if not campaign.target_segments:
        return False
    if segment not in campaign.target_segments:
        return False
    if campaign.target_tags:
        return bool(set(campaign.target_tags) & set(tags or []))
    return True


def is_eligible(campaign, customer_id, segment, tags):
    """Is this customer part of this campaign's audience?

    A K-Means campaign holds its audience as coupon assignments, so membership
    is one indexed lookup and no RFM threshold or segment rule is applied at
    all. A legacy campaign keeps the segment/tag rule above - and is unreachable
    for customers unless `legacy_reachable()` is turned on - so a customer can
    never redeem an offer from a group they do not belong to.
    """
    if campaign.targets_clusters:
        return cluster_targeting.is_member(campaign, customer_id)
    if not legacy_reachable():
        return False
    return matches_customer(campaign, segment, tags)


def live_campaigns_for(customer_id, segment, tags, campaigns=None, now=None):
    """The published campaigns this customer may currently see.

    A single query answers the cluster-membership question for every K-Means
    campaign at once, so the offer list costs one read per customer rather than
    one per campaign.
    """
    campaigns = (fetch_published_campaigns(now) if campaigns is None
                 else list(campaigns))
    legacy = [c for c in campaigns if not c.targets_clusters]
    cluster_ids = {c.campaign_id for c in campaigns if c.targets_clusters}

    visible = [c for c in legacy if legacy_reachable()
               and matches_customer(c, segment, tags)]
    if cluster_ids:
        members = cluster_targeting.member_campaign_ids(customer_id, cluster_ids)
        visible += [c for c in campaigns
                    if c.targets_clusters and c.campaign_id in members]
    return visible


def status_label(campaign, now=None):
    """Effective status for display, distinguishing a lapsed PUBLISHED row."""
    now = now or timezone.now()
    if campaign.status == CampaignStatus.PUBLISHED and campaign.end_date < now:
        return 'expired'
    return campaign.status.lower()
