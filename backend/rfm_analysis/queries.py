"""Efficient, parameterized PostgreSQL reads for the RFM engine.

Everything is aggregated server-side in one grouped statement over
`public.orders` (verified schema: one product per order, `orderid` is the
primary key, `final_price` is the amount actually paid for that order). There
is therefore no order/line duplication to guard against - one row is one
order - and Frequency counts distinct `orderid` values directly.

Only eligible completed purchases feed the metrics. The eligibility filters
mirror `utils.eligible_delivery_statuses` and the negative-price policy, and
`purchase_date` is parsed from its stored 'DD-MM-YYYY' text form.
"""

from django.db import connection

from . import utils


# Aggregates one row per eligible buyer. Recency is measured against the
# analysis date (the greater of the DB's current date and the latest purchase
# date, so future-dated rows can never yield a negative Recency).
BUYER_METRICS_SQL = """
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
    ) AS analysis_date
),
per_customer AS (
    SELECT
        e.customer_id,
        MAX(e.pdate)                  AS last_purchase_date,
        MIN(e.pdate)                  AS first_purchase_date,
        -- orderid is the primary key and one row is one order, so COUNT(*) is
        -- exactly the distinct-order Frequency the rules require, without the
        -- cost of a distinct hash over ~590k eligible rows.
        COUNT(*)::bigint              AS frequency,
        COUNT(*)::bigint              AS lifetime_orders,
        SUM(e.final_price)            AS monetary
    FROM eligible e
    GROUP BY e.customer_id
)
SELECT
    pc.customer_id,
    cu.customer_name                        AS customer_name,
    pc.frequency::int                 AS frequency,
    ROUND(pc.monetary::numeric, 2)    AS monetary,
    (b.analysis_date - pc.last_purchase_date)::int AS recency_days,
    pc.last_purchase_date::text       AS last_purchase_date,
    pc.first_purchase_date::text      AS first_purchase_date,
    b.analysis_date::text             AS analysis_date
FROM per_customer pc
CROSS JOIN bounds b
LEFT JOIN public.customers cu ON cu.customer_id = pc.customer_id
"""


def fetch_buyer_metrics():
    """Return (rows, analysis_date_iso).

    `rows` is a list of lightweight dicts, one per eligible buyer. The heavy
    grouping happens entirely inside PostgreSQL; this call streams the reduced
    per-customer result (~one row per buyer) rather than the raw order table.

    The `purchase_date` validity filter was verified against the live data -
    every stored date already matches 'DD-MM-YYYY' - so only a cheap NOT NULL
    guard remains here; a partial covering index on delivered orders (see
    `migrations`) makes this a single index-only scan.
    """
    statuses = utils.eligible_delivery_statuses()
    exclude_negative = utils.EXCLUDE_NEGATIVE_FINAL_PRICE

    with connection.cursor() as cursor:
        cursor.execute(BUYER_METRICS_SQL, [statuses, exclude_negative])
        columns = [col.name for col in cursor.description]
        raw = cursor.fetchall()

    rows = [dict(zip(columns, record)) for record in raw]
    analysis_date = rows[0]['analysis_date'] if rows else None
    return rows, analysis_date


AGGREGATE_TOTALS_SQL = """
SELECT
    (SELECT COUNT(*) FROM public.customers) AS total_customers
"""


def fetch_total_customers():
    """The one count that is not derivable from the buyer metrics.

    Every other dashboard total (buyers, eligible orders, eligible revenue,
    Never Purchased) is computed from the already-fetched per-customer metrics
    in `engine`, so this is the only aggregate that needs a database round-trip
    and it is a cheap primary-key count on `customers`.
    """
    with connection.cursor() as cursor:
        cursor.execute(AGGREGATE_TOTALS_SQL)
        return int(cursor.fetchone()[0] or 0)


NEVER_PURCHASED_SQL = """
SELECT cu.customer_id, cu.customer_name
FROM public.customers cu
WHERE NOT EXISTS (
    SELECT 1 FROM public.orders o
    WHERE o.customer_id = cu.customer_id
      AND o.delivery_status = ANY(%s)
      AND (%s OR o.final_price >= 0)
)
ORDER BY cu.customer_id
LIMIT %s OFFSET %s
"""


def fetch_never_purchased_page(page_size, offset):
    """One server-side page of customers with no eligible purchase.

    Never Purchased customers carry no RFM metrics by definition, so their
    detail list is read straight from `customers` on demand instead of being
    materialised into the snapshot.
    """
    statuses = utils.eligible_delivery_statuses()
    exclude_negative = utils.EXCLUDE_NEGATIVE_FINAL_PRICE
    with connection.cursor() as cursor:
        cursor.execute(NEVER_PURCHASED_SQL, [statuses, exclude_negative, page_size, offset])
        columns = [col.name for col in cursor.description]
        return [dict(zip(columns, record)) for record in cursor.fetchall()]


def count_never_purchased():
    statuses = utils.eligible_delivery_statuses()
    exclude_negative = utils.EXCLUDE_NEGATIVE_FINAL_PRICE
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT COUNT(*) FROM public.customers cu
            WHERE NOT EXISTS (
                SELECT 1 FROM public.orders o
                WHERE o.customer_id = cu.customer_id
                  AND o.delivery_status = ANY(%s)
                  AND (%s OR o.final_price >= 0)
            )
            """,
            [statuses, exclude_negative],
        )
        return int(cursor.fetchone()[0] or 0)


CUSTOMER_RFM_SQL = """
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
    ) AS analysis_date
)
SELECT
    COUNT(*)::int                     AS frequency,
    ROUND(COALESCE(SUM(e.final_price), 0)::numeric, 2) AS monetary,
    MAX(e.pdate)::text                               AS last_purchase_date,
    MIN(e.pdate)::text                               AS first_purchase_date,
    (SELECT b.analysis_date)::text                   AS analysis_date
FROM eligible e
"""


def fetch_single_customer_metrics(customer_id):
    """Live eligible metrics for one customer (used as an analysis fallback).

    When no completed snapshot exists yet, a customer dashboard can still fall
    back to this cheap single-customer aggregate; it never recomputes the whole
    population and returns only this customer's raw metrics (segment/scoring
    still requires a full buyer population, so those are simply absent here).
    """
    statuses = utils.eligible_delivery_statuses()
    exclude_negative = utils.EXCLUDE_NEGATIVE_FINAL_PRICE
    with connection.cursor() as cursor:
        cursor.execute(CUSTOMER_RFM_SQL, [customer_id, statuses, exclude_negative])
        columns = [col.name for col in cursor.description]
        record = cursor.fetchone()
    if record is None:
        return None
    row = dict(zip(columns, record))
    if not row['frequency']:
        return None
    if row['last_purchase_date'] and row['analysis_date']:
        from datetime import date
        last = date.fromisoformat(row['last_purchase_date'])
        analysis = date.fromisoformat(row['analysis_date'])
        row['recency_days'] = (analysis - last).days
    return row
