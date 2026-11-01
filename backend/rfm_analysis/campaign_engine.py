"""Campaign fetching and evaluation against a customer's segment.

Campaigns are authored, approved and published by an admin (Section 11): the
personalization engine never invents or auto-publishes a campaign, it only
reads persisted ones and decides which are currently visible to a customer.

A campaign is *active* only when it is PUBLISHED and the current time is within
its start/end window. An expired-but-still-PUBLISHED row is reported as expired
rather than silently treated as live.
"""

from django.utils import timezone

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


def matches_customer(campaign, segment, tags):
    """Does this campaign target the customer's primary segment and tags?

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


def status_label(campaign, now=None):
    """Effective status for display, distinguishing a lapsed PUBLISHED row."""
    now = now or timezone.now()
    if campaign.status == CampaignStatus.PUBLISHED and campaign.end_date < now:
        return 'expired'
    return campaign.status.lower()
