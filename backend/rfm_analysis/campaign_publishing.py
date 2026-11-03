"""The single campaign publish / status-change workflow.

Both the admin status endpoint and the seed command go through here, so there is
exactly one definition of what "Published" means and one place where a
K-Means campaign's audience is turned into real coupon assignments.

Rules this module enforces:

* Publishing is always an explicit admin action; nothing auto-publishes.
* A campaign is publishable only when it has a resolvable audience, live dates
  and a complete, valid offer configuration - so a row shown as Published is one
  a customer may actually see and use.
* A K-Means campaign's audience is resolved from the persisted cluster
  assignments of the clustering run the campaign itself references, and issued
  through `CampaignAudience` (one row per customer, duplicate-proof by a unique
  constraint). Re-publishing after a pause keeps the customers it already issued
  to: a later clustering run cannot move a published campaign's audience.
* Status changes never delete anything. Coupons already issued and every
  redemption record survive a deactivation, an expiry or a re-activation.
"""

from django.utils import timezone
from rest_framework.serializers import ValidationError as DRFValidationError

from . import cache_manager, cluster_targeting
from .models import CampaignStatus
from .serializers import CampaignSerializer

# The statuses the admin workflow may set. `PAUSED` is surfaced as "Deactivated":
# customers can neither claim nor redeem it, while its history stays.
ALLOWED_STATUSES = {CampaignStatus.DRAFT, CampaignStatus.PUBLISHED,
                    CampaignStatus.PAUSED, CampaignStatus.EXPIRED}


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


def cluster_blocker(campaign):
    """Why a K-Means campaign cannot (yet) be published, or None."""
    if not campaign.target_cluster_ids:
        return ('This campaign has no customer group selected. Choose at least '
                'one of the four K-Means clusters before publishing.')
    if campaign.clustering_run_id is None:
        return ('This campaign does not reference a persisted K-Means clustering '
                'run. Re-select its customer groups, which stores the current run.')
    if cluster_targeting.audience_size(campaign.target_cluster_ids) <= 0:
        return ('None of the selected customer groups contains any customer in the '
                'stored clustering. Re-run the clustering on the RFM page, then '
                're-select the audience of this campaign.')
    return None


def dates_and_rules_blocker(campaign):
    """Re-validate the stored offer and its dates before it goes live."""
    if campaign.end_date <= timezone.now():
        return ("This campaign's validity has already ended. "
                'Update its dates before publishing.')
    serializer = CampaignSerializer(campaign, data={}, partial=True)
    # A campaign edited before the rules tightened cannot be published
    # half-configured: the full offer validation runs against the stored data.
    try:
        serializer.is_valid(raise_exception=True)
    except DRFValidationError as exc:
        return _flatten_error(exc)
    return None


def publish_blocker(campaign):
    """(error message, audience result); error None means it may be published."""
    if campaign.targets_clusters:
        error = cluster_blocker(campaign)
    elif not campaign.target_segments:
        error = ('Publish this campaign to at least one customer group first - '
                 'offers must never go to all customers.')
    else:
        error = None
    if error:
        return error, None
    error = dates_and_rules_blocker(campaign)
    if error:
        return error, None
    audience = issue_coupons(campaign) if campaign.targets_clusters else None
    return None, audience


def issue_coupons(campaign):
    """Assign the coupon to the campaign's audience, or report the frozen one.

    Idempotent: a campaign that has been published before keeps exactly the
    customers its `CampaignAudience` rows name, so neither a pause/resume cycle
    nor a future clustering run changes who holds it.
    """
    if cluster_targeting.has_audience(campaign):
        return cluster_targeting.audience_stats(campaign)
    return cluster_targeting.materialize_audience(campaign)


def change_status(campaign, new_status):
    """Move a campaign to `new_status`, publishing its audience when required.

    Returns ``(audience, error)``: on a refusal the campaign is left untouched
    and `error` is a plain admin-readable reason. On success `audience` holds the
    K-Means issue counts (None for a legacy-segment campaign) and the cached
    customer offer lists are invalidated, so the change is live on the
    customer's next request.
    """
    new_status = (new_status or '').strip().upper()
    if new_status not in ALLOWED_STATUSES:
        return None, f'Status must be one of {sorted(ALLOWED_STATUSES)}.'

    audience = None
    if new_status == CampaignStatus.PUBLISHED:
        error, audience = publish_blocker(campaign)
        if error:
            return None, error

    campaign.status = new_status
    campaign.save(update_fields=['status', 'updated_at'])
    cache_manager.bump_campaign_epoch()
    return audience, None
