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
from .models import CustomerSegment


def _big_spender_param():
    import json
    return json.dumps([utils.TAG_BIG_SPENDER])


# The whole dashboard aggregate - overall KPIs, the six-segment distribution and
# the K-Means cluster profiles - computed in ONE pass over the small result
# table via GROUPING SETS. The remote Neon database is the bottleneck (every
# round trip is ~250 ms while the aggregate itself runs in ~20 ms), so turning
# three separate queries into one is the main latency win; the caller then caches
# the result per (version, clustering epoch) so warm reads need no query at all.
#
# Row kinds, from the two GROUPING() flags:
#   g_segment=1, g_kmeans=1 -> the overall totals row
#   g_segment=0             -> one segment-distribution row
#   g_kmeans=0              -> one cluster row (kmeans_cluster_id NULL skipped)
DASHBOARD_BUNDLE_SQL = """
SELECT
    GROUPING(segment)                    AS g_segment,
    GROUPING(kmeans_cluster_id)          AS g_kmeans,
    segment,
    kmeans_cluster_id,
    kmeans_category,
    COUNT(*)::bigint                     AS row_count,
    COALESCE(SUM(frequency), 0)::bigint  AS sum_frequency,
    COALESCE(SUM(monetary), 0)           AS sum_monetary,
    AVG(recency)::float                  AS avg_recency,
    AVG(frequency)::float                AS avg_frequency,
    AVG(monetary)::float                 AS avg_monetary,
    COUNT(*) FILTER (WHERE tags @> %s::jsonb)::bigint AS big_spender_count
FROM rfm_customer_segments
GROUP BY GROUPING SETS ( (), (segment), (kmeans_cluster_id, kmeans_category) )
ORDER BY g_segment, g_kmeans, segment, kmeans_cluster_id
"""


def _empty_bundle():
    return {
        'totals': {'buyer_count': 0, 'total_orders': 0,
                   'total_revenue': 0, 'big_spender_count': 0},
        'distribution': [],
        'kmeans_clusters': [],
    }


def fetch_dashboard_bundle():
    """One-query dashboard aggregate bundle (Postgres) or ORM fallback.

    Returns ``{'totals', 'distribution', 'kmeans_clusters'}``. The shape is
    identical across vendors so the (cached) summary view is backend-agnostic.
    """
    if connection.vendor != 'postgresql':
        return _fetch_dashboard_bundle_orm()

    bundle = _empty_bundle()
    with connection.cursor() as cursor:
        cursor.execute(DASHBOARD_BUNDLE_SQL, [_big_spender_param()])
        columns = [c.name for c in cursor.description]
        rows = [dict(zip(columns, r)) for r in cursor.fetchall()]

    for row in rows:
        if row['g_segment'] == 1 and row['g_kmeans'] == 1:
            bundle['totals'] = {
                'buyer_count': int(row['row_count'] or 0),
                'total_orders': int(row['sum_frequency'] or 0),
                'total_revenue': round(float(row['sum_monetary'] or 0), 2),
                'big_spender_count': int(row['big_spender_count'] or 0),
            }
        elif row['g_segment'] == 0:
            bundle['distribution'].append(
                {'segment': row['segment'], 'count': int(row['row_count'] or 0)})
        elif row['g_kmeans'] == 0 and row['kmeans_cluster_id'] is not None:
            bundle['kmeans_clusters'].append({
                'cluster_id': row['kmeans_cluster_id'],
                'category': row['kmeans_category'] or '',
                'customer_count': int(row['row_count'] or 0),
                'avg_recency': _round_or_none(row['avg_recency'], 2),
                'avg_frequency': _round_or_none(row['avg_frequency'], 2),
                'avg_monetary': _round_or_none(row['avg_monetary'], 2),
            })

    bundle['distribution'].sort(key=lambda d: d['segment'])
    bundle['kmeans_clusters'].sort(key=lambda c: c['cluster_id'])
    return bundle


def _round_or_none(value, digits):
    return round(float(value), digits) if value is not None else None


def _fetch_dashboard_bundle_orm():
    """Backend-agnostic fallback (SQLite tests): same shape, a few ORM reads.

    Only non-PostgreSQL backends land here, and the one thing they cannot do is
    the JSONB `tags @> [...]` containment the SQL statement uses - `contains` is
    not implemented on SQLite - so the Big Spender count is tallied from the
    stored tag lists in Python instead. Production always takes the single
    GROUPING SETS statement above.
    """
    from django.db.models import Avg, Count, DecimalField, Sum, Value
    from django.db.models.functions import Coalesce

    totals = CustomerSegment.objects.aggregate(
        buyer_count=Count('customer_id'),
        total_orders=Coalesce(Sum('frequency'), Value(0)),
        total_revenue=Coalesce(
            Sum('monetary'), Value(0),
            output_field=DecimalField(max_digits=16, decimal_places=2)),
    )
    big_spenders = sum(1 for tags in
                       CustomerSegment.objects.values_list('tags', flat=True)
                       if utils.TAG_BIG_SPENDER in (tags or []))
    distribution = [
        {'segment': row['segment'], 'count': row['count']}
        for row in CustomerSegment.objects.values('segment')
        .annotate(count=Count('customer_id')).order_by('segment')
    ]
    cluster_rows = (
        CustomerSegment.objects
        .exclude(kmeans_cluster_id__isnull=True)
        .values('kmeans_cluster_id', 'kmeans_category')
        .annotate(
            customer_count=Count('customer_id'),
            avg_recency=Avg('recency'),
            avg_frequency=Avg('frequency'),
            avg_monetary=Avg('monetary'),
        )
        .order_by('kmeans_cluster_id')
    )
    kmeans_clusters = [
        {
            'cluster_id': r['kmeans_cluster_id'],
            'category': r['kmeans_category'] or '',
            'customer_count': r['customer_count'],
            'avg_recency': _round_or_none(r['avg_recency'], 2),
            'avg_frequency': _round_or_none(r['avg_frequency'], 2),
            'avg_monetary': _round_or_none(r['avg_monetary'], 2),
        }
        for r in cluster_rows
    ]
    return {
        'totals': {
            'buyer_count': totals['buyer_count'] or 0,
            'total_orders': totals['total_orders'] or 0,
            'total_revenue': round(float(totals['total_revenue'] or 0), 2),
            'big_spender_count': big_spenders,
        },
        'distribution': distribution,
        'kmeans_clusters': kmeans_clusters,
    }



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

    On a backend without the pre-existing dataset table - the SQLite used for
    unit tests has no `public.customers` - there is nothing to count, so it
    reports 0 instead of failing. That is the same convention
    `compute_source_fingerprint` uses for a missing `public.orders`, and it is
    what lets the dashboard aggregate be built and cached on any backend.
    """
    if connection.vendor != 'postgresql':
        return 0
    with connection.cursor() as cursor:
        cursor.execute(AGGREGATE_TOTALS_SQL)
        return int(cursor.fetchone()[0] or 0)


# A single cheap pass over the eligible orders that uniquely fingerprints the
# source data a run consumed: adding/removing an eligible order (a new purchase
# or a cancellation/return that changes eligibility) moves the count; a new
# buyer moves the distinct-buyer count; a newer purchase moves the max date.
# The incremental refresh compares this against the fingerprint stored with the
# last completed version to decide - without a dirty-customer queue - whether
# anything actually changed. It is index-assisted by `orders_rfm_delivered_idx`.
SOURCE_FINGERPRINT_SQL = """
SELECT
    COUNT(*)::bigint                              AS order_count,
    COUNT(DISTINCT o.customer_id)::bigint         AS buyer_count,
    MAX(to_date(o.purchase_date, 'DD-MM-YYYY'))::text AS max_date
FROM public.orders o
WHERE o.delivery_status = ANY(%s)
  AND o.customer_id IS NOT NULL
  AND o.purchase_date IS NOT NULL
  AND (%s OR o.final_price >= 0)
"""


def compute_source_fingerprint():
    """Short stable string fingerprint of the current eligible source data.

    Returns '' on a backend without the `public.orders` table (e.g. the SQLite
    used for unit tests), which the incremental path treats as "cannot prove
    unchanged" and therefore refreshes.
    """
    if connection.vendor != 'postgresql':
        return ''
    statuses = utils.eligible_delivery_statuses()
    exclude_negative = utils.EXCLUDE_NEGATIVE_FINAL_PRICE
    with connection.cursor() as cursor:
        cursor.execute(SOURCE_FINGERPRINT_SQL, [statuses, exclude_negative])
        order_count, buyer_count, max_date = cursor.fetchone()
    return f'{order_count}|{buyer_count}|{max_date or ""}'


def fetch_dashboard_totals():
    """Dashboard KPIs + segment distribution from the persisted result table.

    Aggregation runs entirely in PostgreSQL over the small (one row per buyer)
    `rfm_customer_segments` table - a ~20 ms index/seq scan on 100k rows - so a
    completed dashboard render never depends on the ephemeral cache snapshot and
    never re-scans the 1M-row orders table. This is what makes the RFM page open
    instantly after a restart: it shows the latest *successfully completed*
    analysis that is already stored, while any refresh happens in the background.

    Returns (totals, distribution):
      totals       - {buyer_count, total_orders, total_revenue, big_spender_count}
      distribution - [{segment, count}, ...] ordered by label
    """
    from django.db.models import Count, DecimalField, Q, Sum, Value
    from django.db.models.functions import Coalesce

    totals = CustomerSegment.objects.aggregate(
        buyer_count=Count('customer_id'),
        total_orders=Coalesce(Sum('frequency'), Value(0)),
        total_revenue=Coalesce(
            Sum('monetary'), Value(0),
            output_field=DecimalField(max_digits=16, decimal_places=2)),
        big_spender_count=Count(
            'customer_id', filter=Q(tags__contains=[utils.TAG_BIG_SPENDER])),
    )
    distribution = list(
        CustomerSegment.objects.values('segment')
        .annotate(count=Count('customer_id'))
        .order_by('segment'))
    return totals, distribution


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
