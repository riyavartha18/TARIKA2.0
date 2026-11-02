"""CLV business configuration in one place (mirrors rfm_analysis.utils).

Every threshold, cache key and calculation policy lives here so the formulas
can be reviewed and tuned without touching the logic. All values may be
overridden through environment variables.

Documented calculation rules
----------------------------
* Valid order / revenue definition: shared with RFM (see `rfm_analysis.utils`)
  - exactly `Delivered` orders with a non-negative `final_price`. One order is
  one row (`orderid` is the primary key), so COUNT(*) is the distinct order
  count and no join duplication is possible.
* Historical CLV = the customer's valid lifetime revenue - the stored RFM
  Monetary value when available, otherwise the same live aggregate.
* AOV = historical revenue / valid distinct order count (0 orders -> 0).
* Tenure = reporting cutoff date - first valid purchase date. The cutoff is
  the greater of "today" and the latest valid purchase date, identical to the
  RFM analysis date rule, so future-dated rows never produce a negative value.
* Annual purchase frequency = valid orders / tenure in years, floored at
  MIN_TENURE_YEARS (default 30 days): a brand-new customer with one first
  order is not extrapolated to a fictional 365 purchases a year.
* High / Medium / Low tiers are percentile bands of the *calculated historical
  CLV* across all buyers (average-rank percentiles, same method as RFM
  scoring): High >= P70, Medium >= P30, else Low. No fixed rupee threshold.
* At Risk is not a fourth CLV tier: it is the existing RFM At-Risk segment
  shown as an engagement overlay on the same dashboard (counts overlap with
  the three value tiers by design; the API reports both separately).
* Future CLV requires a cohort-derived survival estimate measured in calendar
  MONTHS from each buyer's first valid purchase to their last one (a ~2-year
  order history can never complete two *yearly* cohort ages, so yearly periods
  made the estimate mathematically impossible on this dataset). A survival age
  counts only while its observation month lies inside the data horizon (the
  latest valid purchase date), and at least MIN_MATURE_RETENTION_AGES distinct
  mature ages must exist - otherwise the status is 'insufficient_data' and no
  lifespan, future CLV or multiplier is invented. Buyers who have already
  surpassed the oldest observed age have no evidence to project on and are
  reported without a Future CLV (never a zero).
"""

import os

from rfm_analysis import utils as rfm_utils  # single source of eligibility


# ---------------------------------------------------------------------------
# Order eligibility - shared verbatim with RFM (verified Neon schema:
# delivery_status is only ever 'Delivered' / 'In Transit' / 'Returned' / NULL,
# and negative final_price rows are data corruption, not refunds).
# ---------------------------------------------------------------------------
def eligible_delivery_statuses():
    return rfm_utils.eligible_delivery_statuses()


def exclude_negative_final_price():
    return rfm_utils.EXCLUDE_NEGATIVE_FINAL_PRICE


# Days per year used by every tenure/frequency conversion.
DAYS_PER_YEAR = 365.25

# Minimum tenure (years) used when annualizing purchase frequency. Customers
# with a shorter observed history are stabilized instead of extrapolated.
MIN_TENURE_YEARS = (
    float(os.getenv('CLV_MIN_TENURE_DAYS', 30)) / DAYS_PER_YEAR
)

# Percentile bands for the value tiers (reproducible, data-driven).
CLV_HIGH_PERCENTILE = float(os.getenv('CLV_HIGH_PERCENTILE', 70))
CLV_MEDIUM_PERCENTILE = float(os.getenv('CLV_MEDIUM_PERCENTILE', 30))

# Future CLV is only reported when the cohort history provides at least this
# many distinct mature retention AGES (in calendar months - the documented
# survival requirement; the ~2-year Neon history yields ~24 mature ages).
MIN_MATURE_RETENTION_AGES = int(os.getenv('CLV_MIN_MATURE_RETENTION_AGES', 2))

# Tier vocabulary (labels only - the numeric bands are the percentiles above).
TIER_HIGH = 'High Value'
TIER_MEDIUM = 'Medium Value'
TIER_LOW = 'Low Value'
VALUE_TIERS = [TIER_HIGH, TIER_MEDIUM, TIER_LOW]

# Future-CLV calculation statuses.
STATUS_OK = 'ok'
STATUS_INSUFFICIENT_DATA = 'insufficient_data'
INSUFFICIENT_DATA_MESSAGE = 'Insufficient historical data'

# ---------------------------------------------------------------------------
# Cache strategy: CLV results are NEVER persisted to the database. A built
# state is a versioned snapshot in the shared Django cache (same pattern as
# the RFM snapshot), keyed by the stored RFM analysis version plus a manual
# rebuild epoch, so a new completed RFM run or a POST /api/clv/recalculate
# makes the old snapshot unreachable instead of serving stale numbers.
# ---------------------------------------------------------------------------
CLV_STATE_POINTER_KEY = 'clv:analysis:latest'
CLV_STATE_META_KEY = 'clv:analysis:state:meta:{token}'
CLV_STATE_RECORDS_KEY = 'clv:analysis:state:records:{token}'
CLV_BUILD_EPOCH_KEY = 'clv:analysis:build_epoch'
CLV_RUN_STATUS_KEY = 'clv:analysis:run_status'
CLV_RUN_LOCK_KEY = 'clv:analysis:run_lock'
# Short-lived memo of the persisted RFM version (one remote state query saved
# per read burst) - dropped explicitly when an RFM run stores new results.
CLV_STORED_RFM_VERSION_KEY = 'clv:analysis:stored_rfm_version'
STORED_RFM_VERSION_TTL_SECONDS = int(os.getenv('CLV_RFM_VERSION_TTL_SECONDS', 20))
# Snapshot-keyed read caches: every part of a published snapshot's token dies
# with the snapshot itself, so pages/details are served without re-querying
# Neon while the analysis version is unchanged.
CLV_PAGE_CACHE_KEY = 'clv:customers:page:{key}'
CLV_DETAIL_CACHE_KEY = 'clv:customers:detail:{token}:{customer_id}'
READ_CACHE_TTL_SECONDS = int(os.getenv('CLV_READ_CACHE_TTL_SECONDS', 5 * 60))

STATE_TTL_SECONDS = int(os.getenv('CLV_STATE_TTL_SECONDS', 60 * 60))
RUN_LOCK_TTL_SECONDS = int(os.getenv('CLV_RUN_LOCK_TTL_SECONDS', 10 * 60))

# Snapshot of the cohort matrix (one row per buyer) is bounded by the buyer
# population, so ~100k compact dicts is the same order of magnitude the RFM
# snapshot already keeps in cache.
RECORD_PROJECTION = (
    'customer_id', 'customer_name', 'historical_clv', 'future_clv',
    'total_clv', 'aov', 'order_count', 'first_purchase_date',
    'last_purchase_date', 'tenure_days', 'annual_frequency',
    'rfm_segment', 'clv_tier',
)


def state_meta_key(token):
    return CLV_STATE_META_KEY.format(token=token)


def state_records_key(token):
    return CLV_STATE_RECORDS_KEY.format(token=token)


def page_cache_key(raw_key):
    """Hash the composite page key: short and safe for every cache backend."""
    import hashlib
    digest = hashlib.sha1(raw_key.encode('utf-8')).hexdigest()
    return CLV_PAGE_CACHE_KEY.format(key=digest)


def detail_cache_key(token, customer_id):
    return CLV_DETAIL_CACHE_KEY.format(token=token, customer_id=customer_id)


def utcnow():
    from django.utils import timezone
    return timezone.now()
