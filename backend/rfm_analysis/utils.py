"""Shared helpers and centralized RFM business configuration.

Every threshold, eligibility rule and cache key used by the RFM module lives
here (or in `segmentation.py`) so nothing is scattered across files and the
business rules can be reviewed in one place. Values may be overridden through
environment variables - nothing customer- or campaign-specific is hardcoded.
"""

import os


# ---------------------------------------------------------------------------
# Order eligibility (Section 4 of the business requirements)
# ---------------------------------------------------------------------------
# Verified against the live Neon schema: `delivery_status` only ever carries
# 'Delivered', 'In Transit', 'Returned' or NULL, so exactly one value proves a
# completed purchase. The list stays configurable through the environment.
def eligible_delivery_statuses():
    raw = os.getenv('RFM_ELIGIBLE_DELIVERY_STATUSES', 'Delivered')
    return [item.strip() for item in raw.split(',') if item.strip()]


# Negative `final_price` rows were verified to be data corruption (the line
# discount exceeded the line gross), not refunds: they occur across every
# delivery status. They are excluded from Monetary and order counts; the
# excluded volume is reported in the analysis summary for auditability.
EXCLUDE_NEGATIVE_FINAL_PRICE = (
    os.getenv('RFM_EXCLUDE_NEGATIVE_FINAL_PRICE', '1').strip() != '0'
)

# Orders dated in the future (the dataset contains rows past "today") are kept
# for Frequency/Monetary but can never produce a negative Recency: the
# analysis date is the greater of "today" and the latest purchase date.
ANALYSIS_DATE_KEY = 'analysis_date'

# ---------------------------------------------------------------------------
# Cache strategy (Section 9: no permanent RFM table, snapshot only)
# ---------------------------------------------------------------------------
RFM_SNAPSHOT_POINTER_KEY = 'rfm:analysis:latest_version'
RFM_SNAPSHOT_META_KEY = 'rfm:analysis:snapshot:meta:{version}'
RFM_SNAPSHOT_RECORDS_KEY = 'rfm:analysis:snapshot:records:{version}'
RFM_RUN_STATUS_KEY = 'rfm:analysis:run_status'
RFM_RUN_LOCK_KEY = 'rfm:analysis:run_lock'
# Rate limit for the dashboard's background freshness nudge. Opening the RFM
# page must not pay for a state read plus a possible run decision on every
# request: the first request in this window schedules it on a worker thread and
# the rest simply get the already-cached run status.
RFM_FRESHNESS_NUDGE_KEY = 'rfm:analysis:freshness_nudge'
RFM_FRESHNESS_NUDGE_SECONDS = int(os.getenv('RFM_FRESHNESS_NUDGE_SECONDS', 2 * 60))
# Memo of the single-row analysis state (version/dates/buyer_count), so the
# dashboard summary path knows which cached bundle to read without a per-request
# round trip to the remote database. Rewritten by a completed run.
RFM_ANALYSIS_STATE_MEMO_KEY = 'rfm:analysis:state_memo'
# Bumped when a K-Means clustering run persists new labels; part of the cached
# dashboard bundle key so a rerun is seen immediately.
RFM_KMEANS_EPOCH_KEY = 'rfm:kmeans:epoch'
# Bumped whenever an admin creates, edits, publishes, pauses or deletes a
# campaign. It is part of every per-customer offer cache key, so a campaign
# change is visible to customers on their very next request instead of after
# the short offer TTL has elapsed.
RFM_CAMPAIGN_EPOCH_KEY = 'rfm:campaigns:epoch'
# Bumped when a completed analysis publishes new segment labels. Together with
# the campaign epoch it keys the cached per-customer offer list, so a customer
# page can be served entirely from cache - no segment query at all - until
# either a campaign or the segmentation actually changes.
RFM_ANALYSIS_EPOCH_KEY = 'rfm:analysis:epoch'
# Memo of the single-row K-Means run state (RFM version, mapping, timestamps),
# so the dashboard can explain and age the stored labels without a per-request
# round trip to the remote database. Rewritten by every completed clustering run.
RFM_KMEANS_STATE_MEMO_KEY = 'rfm:kmeans:state_memo'
# Guard against two clustering runs overlapping on the same ~100k rows.
RFM_KMEANS_RUN_LOCK_KEY = 'rfm:kmeans:run_lock'
KMEANS_RUN_LOCK_TTL_SECONDS = int(os.getenv('RFM_KMEANS_RUN_LOCK_TTL_SECONDS', 15 * 60))
# Cooldown marker for the customer-side self-heal (a customer request may start
# a background analysis when none exists yet). Without it, traffic arriving while
# runs keep failing could repeatedly launch a full-population computation.
RFM_OFFER_SELF_HEAL_KEY = 'rfm:offers:self_heal'
OFFER_SELF_HEAL_COOLDOWN_SECONDS = int(
    os.getenv('RFM_OFFER_SELF_HEAL_COOLDOWN_SECONDS', 2 * 60)
)

# Snapshot TTL: long enough that dashboards read pure cache, short enough that
# a forgotten analysis still refreshes itself eventually.
SNAPSHOT_TTL_SECONDS = int(os.getenv('RFM_SNAPSHOT_TTL_SECONDS', 24 * 3600))
# The run lock must outlive a crashed worker thread at most by one analysis
# duration, never forever.
RUN_LOCK_TTL_SECONDS = int(os.getenv('RFM_RUN_LOCK_TTL_SECONDS', 15 * 60))
# Client-facing offer/eligibility lookups are cached briefly per analysis
# version; the version in the key makes stale reads impossible after a run.
OFFER_CACHE_TTL_SECONDS = int(os.getenv('RFM_OFFER_CACHE_TTL_SECONDS', 120))

# Background auto-refresh threshold. When an admin opens the analysis and the
# latest completed snapshot is older than this, a refresh is triggered in the
# background (guarded by the run lock) while the existing completed snapshot
# keeps being served - so the dashboard never shows partial or no data. Set to
# 0 to disable automatic refresh entirely.
RFM_REFRESH_AFTER_SECONDS = int(os.getenv('RFM_REFRESH_AFTER_SECONDS', 3 * 3600))

SNAPSHOT_VERSION_MIN = 1

# Segment vocabulary of the *previous* rule-based segmentation. It is no longer
# offered when authoring a campaign - the Campaign page now targets the four
# K-Means clusters below - but it must keep resolving exactly as before for the
# campaigns, coupons and redemption rows that were published against it, and for
# the CLV segment reads that still use the persisted `segment` column.
# ---------------------------------------------------------------------------
SEGMENT_CHAMPIONS = 'Champions'
SEGMENT_LOYAL = 'Loyal Customers'
SEGMENT_POTENTIAL_LOYALISTS = 'Potential Loyalists'
SEGMENT_NEW = 'New Customers'
SEGMENT_AT_RISK = 'At-Risk'
SEGMENT_HIBERNATING = 'Hibernating'
SEGMENT_NEVER_PURCHASED = 'Never Purchased'

TAG_BIG_SPENDER = 'Big Spender'

# Whether campaigns authored on the *previous* rule-based segments may still
# reach a customer. Personalised coupons are now chosen from the four K-Means
# clusters, and a customer must see only the offer of the group they belong to,
# so a legacy segment campaign no longer becomes visible or redeemable.
#
# This gates visibility only. Nothing is deleted or reinterpreted: the campaign
# rows, their issued coupons and every redemption record stay exactly as they
# are, the admin list still shows them (marked "Previous RFM segmentation"), and
# setting RFM_LEGACY_CAMPAIGNS_VISIBLE_TO_CUSTOMERS=1 restores the old behaviour
# without a code change or a migration.
LEGACY_CAMPAIGNS_VISIBLE_TO_CUSTOMERS = (
    os.getenv('RFM_LEGACY_CAMPAIGNS_VISIBLE_TO_CUSTOMERS', '0').strip() == '1'
)

# Every eligible buyer is assigned to one of these six primary segments (see
# segmentation._fallback_classify for the residual mapping). There is no longer
# an "Others" segment.
PRIMARY_SEGMENTS = [
    SEGMENT_CHAMPIONS,
    SEGMENT_LOYAL,
    SEGMENT_POTENTIAL_LOYALISTS,
    SEGMENT_NEW,
    SEGMENT_AT_RISK,
    SEGMENT_HIBERNATING,
]

ALL_SEGMENTS = PRIMARY_SEGMENTS + [SEGMENT_NEVER_PURCHASED]

SECONDARY_TAGS = [TAG_BIG_SPENDER]


# ---------------------------------------------------------------------------
# K-Means++ clustering vocabulary (labels only - the algorithm lives in
# `clustering.py`). These four business categories are the label a numeric
# K-Means cluster is mapped to *after* clustering, from the cluster's unscaled
# RFM profile. They are separate from the six rule-based segments above: CLV
# still reads the RFM metrics only, and campaign targeting now selects its
# audience from these four clusters (`cluster_targeting.py`) instead of the
# rule-based segments, which stay in place only for historical campaigns.
#
# The four categories are spending / frequency / dormancy descriptions, chosen
# so the label is always backed by the cluster's real RFM numbers. They are NOT
# tied to a fixed cluster id: which id carries which label is re-derived from
# the profiles on every run (see `clustering.map_clusters_to_categories`).
# ---------------------------------------------------------------------------
KMEANS_N_CLUSTERS = int(os.getenv('RFM_KMEANS_N_CLUSTERS', 4))
KMEANS_RANDOM_STATE = int(os.getenv('RFM_KMEANS_RANDOM_STATE', 42))
KMEANS_N_INIT = int(os.getenv('RFM_KMEANS_N_INIT', 10))

KMEANS_CATEGORY_MODERATE_SPENDING = 'Moderate Spending'
KMEANS_CATEGORY_HIGH_SPENDING = 'High Spending'
KMEANS_CATEGORY_AT_RISK = 'At Risk'
KMEANS_CATEGORY_FREQUENT_BUYERS = 'Frequent Buyers'

# Order is display order, not priority; every entry is one of the four labels
# the four clusters are mapped onto.
KMEANS_CATEGORIES = [
    KMEANS_CATEGORY_MODERATE_SPENDING,
    KMEANS_CATEGORY_HIGH_SPENDING,
    KMEANS_CATEGORY_AT_RISK,
    KMEANS_CATEGORY_FREQUENT_BUYERS,
]


def snapshot_meta_key(version):
    return RFM_SNAPSHOT_META_KEY.format(version=version)


def snapshot_records_key(version):
    return RFM_SNAPSHOT_RECORDS_KEY.format(version=version)


def utcnow():
    from django.utils import timezone
    return timezone.now()
