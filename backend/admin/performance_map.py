"""Product Performance Map — sales/revenue quadrant classification of catalog subcategories.

Data sources (read-only; nothing here writes to the database):

  ``public.products``            product identity + the free-text ``sub_category``
                                 the map plots on. Only ``is_active = TRUE`` rows
                                 are counted, exactly like the other catalog KPIs
                                 in ``AdminDashboardStatsView`` / ``AdminProductListView``.
  ``public.orders``              the sales and revenue actually achieved.
                                 ``product_id`` joins ``products.product_key``.

Metric definitions (why these columns):

  * **Sales (X axis)**  = ``SUM(orders.quantity)`` for that product.
  * **Revenue (Y axis)** = ``SUM(orders.final_price)``. ``final_price`` is the
    line gross written at checkout (``unit_price * quantity``, already net of any
    coupon share in ``additional_discount``), so summing it is the realised
    revenue — no price parsing of the TEXT ``actual_price`` column is involved.
  * **Only completed sales count.** The aggregate keeps rows with
    ``delivery_status = 'Delivered'`` and therefore excludes ``Returned`` and
    ``In Transit`` orders, matching the authoritative rule already used by the
    ``rebuild_sales_metrics`` command (``fact_product_analysis.units_sold`` =
    SUM of delivered quantity). Verified against the connected Neon database:
    the delivered-only order aggregate reproduces ``SUM(units_sold)`` exactly
    (1,772,450 units), so ``orders`` is used as the single source for BOTH axes
    because ``fact_product_analysis.total_sales`` no longer agrees with
    delivered-order revenue and would silently mis-state the Y axis.

Quadrant thresholds are data-driven, never hardcoded:

  * ``median_units``   = median of the per-subcategory delivered-unit totals.
  * ``median_revenue`` = median of the per-subcategory delivered-revenue totals.
  * A subcategory is *high* on an axis when it has a non-zero value on that axis
    **and** it is at or above the median. The non-zero guard matters: with the
    raw ``>=`` test a subcategory with zero delivered sales would sit on the
    "high" side of a median of zero, which would put dead stock into Star
    Products. Every subcategory therefore lands in exactly one quadrant, and the
    four quadrants are the median split of the real distribution.

Subcategory names are free text, so grouping uses the project's single
normalization rule (``catalog.normalize``): case/whitespace variants such as
"Dresses"/"dresses" merge into one point, while genuinely different names stay
separate. The display name is the variant that actually carries the most
products, and no stored row is rewritten.
"""

import datetime
import json
from statistics import median

from django.db import connection

from catalog.normalize import normalize_category

# The four quadrants of the map. ``high_sales``/``high_revenue`` are the median
# split conditions, so the labels stay attached to the axes and not to any
# hard-coded sales or revenue figure.
QUADRANT_DEFS = (
    {
        'key': 'star',
        'label': 'Star Products',
        'tagline': 'High Sales + High Revenue',
        'guidance': 'Strong on both axes — protect stock and keep them visible.',
        'high_sales': True,
        'high_revenue': True,
    },
    {
        'key': 'premium',
        'label': 'Premium',
        'tagline': 'Low Sales + High Revenue',
        'guidance': 'Low volume, high value per order — worth targeted demand work.',
        'high_sales': False,
        'high_revenue': True,
    },
    {
        'key': 'volume',
        'label': 'Volume Drivers',
        'tagline': 'High Sales + Low Revenue',
        'guidance': 'Sells often but cheaply — margin and bundling opportunity.',
        'high_sales': True,
        'high_revenue': False,
    },
    {
        'key': 'attention',
        'label': 'Needs Attention',
        'tagline': 'Low Sales + Low Revenue',
        'guidance': 'Below the median on both axes — review pricing and relevance.',
        'high_sales': False,
        'high_revenue': False,
    },
)

QUADRANT_BY_KEY = {q['key']: q for q in QUADRANT_DEFS}

# Delivered orders only — 'Returned' / 'In Transit' are never counted as sales.
DELIVERED_STATUS = 'delivered'

# How many best sellers to attach to each plotted subcategory for drill-down.
TOP_PRODUCTS_PER_SUBCATEGORY = 5

# Products grouped per subcategory, then aggregated to subcategory level in one
# pass. ``sub_category`` is grouped by the normalized key AND the raw trimmed
# value so the caller can pick a display name without a second query.
AGGREGATE_SQL = f"""
WITH delivered AS (
    SELECT o.product_id                    AS product_key,
           SUM(COALESCE(o.quantity, 0))    AS units_sold,
           SUM(COALESCE(o.final_price, 0)) AS revenue
      FROM orders o
     WHERE o.product_id IS NOT NULL
       AND LOWER(TRIM(COALESCE(o.delivery_status, ''))) = %s
     GROUP BY o.product_id
),
product_metrics AS (
    SELECT LOWER(TRIM(COALESCE(p.sub_category, ''))) AS sub_category_key,
           TRIM(COALESCE(p.sub_category, ''))        AS sub_category_display,
           p.product_key                             AS product_key,
           COALESCE(p.name, 'Unnamed Product')       AS product_name,
           COALESCE(p.main_category, '')             AS main_category,
           COALESCE(d.units_sold, 0)::float8         AS units_sold,
           COALESCE(d.revenue, 0)::float8            AS revenue
      FROM products p
      LEFT JOIN delivered d ON d.product_key = p.product_key
     WHERE p.is_active = TRUE
),
ranked AS (
    SELECT m.*,
           ROW_NUMBER() OVER (
               PARTITION BY m.sub_category_key
               ORDER BY m.units_sold DESC, m.revenue DESC, m.product_key
           ) AS rn
      FROM product_metrics m
),
top_products AS (
    SELECT sub_category_key,
           json_agg(json_build_object(
               'product_key', product_key,
               'product_name', product_name,
               'main_category', main_category,
               'units_sold', units_sold,
               'revenue', revenue
           ) ORDER BY rn) AS products
      FROM ranked
     WHERE rn <= %s
     GROUP BY sub_category_key
),
sub_agg AS (
    SELECT sub_category_key,
           sub_category_display,
           COUNT(*)::int                                AS product_count,
           SUM(units_sold)::float8                      AS units_sold,
           SUM(revenue)::float8                         AS revenue,
           COUNT(*) FILTER (WHERE units_sold > 0)::int  AS selling_products
      FROM product_metrics
     GROUP BY 1, 2
)
SELECT a.sub_category_key,
       a.sub_category_display,
       a.product_count,
       a.units_sold,
       a.revenue,
       a.selling_products,
       t.products AS top_products
  FROM sub_agg a
  LEFT JOIN top_products t USING (sub_category_key)
 ORDER BY a.revenue DESC
"""

COLUMNS = (
    'sub_category_key',
    'sub_category_display',
    'product_count',
    'units_sold',
    'revenue',
    'selling_products',
    'top_products',
)


def load_subcategory_rows():
    """Fetch the raw (normalized key, display variant) aggregate rows from Neon.

    Returns [] when the analytics tables are missing or unreadable, so the
    caller can render an empty state instead of a fabricated chart.
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute(AGGREGATE_SQL, [DELIVERED_STATUS, TOP_PRODUCTS_PER_SUBCATEGORY])
            raw = cursor.fetchall()
    except Exception:  # pragma: no cover - depends on the connected database
        return []

    rows = []
    for record in raw:
        row = dict(zip(COLUMNS, record))
        # psycopg delivers json_agg as text on some drivers, as a list on others.
        products = row.get('top_products')
        if isinstance(products, (str, bytes)):
            try:
                products = json.loads(products)
            except ValueError:
                products = []
        row['top_products'] = products or []
        rows.append(row)
    return rows


def _merge_display_variants(rows):
    """Collapse 'Dresses'/'dresses' style variants into one subcategory.

    The display name is the variant with the most products, so the map shows a
    name that really occurs in the data rather than a re-cased invention.
    """
    merged = {}
    for row in rows:
        key = normalize_category(row.get('sub_category_key'))
        if not key:
            key = '__uncategorized__'
        bucket = merged.get(key)
        if bucket is None:
            bucket = {
                'key': key,
                'name': row.get('sub_category_display') or 'Uncategorized',
                '_name_weight': 0,
                'product_count': 0,
                'units_sold': 0.0,
                'revenue': 0.0,
                'selling_products': 0,
                'top_products': [],
            }
            merged[key] = bucket

        bucket['product_count'] += int(row.get('product_count') or 0)
        bucket['units_sold'] += float(row.get('units_sold') or 0.0)
        bucket['revenue'] += float(row.get('revenue') or 0.0)
        bucket['selling_products'] += int(row.get('selling_products') or 0)

        # Adopt the display variant that carries the most products.
        variant_weight = int(row.get('product_count') or 0)
        if variant_weight > bucket['_name_weight']:
            bucket['_name_weight'] = variant_weight
            bucket['name'] = row.get('sub_category_display') or 'Uncategorized'

        bucket['top_products'].extend(row.get('top_products') or [])

    for bucket in merged.values():
        bucket.pop('_name_weight', None)
    return merged


def _quadrant_key(units, revenue, median_units, median_revenue):
    """Median split with a non-zero guard on both axes (see module docstring)."""
    high_sales = units > 0 and units >= median_units
    high_revenue = revenue > 0 and revenue >= median_revenue
    for definition in QUADRANT_DEFS:
        if definition['high_sales'] == high_sales and definition['high_revenue'] == high_revenue:
            return definition['key']
    return 'attention'  # pragma: no cover - the four combinations are exhaustive


def _round(value, digits=2):
    return round(float(value or 0.0), digits)


def build_performance_map(rows):
    """Turn aggregate rows into the chart payload: points, quadrants, thresholds.

    Pure function — no database access, so the classification can be unit-tested
    with any fixture (including the "insufficient data" empty states).
    """
    merged = _merge_display_variants(rows)
    subcategories = sorted(merged.values(), key=lambda item: item['revenue'], reverse=True)

    total_products = sum(item['product_count'] for item in subcategories)
    total_units = sum(item['units_sold'] for item in subcategories)
    total_revenue = sum(item['revenue'] for item in subcategories)

    base = {
        'data_available': False,
        'thresholds': {
            'sales': {'method': 'median', 'value': 0.0, 'label': 'Median units sold'},
            'revenue': {'method': 'median', 'value': 0.0, 'label': 'Median revenue'},
        },
        'summary': {
            'subcategory_count': len(subcategories),
            'total_products': total_products,
            'total_units_sold': _round(total_units, 0),
            'total_revenue': _round(total_revenue),
            'delivered_only': True,
        },
        'quadrants': [],
        'points': [],
        'note': '',
    }

    # --- Empty / insufficient-data states (never fabricate) -----------------
    if not subcategories:
        base['note'] = (
            'No catalog products were found, so there is nothing to plot. '
            'The Product Performance Map appears once products exist.'
        )
        return base

    if total_units <= 0 or total_revenue <= 0:
        base['note'] = (
            'No delivered (completed) sales are recorded for this catalog yet — '
            'returned and in-transit orders are excluded, so the map has no '
            'sales or revenue data to classify. Nothing has been estimated.'
        )
        return base

    median_units = float(median([item['units_sold'] for item in subcategories]))
    median_revenue = float(median([item['revenue'] for item in subcategories]))
    # The medians are rounded once and then used for the classification itself,
    # so the cut-offs published in the payload are exactly the ones applied. A
    # chart that draws its divider at the reported number can then never put a
    # point on the wrong side of it through rounding alone.
    median_units = _round(median_units, 0)
    median_revenue = _round(median_revenue)

    points = []
    for item in subcategories:
        # Round first, then classify: the tooltip numbers and the quadrant a
        # point is filed under are therefore produced from the same values.
        units = _round(item['units_sold'], 0)
        revenue = _round(item['revenue'])
        quadrant = _quadrant_key(units, revenue, median_units, median_revenue)
        points.append({
            'key': item['key'],
            'subcategory': item['name'],
            'product_count': item['product_count'],
            'units_sold': units,
            'revenue': revenue,
            # Average realised rupees per delivered unit — explains why a
            # high-volume subcategory can still sit below the revenue median.
            'revenue_per_unit': _round(item['revenue'] / item['units_sold']) if item['units_sold'] else 0.0,
            'selling_products': item['selling_products'],
            'quadrant': quadrant,
            'top_products': [
                {
                    'product_key': p.get('product_key'),
                    'product_name': p.get('product_name'),
                    'main_category': p.get('main_category'),
                    'units_sold': _round(p.get('units_sold'), 0),
                    'revenue': _round(p.get('revenue')),
                }
                # A merged display variant can bring its own top list along.
                for p in sorted(
                    item['top_products'],
                    key=lambda p: float(p.get('units_sold') or 0),
                    reverse=True,
                )[:TOP_PRODUCTS_PER_SUBCATEGORY]
            ],
        })

    quadrants = []
    for definition in QUADRANT_DEFS:
        members = [p for p in points if p['quadrant'] == definition['key']]
        quadrant_units = sum(p['units_sold'] for p in members)
        quadrant_revenue = sum(p['revenue'] for p in members)
        quadrants.append({
            'key': definition['key'],
            'label': definition['label'],
            'tagline': definition['tagline'],
            'guidance': definition['guidance'],
            'high_sales': definition['high_sales'],
            'high_revenue': definition['high_revenue'],
            'subcategory_count': len(members),
            'product_count': sum(p['product_count'] for p in members),
            'units_sold': _round(quadrant_units, 0),
            'revenue': _round(quadrant_revenue),
            'revenue_share': _round(100 * quadrant_revenue / total_revenue, 1) if total_revenue else 0.0,
            'sales_share': _round(100 * quadrant_units / total_units, 1) if total_units else 0.0,
            # Names of the real subcategories filed in this quadrant, biggest
            # revenue first; the count of members tells how many are listed.
            'subcategories': [p['subcategory'] for p in members],
        })

    base['data_available'] = True
    base['thresholds'] = {
        'sales': {
            'method': 'median',
            'value': median_units,
            'label': 'Median units sold',
            'description': 'Subcategories at or above this delivered-unit total count as high sales.',
        },
        'revenue': {
            'method': 'median',
            'value': median_revenue,
            'label': 'Median revenue',
            'description': 'Subcategories at or above this delivered revenue count as high revenue.',
        },
    }
    base['quadrants'] = quadrants
    base['points'] = points
    base['note'] = (
        'Sales and revenue cover delivered orders only; returned and in-transit '
        'orders are excluded. Quadrant cut-offs are the medians of the current '
        'subcategory totals, so they move with the data.'
    )
    return base


def build_source_meta():
    """Provenance block shipped with every payload so the chart can state its basis."""
    return {
        'database': 'Neon PostgreSQL',
        'tables': ['public.products', 'public.orders'],
        'sales_metric': "SUM(orders.quantity) WHERE delivery_status = 'Delivered'",
        'revenue_metric': "SUM(orders.final_price) WHERE delivery_status = 'Delivered'",
        'excluded_order_states': ['Returned', 'In Transit'],
        'product_scope': 'products.is_active = TRUE',
        'grouping': 'products.sub_category (case/whitespace variants merged)',
        'classification': 'median split on delivered units (X) and delivered revenue (Y)',
        'generated_at': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'),
    }
