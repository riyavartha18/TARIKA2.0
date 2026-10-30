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

# ---------------------------------------------------------------------------
# Segment vocabulary (labels only - the numeric rules are in segmentation.py)
# ---------------------------------------------------------------------------
SEGMENT_CHAMPIONS = 'Champions'
SEGMENT_LOYAL = 'Loyal Customers'
SEGMENT_POTENTIAL_LOYALISTS = 'Potential Loyalists'
SEGMENT_NEW = 'New Customers'
SEGMENT_AT_RISK = 'At-Risk'
SEGMENT_HIBERNATING = 'Hibernating'
SEGMENT_NEVER_PURCHASED = 'Never Purchased'

TAG_BIG_SPENDER = 'Big Spender'

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


def snapshot_meta_key(version):
    return RFM_SNAPSHOT_META_KEY.format(version=version)


def snapshot_records_key(version):
    return RFM_SNAPSHOT_RECORDS_KEY.format(version=version)


def utcnow():
    from django.utils import timezone
    return timezone.now()
