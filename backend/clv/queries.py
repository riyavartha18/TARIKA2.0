"""Efficient, parameterized PostgreSQL reads for the CLV module.

One grouped statement over `public.orders` reduces the ~1M-row history to one
row per eligible buyer (~100k), aggregating entirely server-side over the
partial index created for RFM (`orders (customer_id) INCLUDE (final_price,
purchase_date) WHERE delivery_status='Delivered'`). Nothing is loaded
order-by-order into application memory, and one row is one order (`orderid`
is the primary key), so COUNT(*) is the distinct order count by construction.

The per-buyer purchase-year array lets the cohort matrix be derived from the
same single round trip. First/last purchase dates and lifetime order counts
are deliberately NOT stored anywhere - the orders table is their only source.
"""

from django.db import connection

from rfm_analysis.models import CustomerSegment, RfmAnalysisState

from . import utils


# One row per eligible buyer with everything the CLV pipeline needs. The
# eligibility filters are the exact RFM ones (same revenue definition), and
# `purchase_date` is parsed from its stored 'DD-MM-YYYY' text form (verified:
# every stored date matches that pattern, so a NOT NULL guard suffices).
BUYER_CLV_BASE_SQL = """
WITH eligible AS (
    SELECT
        o.customer_id,
        o.final_price,
        to_date(o.purchase_date, 'DD-MM-YYYY') AS pdate
    FROM public.orders o
    WHERE o.delivery_status = ANY(%s)
      AND o.customer_id IS NOT NULL
      AND o.purchase_date IS NOT NULL
      AND (%s OR o.final_price >= 0)
),
bounds AS (
    SELECT GREATEST(
        CURRENT_DATE,
        COALESCE((SELECT MAX(pdate) FROM eligible), CURRENT_DATE)
    ) AS cutoff_date
),
per_customer AS (
    SELECT
        e.customer_id,
        COUNT(*)::bigint                          AS order_count,
        SUM(e.final_price)                        AS revenue,
        MIN(e.pdate)                              AS first_purchase_date,
        MAX(e.pdate)                              AS last_purchase_date,
        ARRAY_AGG(DISTINCT EXTRACT(YEAR FROM e.pdate)::int) AS purchase_years
    FROM eligible e
    GROUP BY e.customer_id
)
SELECT
    pc.customer_id,
    cu.customer_name                              AS customer_name,
    pc.order_count::int                           AS order_count,
    ROUND(pc.revenue::numeric, 2)                 AS revenue,
    pc.first_purchase_date::text                  AS first_purchase_date,
    pc.last_purchase_date::text                   AS last_purchase_date,
    pc.purchase_years                             AS purchase_years,
    b.cutoff_date::text                           AS cutoff_date
FROM per_customer pc
CROSS JOIN bounds b
LEFT JOIN public.customers cu ON cu.customer_id = pc.customer_id
"""


def fetch_buyer_clv_rows():
    """Return (rows, cutoff_date_iso), one lightweight dict per eligible buyer."""
    statuses = utils.eligible_delivery_statuses()
    exclude_negative = utils.exclude_negative_final_price()

    with connection.cursor() as cursor:
        cursor.execute(BUYER_CLV_BASE_SQL, [statuses, exclude_negative])
        columns = [col.name for col in cursor.description]
        raw = cursor.fetchall()

    rows = [dict(zip(columns, record)) for record in raw]
    cutoff = rows[0]['cutoff_date'] if rows else None
    return rows, cutoff


def fetch_stored_rfm_metrics():
    """Reusable customer-level metrics persisted by the latest completed RFM run.

    Returns (rfm_version, {customer_id: {'segment', 'monetary'}}); (None, {})
    when no analysis has ever completed. The result table is the authoritative
    "latest state per customer" store, so it is read in full rather than filtered
    by version: an incremental refresh only rewrites buyers whose values actually
    changed (leaving unchanged buyers on an older per-row version), and every row
    still represents that customer's latest result.

    `monetary` is None for rows stored before Monetary persistence existed - the
    caller then falls back to the live revenue from the orders table (never a
    duplicate stored metric).
    """
    state = RfmAnalysisState.objects.filter(pk=RfmAnalysisState.SINGLETON_ID).first()
    if state is None:
        return None, {}
    stored = {}
    rows = CustomerSegment.objects.values_list(
        'customer_id', 'segment', 'monetary')
    # A plain (materialized) read, not .iterator(): Neon's transaction
    # pooler drops server-side named cursors, and ~100k tiny tuples is
    # exactly the population the RFM snapshot already keeps in memory.
    for customer_id, segment, monetary in rows:
        stored[customer_id] = {
            'segment': segment,
            'monetary': float(monetary) if monetary is not None else None,
        }
    return state.version, stored


def fetch_stored_rfm_base():
    """The whole CLV customer base straight from the persisted RFM result table.

    This is what removes the 1M-row order scan from the CLV page: Historical CLV
    (Monetary), order count (Frequency), the RFM segment, and the first/last
    valid purchase date are all already stored per buyer by the completed RFM
    run, using the exact eligibility definition CLV needs. Cohort retention is
    the one thing this cannot supply (it needs the set of purchase *years*), so
    it is computed separately with `fetch_cohort_matrix`.

    Returns (rfm_version, cutoff_date, rows) where each row is a small dict.
    `cutoff_date` is the RFM analysis date (the reporting cutoff). Returns
    (None, None, []) when no analysis has completed - the caller then falls back
    to a live order aggregate so CLV still works before the first RFM run.
    """
    state = RfmAnalysisState.objects.filter(pk=RfmAnalysisState.SINGLETON_ID).first()
    if state is None:
        return None, None, []
    rows = []
    for (customer_id, segment, monetary, frequency,
         first_date, last_date) in CustomerSegment.objects.values_list(
            'customer_id', 'segment', 'monetary', 'frequency',
            'first_purchase_date', 'last_purchase_date'):
        rows.append({
            'customer_id': customer_id,
            'segment': segment,
            'monetary': float(monetary) if monetary is not None else None,
            'order_count': int(frequency) if frequency is not None else 0,
            'first_purchase_date': first_date,
            'last_purchase_date': last_date,
        })
    cutoff = state.analysis_date
    if cutoff is None and rows:
        dates = [r['last_purchase_date'] for r in rows if r['last_purchase_date']]
        cutoff = max(dates) if dates else None
    return state.version, cutoff, rows


# Cohort survival computed ENTIRELY server-side into a tiny histogram (one row
# per cohort-month x last-purchase-month, a few hundred rows at most). It scans
# the eligible orders once and never streams the ~100k per-buyer rows the old
# `fetch_buyer_clv_rows` did. Each buyer contributes their first and last valid
# purchase MONTH; `clv.calc.retention_report` derives cohort sizes, mature
# observation windows and the pooled survival curve from that histogram, so
# the maturity rule has one source in Python.
COHORT_AGGREGATE_SQL = """
WITH eligible AS (
    SELECT o.customer_id,
           to_date(o.purchase_date, 'DD-MM-YYYY') AS pdate
    FROM public.orders o
    WHERE o.delivery_status = ANY(%s)
      AND o.customer_id IS NOT NULL
      AND o.purchase_date IS NOT NULL
      AND (%s OR o.final_price >= 0)
),
spans AS (
    SELECT customer_id,
           EXTRACT(YEAR FROM MIN(pdate))::int * 12
             + EXTRACT(MONTH FROM MIN(pdate))::int AS cohort_period,
           EXTRACT(YEAR FROM MAX(pdate))::int * 12
             + EXTRACT(MONTH FROM MAX(pdate))::int AS last_period,
           MAX(pdate) AS last_date
    FROM eligible
    GROUP BY customer_id
)
SELECT cohort_period, last_period, COUNT(*) AS n, MAX(last_date)::text AS max_last
FROM spans
GROUP BY cohort_period, last_period
"""


def fetch_cohort_matrix():
    """{'cells': {(cohort_month, last_month): buyers}, 'horizon_period', 'horizon_date'}.

    PostgreSQL-only (uses the unmanaged `public.orders` table); on a backend
    without it (the SQLite test DB) returns {} so callers fall back to the
    per-buyer cohort derivation in `clv.calc.build_cohort_matrix`.
    """
    if connection.vendor != 'postgresql':
        return {}
    statuses = utils.eligible_delivery_statuses()
    exclude_negative = utils.exclude_negative_final_price()
    cells = {}
    horizon_period = None
    horizon_date = None
    with connection.cursor() as cursor:
        cursor.execute(COHORT_AGGREGATE_SQL, [statuses, exclude_negative])
        for cohort, last, n, max_last in cursor.fetchall():
            cells[(int(cohort), int(last))] = int(n)
            if horizon_period is None or int(last) > horizon_period:
                horizon_period = int(last)
                horizon_date = max_last
    return {'cells': cells,
            'horizon_period': horizon_period,
            'horizon_date': horizon_date}


# ---------------------------------------------------------------------------
# SQL-first CLV aggregation over the persisted RFM result table.
#
# Historical CLV is exactly the stored RFM Monetary, and order count is the
# stored Frequency, so the summary, value tiers, segment analysis AND the
# per-customer Future CLV (a step function of the pooled survival curve over
# the stored columns - see `clv.calc.future_clv_sql`) are pure aggregates over
# the ~100k-row result table. They return a handful of rows, so a dashboard
# load never transfers the population into application memory (the single
# biggest change behind the CLV cold-start speed-up).
# ---------------------------------------------------------------------------
CLV_AGGREGATE_SQL = """
WITH scored AS (
    SELECT monetary, segment, ({future}) AS future_clv
    FROM rfm_customer_segments
)
SELECT
    COUNT(*)                                                   AS buyer_count,
    COALESCE(SUM(monetary), 0)                                 AS total_revenue,
    COALESCE(AVG(monetary), 0)                                 AS avg_historical_clv,
    percentile_cont(%s) WITHIN GROUP (ORDER BY monetary)       AS high_value,
    percentile_cont(%s) WITHIN GROUP (ORDER BY monetary)       AS medium_value,
    COUNT(*) FILTER (WHERE segment = %s)                       AS at_risk_count,
    COUNT(*) FILTER (WHERE future_clv IS NOT NULL)             AS future_supported_count,
    AVG(future_clv)                                            AS avg_future_clv,
    AVG(CASE WHEN future_clv IS NOT NULL
             THEN monetary + future_clv END)                   AS avg_total_clv
FROM scored
"""


def fetch_clv_aggregates(future_sql=None):
    """Population totals + percentiles + At-Risk + Future-CLV stats in one pass.

    `future_sql` is the placeholder-free expression from
    `clv.calc.future_clv_sql` (None when the survival curve is not usable
    yet). Returns None when there are no persisted results (no completed RFM
    run).
    """
    if connection.vendor != 'postgresql':
        return None
    from . import utils as _u
    sql = CLV_AGGREGATE_SQL.replace('{future}', future_sql or 'NULL::numeric')
    with connection.cursor() as cursor:
        cursor.execute(sql, [
            _u.CLV_HIGH_PERCENTILE / 100.0,
            _u.CLV_MEDIUM_PERCENTILE / 100.0,
            rfm_segment_at_risk_label(),
        ])
        row = cursor.fetchone()
    if not row or not row[0]:
        return None
    (buyer_count, total_revenue, avg_historical_clv,
     high_value, medium_value, at_risk_count,
     future_supported_count, avg_future_clv, avg_total_clv) = row
    return {
        'buyer_count': int(buyer_count),
        'total_revenue': round(float(total_revenue), 2),
        'avg_historical_clv': round(float(avg_historical_clv), 2),
        'high_value': round(float(high_value), 2) if high_value is not None else None,
        'medium_value': round(float(medium_value), 2) if medium_value is not None else None,
        'at_risk_count': int(at_risk_count),
        'future_supported_count': int(future_supported_count or 0),
        'avg_future_clv': (round(float(avg_future_clv), 2)
                           if avg_future_clv is not None else None),
        'avg_total_clv': (round(float(avg_total_clv), 2)
                          if avg_total_clv is not None else None),
    }


def rfm_segment_at_risk_label():
    from rfm_analysis import utils as rfm_utils
    return rfm_utils.SEGMENT_AT_RISK


CLV_TIER_COUNTS_SQL = """
SELECT
    COUNT(*) FILTER (WHERE monetary >= %s) AS high,
    COUNT(*) FILTER (WHERE monetary >= %s AND monetary < %s) AS medium,
    COUNT(*) FILTER (WHERE monetary < %s) AS low
FROM rfm_customer_segments
"""


def fetch_tier_counts(high_value, medium_value):
    """High / Medium / Low customer counts against the percentile boundaries."""
    if connection.vendor != 'postgresql' or high_value is None:
        return None
    with connection.cursor() as cursor:
        cursor.execute(CLV_TIER_COUNTS_SQL,
                       [high_value, medium_value, high_value, medium_value])
        high, medium, low = cursor.fetchone()
    return {'High Value': int(high), 'Medium Value': int(medium),
            'Low Value': int(low)}


CLV_SEGMENT_ANALYSIS_SQL = """
WITH scored AS (
    SELECT COALESCE(segment, 'Unsegmented') AS segment,
           monetary, frequency, ({future}) AS future_clv
    FROM rfm_customer_segments
)
SELECT
    segment,
    COUNT(*)                            AS customer_count,
    COALESCE(AVG(monetary), 0)          AS avg_historical_clv,
    COALESCE(SUM(monetary), 0)          AS total_historical_clv,
    COALESCE(AVG(frequency), 0)         AS avg_orders,
    AVG(future_clv)                     AS avg_future_clv
FROM scored
GROUP BY segment
ORDER BY COALESCE(SUM(monetary), 0) DESC
"""


def fetch_segment_analysis(future_sql=None):
    """Per-RFM-segment value analysis (grouped aggregate over the result table)."""
    if connection.vendor != 'postgresql':
        return None
    sql = CLV_SEGMENT_ANALYSIS_SQL.replace('{future}', future_sql or 'NULL::numeric')
    rows = []
    with connection.cursor() as cursor:
        cursor.execute(sql)
        for (segment, count, avg_h, total_h, avg_orders,
             avg_future) in cursor.fetchall():
            rows.append({
                'segment': segment,
                'customer_count': int(count),
                'avg_historical_clv': round(float(avg_h), 2),
                'total_historical_clv': round(float(total_h), 2),
                'avg_orders': round(float(avg_orders), 2),
                'avg_future_clv': (round(float(avg_future), 2)
                                   if avg_future is not None else None),
            })
    return rows


# One page of customer CLV rows, read straight from the persisted result
# table. Only ~25 rows cross the network and the customers table is touched
# ONLY when the query genuinely needs names (name search / name sort), so the
# common page load is two small indexed reads instead of a 100k-row join.
# Filtering, sorting and the Future-CLV range/availability predicates all run
# in SQL over the full dataset (never just the current page).
def fetch_customer_page(segment=None, tier=None, search='', order_by='monetary',
                        direction='desc', limit=25, offset=0,
                        future_sql=None, future_min=None, future_max=None,
                        future_state=None):
    """(rows, total) for one paginated, filtered, sorted CLV customer page.

    `future_sql` is the placeholder-free per-customer Future CLV expression
    (`clv.calc.future_clv_sql`); it powers the Future-CLV range/availability
    filters and the Future-CLV sort. Returns ([], 0) on a backend without the
    result table.
    """
    if connection.vendor != 'postgresql':
        return [], 0

    where = []
    params = []
    if segment and segment != 'ALL':
        where.append('cs.segment = %s')
        params.append(segment)
    if search:
        # Name membership is an EXISTS probe (driven by the outer row's PK),
        # so the base query never fans out into a population-sized join.
        where.append("(cs.customer_id ILIKE %s OR EXISTS (SELECT 1 FROM public.customers cu"
                     " WHERE cu.customer_id = cs.customer_id AND cu.customer_name ILIKE %s))")
        params.extend([f'%{search}%', f'%{search}%'])
    clause, extra = _tier_clause(tier, alias='cs.')
    if clause:
        where.append(clause)
        params.extend(extra)
    if future_sql:
        if future_state == 'available':
            where.append(f'({future_sql}) IS NOT NULL')
        elif future_state == 'insufficient':
            where.append(f'({future_sql}) IS NULL')
        if future_min is not None:
            where.append(f'({future_sql}) >= %s')
            params.append(future_min)
        if future_max is not None:
            where.append(f'({future_sql}) <= %s')
            params.append(future_max)
    where_sql = ('WHERE ' + ' AND '.join(where)) if where else ''

    col = {'customer_id': 'cs.customer_id', 'monetary': 'cs.monetary',
           'historical_clv': 'cs.monetary', 'clv_tier': 'cs.monetary',
           'order_count': 'cs.frequency', 'frequency': 'cs.frequency',
           'future_clv': future_sql}.get(order_by, 'cs.monetary')
    if order_by == 'future_clv' and not col:
        col = 'cs.monetary'
    direction_sql = 'DESC' if direction == 'desc' else 'ASC'

    cols = ('cs.customer_id, cs.segment, cs.monetary, cs.frequency, '
            'cs.first_purchase_date::text, cs.last_purchase_date::text')
    # One statement per page: COUNT(*) OVER() carries the filtered total, and
    # the customers table is joined either inside (name sort) or against the
    # 25 already-limited rows (plain name lookup) - never across the whole
    # population.
    if order_by == 'customer_name':
        inner = (
            f'SELECT {cols}, COALESCE(cu.customer_name, \'\') AS customer_name, '
            'COUNT(*) OVER () AS total_count '
            'FROM rfm_customer_segments cs '
            'LEFT JOIN public.customers cu ON cu.customer_id = cs.customer_id '
            f'{where_sql} '
            f'ORDER BY COALESCE(cu.customer_name, \'\') {direction_sql} NULLS LAST, '
            'cs.customer_id ASC LIMIT %s OFFSET %s'
        )
        sql = f'SELECT * FROM ({inner}) p'
    else:
        inner = (
            f'SELECT {cols}, COUNT(*) OVER () AS total_count '
            f'FROM rfm_customer_segments cs {where_sql} '
            f'ORDER BY {col} {direction_sql} NULLS LAST, cs.customer_id ASC '
            'LIMIT %s OFFSET %s'
        )
        sql = ('SELECT p.*, cu.customer_name '
               f'FROM ({inner}) p '
               'LEFT JOIN public.customers cu ON cu.customer_id = p.customer_id')

    with connection.cursor() as cursor:
        cursor.execute(sql, params + [limit, offset])
        columns = [c.name for c in cursor.description]
        rows = [dict(zip(columns, record)) for record in cursor.fetchall()]
    total = int(rows[0]['total_count']) if rows else 0
    for row in rows:
        row.pop('total_count', None)
    return rows, total


def _tier_clause(tier, alias=''):
    """Translate a value tier into a monetary predicate using the boundaries
    published by `set_tier_boundaries` (empty when unknown)."""
    bounds = _TIER_BOUNDS
    if not tier or tier == 'ALL' or not bounds:
        return '', []
    high, medium = bounds['high'], bounds['medium']
    monetary = f'{alias}monetary'
    if tier == 'High Value':
        return f'{monetary} >= %s', [high]
    if tier == 'Medium Value':
        return f'{monetary} >= %s AND {monetary} < %s', [medium, high]
    if tier == 'Low Value':
        return f'{monetary} < %s', [medium]
    return '', []


_TIER_BOUNDS = {}


def set_tier_boundaries(high_value, medium_value):
    """Publish the percentile boundaries for tier-filtered pagination."""
    global _TIER_BOUNDS
    _TIER_BOUNDS = {'high': high_value, 'medium': medium_value}


# ---------------------------------------------------------------------------
# Fallback path (used only before any RFM analysis has persisted a result).
# ---------------------------------------------------------------------------
def fetch_buyer_clv_rows_via_orders():
    """Legacy per-buyer order aggregate; retained as the no-RFM-yet fallback."""
    return fetch_buyer_clv_rows()


# Cheap single-buyer aggregate for the customer detail view when no built CLV
# state exists yet: never recomputes the population, only this buyer's rows.
SINGLE_CUSTOMER_CLV_SQL = """
WITH eligible AS (
    SELECT
        o.final_price,
        to_date(o.purchase_date, 'DD-MM-YYYY') AS pdate
    FROM public.orders o
    WHERE o.customer_id = %s
      AND o.delivery_status = ANY(%s)
      AND o.purchase_date IS NOT NULL
      AND (%s OR o.final_price >= 0)
),
bounds AS (
    SELECT GREATEST(
        CURRENT_DATE,
        COALESCE((SELECT MAX(to_date(purchase_date, 'DD-MM-YYYY'))
                  FROM public.orders
                  WHERE purchase_date IS NOT NULL),
                 CURRENT_DATE)
    ) AS cutoff_date
)
SELECT
    COUNT(*)::int                                AS order_count,
    ROUND(COALESCE(SUM(e.final_price), 0)::numeric, 2) AS revenue,
    MIN(e.pdate)::text                           AS first_purchase_date,
    MAX(e.pdate)::text                           AS last_purchase_date,
    (SELECT b.cutoff_date)::text                 AS cutoff_date
FROM eligible e
"""


def fetch_single_customer_metrics(customer_id):
    """Live eligible metrics for one buyer, or None when they have no orders."""
    statuses = utils.eligible_delivery_statuses()
    exclude_negative = utils.exclude_negative_final_price()
    with connection.cursor() as cursor:
        cursor.execute(
            SINGLE_CUSTOMER_CLV_SQL, [customer_id, statuses, exclude_negative]
        )
        columns = [col.name for col in cursor.description]
        record = cursor.fetchone()
    if record is None:
        return None
    row = dict(zip(columns, record))
    if not row['order_count']:
        return None
    return row
