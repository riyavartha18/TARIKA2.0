"""Inventory-velocity metrics: cached summary table + single-query rebuild.

The Admin "Inventory Velocity" analysis needs, for EVERY active product, its
current stock, units sold in the last 30 days, average daily sales, days of
stock and a movement classification. Computing that by joining + aggregating
the ~1M-row ``orders`` table on every dashboard render is far too expensive,
and doing it per page would re-run the aggregate on every click-through. This
module keeps a summary table (``inventory_velocity_metrics``) that is:

  * rebuilt in ONE SQL statement (sales are aggregated database-side with a
    GROUP BY -- no order rows ever stream to Python),
  * reused for every page / filter / sort combination via indexes, so paging
    through the full ~90k catalog is a cheap indexed read,
  * invalidated (``mark_metrics_stale``) whenever orders or stock change, and
  * rebuilt lazily at most once per TTL (default 900s), so the classification
    and its data-driven thresholds always track the real sales data.

SALES RULE (verified against the real Neon schema): a valid sale is a row in
``public.orders`` with ``delivery_status = 'Delivered'``; ``In Transit`` and
``Returned`` are NOT completed sales and are excluded -- the same rule the
demand engine uses for ``units_sold``. Quantities come from ``orders.quantity``
so a multi-unit order counts its units. ``purchase_date`` is TEXT DD-MM-YYYY;
only well-formed dates are converted.

MOVEMENT CLASSIFICATION IS DRIVEN BY ACTUAL SALES QUANTITY, not by stock:
  * NOT MOVING   -- zero units sold in the window (always, regardless of stock).
  * FAST MOVING  -- the highest-selling products (units above the upper cut).
  * NORMAL MOVING-- moderate sellers (units above the lower cut).
  * SLOW MOVING  -- low but still positive sellers (units <= lower cut).
The two cut points are DATA-DRIVEN terciles (by default the 66.67th and 33.33rd
percentiles) of ``sales_last_30_days`` taken over only the products that sold
at all, so a higher sales quantity always lands in an equal-or-higher tier and
the bands adapt to the real sales distribution of the eligible products.

Days of stock stays a pure inventory metric: stock / avg_daily_sales, 0 when
there is no stock, and NULL (rendered "No Sales") when avg daily sales is 0 --
never a divide-by-zero and never a driver of the movement tier.

30-day window: the dataset's order dates can lag behind wall-clock today, so
the window END is anchored to the latest *valid* delivered date not after
today. With live data this is simply today; with a historical dataset the last
30 days of ACTUAL orders are analysed instead of an always-empty window.
"""

import datetime
import os

from django.db import connection, transaction

METRICS_TABLE = 'inventory_velocity_metrics'
STATE_TABLE = 'inventory_velocity_refresh_state'

# Index supporting the mandatory display order (tier priority, then sales).
IDX_MOVEMENT = 'inv_velocity_movement_sales_idx'
IDX_RANK_SALES = 'inv_velocity_rank_sales_idx'
IDX_DAYS = 'inv_velocity_days_idx'
IDX_NAME = 'inv_velocity_name_idx'
IDX_SALES = 'inv_velocity_sales_idx'
LOCK_KEY = 82300701  # advisory-lock namespace for rebuilds

# ---- Configurable, transparent, data-driven thresholds ---------------------
SALES_WINDOW_DAYS = int(os.getenv('INVENTORY_SALES_WINDOW_DAYS', '30'))
# Percentiles (0-100) of the positive-seller sales distribution that define the
# tier boundaries. FAST = above the upper percentile, NORMAL = above the lower,
# SLOW = positive but at or below the lower. Terciles by default.
FAST_PERCENTILE = float(os.getenv('INVENTORY_FAST_PERCENTILE', '66.67'))
NORMAL_PERCENTILE = float(os.getenv('INVENTORY_NORMAL_PERCENTILE', '33.33'))
METRICS_TTL_SECONDS = int(os.getenv('INVENTORY_METRICS_TTL_SECONDS', '900'))

# Tier labels + their fixed display priority (Fast -> Normal -> Slow -> Not).
MOVEMENT_FAST = 'FAST MOVING'
MOVEMENT_NORMAL = 'NORMAL MOVING'
MOVEMENT_SLOW = 'SLOW MOVING'
MOVEMENT_NOT = 'NOT MOVING'
MOVEMENT_RANK = {
    MOVEMENT_FAST: 0,
    MOVEMENT_NORMAL: 1,
    MOVEMENT_SLOW: 2,
    MOVEMENT_NOT: 3,
}
# Ordered highest -> lowest (used by the dashboard filter pills).
MOVEMENT_LABELS = (MOVEMENT_FAST, MOVEMENT_NORMAL, MOVEMENT_SLOW, MOVEMENT_NOT)

# Well-formed delivered-sale rows (internal constants).
_VALID_DELIVERED_SQL = """
    SELECT to_date(purchase_date, 'DD-MM-YYYY') AS d
    FROM orders
    WHERE delivery_status = 'Delivered'
      AND purchase_date ~ '^[0-9]{2}-[0-9]{2}-[0-9]{4}$'
"""

# The window END is the latest valid delivered order date not after today, so
# the analysis always covers the last 30 days of ACTUAL orders (a historical
# dataset whose newest order predates today would otherwise land on an empty
# window). Falls back to today only when there is no usable delivered date.
WINDOW_END_SQL = f"""
    SELECT COALESCE(
        (SELECT MAX(d) FROM ({_VALID_DELIVERED_SQL}) v
          WHERE d <= CURRENT_DATE),
        CURRENT_DATE
    )::date
"""


def _window_start_sql(end_sql):
    return f"({end_sql} - INTERVAL '{SALES_WINDOW_DAYS - 1} days')::date"


def _sold_cte(end_sql):
    """Per-product delivered units over the fixed 30-day window."""
    return f"""
    SELECT o.product_id, SUM(o.quantity)::bigint AS units_sold
    FROM orders o
    WHERE o.delivery_status = 'Delivered'
      AND o.purchase_date ~ '^[0-9]{{2}}-[0-9]{{2}}-[0-9]{{4}}$'
      AND to_date(o.purchase_date, 'DD-MM-YYYY')
          BETWEEN {_window_start_sql(end_sql)} AND {end_sql}
    GROUP BY o.product_id
"""


def cuts_sql(end_sql):
    """Data-driven tier cut points: percentiles of the POSITIVE-seller sales."""
    return f"""
    WITH s AS ({_sold_cte(end_sql)})
    SELECT
        COALESCE(PERCENTILE_CONT({FAST_PERCENTILE / 100.0})
                 WITHIN GROUP (ORDER BY units_sold), 0)::float8 AS fast_cut,
        COALESCE(PERCENTILE_CONT({NORMAL_PERCENTILE / 100.0})
                 WITHIN GROUP (ORDER BY units_sold), 0)::float8 AS normal_cut
    FROM s
    WHERE units_sold > 0
"""


_CREATE_METRICS_SQL = f"""
CREATE TABLE IF NOT EXISTS public.{METRICS_TABLE} (
    product_key        text PRIMARY KEY,
    product_name       text,
    main_category      text,
    sub_category       text,
    current_stock      double precision NOT NULL DEFAULT 0,
    sales_last_30_days bigint NOT NULL DEFAULT 0,
    avg_daily_sales    numeric(12, 2) NOT NULL DEFAULT 0,
    days_of_stock      double precision,
    movement_status    text NOT NULL,
    movement_rank      smallint NOT NULL DEFAULT 3,
    is_out_of_stock    boolean NOT NULL DEFAULT false
)
"""

# Idempotent upgrade path for a metrics table created before movement_rank.
_METRICS_ADD_COLUMN_SQLS = (
    f"ALTER TABLE public.{METRICS_TABLE} ADD COLUMN IF NOT EXISTS movement_rank smallint NOT NULL DEFAULT 3",
)

_CREATE_STATE_SQL = f"""
CREATE TABLE IF NOT EXISTS public.{STATE_TABLE} (
    id             integer PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    refreshed_at   double precision,
    window_start   date,
    window_end     date,
    product_count  integer NOT NULL DEFAULT 0,
    fast_moving    integer NOT NULL DEFAULT 0,
    normal_moving  integer NOT NULL DEFAULT 0,
    slow_moving    integer NOT NULL DEFAULT 0,
    not_moving     integer NOT NULL DEFAULT 0,
    out_of_stock   integer NOT NULL DEFAULT 0,
    window_units   bigint  NOT NULL DEFAULT 0,
    fast_cut       double precision,
    normal_cut     double precision
)
"""

# Summary tiles + the tier cuts are cached on the state row so the dashboard
# reads them for free (no per-request aggregate scan of the 88k rows).
_STATE_ADD_COLUMN_SQLS = (
    "ALTER TABLE public.{t} ADD COLUMN IF NOT EXISTS fast_moving integer NOT NULL DEFAULT 0",
    "ALTER TABLE public.{t} ADD COLUMN IF NOT EXISTS normal_moving integer NOT NULL DEFAULT 0",
    "ALTER TABLE public.{t} ADD COLUMN IF NOT EXISTS slow_moving integer NOT NULL DEFAULT 0",
    "ALTER TABLE public.{t} ADD COLUMN IF NOT EXISTS not_moving integer NOT NULL DEFAULT 0",
    "ALTER TABLE public.{t} ADD COLUMN IF NOT EXISTS out_of_stock integer NOT NULL DEFAULT 0",
    "ALTER TABLE public.{t} ADD COLUMN IF NOT EXISTS window_units bigint NOT NULL DEFAULT 0",
    "ALTER TABLE public.{t} ADD COLUMN IF NOT EXISTS fast_cut double precision",
    "ALTER TABLE public.{t} ADD COLUMN IF NOT EXISTS normal_cut double precision",
)

_CREATE_INDEX_SQLS = (
    # Tier priority then highest sales first -- exactly the required order.
    f"CREATE INDEX IF NOT EXISTS {IDX_RANK_SALES} "
    f"ON public.{METRICS_TABLE} (movement_rank ASC, sales_last_30_days DESC)",
    f"CREATE INDEX IF NOT EXISTS {IDX_MOVEMENT} "
    f"ON public.{METRICS_TABLE} (movement_status, sales_last_30_days DESC)",
    f"CREATE INDEX IF NOT EXISTS {IDX_DAYS} "
    f"ON public.{METRICS_TABLE} (days_of_stock ASC NULLS LAST, sales_last_30_days DESC)",
    f"CREATE INDEX IF NOT EXISTS {IDX_NAME} "
    f"ON public.{METRICS_TABLE} (product_name)",
    f"CREATE INDEX IF NOT EXISTS {IDX_SALES} "
    f"ON public.{METRICS_TABLE} (sales_last_30_days DESC)",
)

# The delivered-order aggregate scans orders once per TTL; purchase_date is
# TEXT DD-MM-YYYY (not lexicographically sortable as a date) and to_date is
# STABLE (cannot back an expression index), so the existing partial-support
# index (product_id, delivery_status) is what the GROUP BY join uses. A seq
# scan of the date predicate for a single once-per-window aggregate is cheap
# and the dashboard never touches it -- it reads the indexed summary below.
_ORDERS_INDEX_SQLS = (
    "CREATE INDEX IF NOT EXISTS orders_product_delivery_idx "
    "ON public.orders (product_id, delivery_status)",
)


def _insert_sql(end_sql):
    """One statement that classifies every active product by sales quantity.

    The tier cut points are bound as parameters (fast_cut, normal_cut) from the
    caller's ``cuts_sql`` result, so the SQL and the cached thresholds are
    always the same numbers.
    """
    return f"""
INSERT INTO public.{METRICS_TABLE} (
    product_key, product_name, main_category, sub_category,
    current_stock, sales_last_30_days, avg_daily_sales,
    days_of_stock, movement_status, movement_rank, is_out_of_stock
)
WITH s AS ({_sold_cte(end_sql)}),
t AS (
    SELECT p AS product_row,
           COALESCE(p.available_quantity, 0) AS stock,
           COALESCE(s.units_sold, 0) AS units_sold,
           CASE WHEN s.units_sold IS NOT NULL AND s.units_sold > 0
                THEN ROUND(s.units_sold::numeric / {SALES_WINDOW_DAYS}, 2)::float
           END AS avg_daily
    FROM products p
    LEFT JOIN s ON s.product_id = p.product_key
    WHERE p.is_active = TRUE
),
classified AS (
    SELECT t.*,
           CASE
             WHEN t.units_sold = 0 THEN '{MOVEMENT_NOT}'
             WHEN t.units_sold > %s THEN '{MOVEMENT_FAST}'
             WHEN t.units_sold > %s THEN '{MOVEMENT_NORMAL}'
             ELSE '{MOVEMENT_SLOW}'
           END AS movement_status
    FROM t
)
SELECT
    (product_row).product_key,
    (product_row).name,
    (product_row).main_category,
    (product_row).sub_category,
    stock,
    units_sold,
    COALESCE(avg_daily, 0),
    -- Days of stock = stock / avg daily; NULL when there are no sales,
    -- CEIL(0 / avg) = 0 when there is no stock. Never a divide-by-zero.
    CASE WHEN avg_daily > 0 THEN CEIL(stock / avg_daily) END,
    movement_status,
    CASE movement_status
      WHEN '{MOVEMENT_FAST}' THEN 0
      WHEN '{MOVEMENT_NORMAL}' THEN 1
      WHEN '{MOVEMENT_SLOW}' THEN 2
      ELSE 3
    END,
    stock <= 0
FROM classified
"""


def ensure_schema():
    """Idempotently create the summary tables + supporting indexes."""
    with connection.cursor() as cursor:
        cursor.execute(_CREATE_METRICS_SQL)
        for sql in _METRICS_ADD_COLUMN_SQLS:
            cursor.execute(sql)
        cursor.execute(_CREATE_STATE_SQL)
        for sql in _STATE_ADD_COLUMN_SQLS:
            cursor.execute(sql.format(t=STATE_TABLE))
        for sql in _CREATE_INDEX_SQLS:
            cursor.execute(sql)
        for sql in _ORDERS_INDEX_SQLS:
            cursor.execute(sql)
        cursor.execute(
            f"INSERT INTO public.{STATE_TABLE} (id) VALUES (1) "
            f"ON CONFLICT (id) DO NOTHING"
        )


def rebuild_metrics():
    """Recompute every active product's metrics + tiers in one aggregation.

    Runs under a transaction-scoped advisory lock plus a row lock on the state
    row, so parallel requests never double-rebuild; a blocked second caller
    finds the state already refreshed when it resumes.
    """
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(%s)", [LOCK_KEY])
            cursor.execute(
                f"SELECT 1 FROM public.{STATE_TABLE} WHERE id = 1 FOR UPDATE")
            cursor.execute(WINDOW_END_SQL)
            end_date = cursor.fetchone()[0]
            end_sql = f"DATE '{end_date.isoformat()}'"

            # Data-driven terciles over the products that actually sold.
            cursor.execute(cuts_sql(end_sql))
            fast_cut, normal_cut = cursor.fetchone()

            cursor.execute(f"TRUNCATE public.{METRICS_TABLE}")
            cursor.execute(_insert_sql(end_sql), [fast_cut, normal_cut])
            inserted = cursor.rowcount

            # Whole-table tier/summary counts, computed once here and cached on
            # the state row so the dashboard never re-scans 88k rows per read.
            cursor.execute(f"""
                SELECT COUNT(*) FILTER (WHERE movement_status = '{MOVEMENT_FAST}')::int,
                       COUNT(*) FILTER (WHERE movement_status = '{MOVEMENT_NORMAL}')::int,
                       COUNT(*) FILTER (WHERE movement_status = '{MOVEMENT_SLOW}')::int,
                       COUNT(*) FILTER (WHERE movement_status = '{MOVEMENT_NOT}')::int,
                       COUNT(*) FILTER (WHERE is_out_of_stock)::int,
                       COALESCE(SUM(sales_last_30_days), 0)::bigint
                FROM public.{METRICS_TABLE}
            """)
            fast_n, normal_n, slow_n, not_n, oos_n, win_units = cursor.fetchone()
            cursor.execute(f"""
                UPDATE public.{STATE_TABLE}
                   SET refreshed_at = EXTRACT(EPOCH FROM (now() AT TIME ZONE 'utc')),
                       window_start = {_window_start_sql(end_sql)},
                       window_end = ({end_sql}),
                       product_count = %s,
                       fast_moving = %s,
                       normal_moving = %s,
                       slow_moving = %s,
                       not_moving = %s,
                       out_of_stock = %s,
                       window_units = %s,
                       fast_cut = %s,
                       normal_cut = %s
                 WHERE id = 1
            """, [inserted, fast_n, normal_n, slow_n, not_n, oos_n, win_units,
                  fast_cut, normal_cut])


def state_snapshot():
    # Trivial single-row read: the state row carries the cached product count,
    # every summary-tile count and the current tier cuts, so the dashboard
    # never re-scans the metrics table for them. Returns None when the tables
    # are not created yet (fresh deploy) so ensure_fresh can build on demand.
    try:
        with connection.cursor() as cursor:
            cursor.execute(f"""
                SELECT refreshed_at, window_start::text, window_end::text,
                       product_count, fast_moving, normal_moving, slow_moving,
                       not_moving, out_of_stock, window_units, fast_cut, normal_cut
                FROM public.{STATE_TABLE} WHERE id = 1
            """)
            row = cursor.fetchone()
    except Exception:  # noqa: BLE001 - tables not created yet
        try:
            connection.close()
        except Exception:  # noqa: BLE001
            pass
        return None
    if not row:
        return None
    (refreshed_at, window_start, window_end, product_count,
     fast_n, normal_n, slow_n, not_n, oos_n, win_units,
     fast_cut, normal_cut) = row
    return {
        'refreshed_at': float(refreshed_at) if refreshed_at is not None else None,
        'window_start': window_start,
        'window_end': window_end,
        'product_count': int(product_count or 0),
        'summary': {
            'fast_moving': int(fast_n or 0),
            'normal_moving': int(normal_n or 0),
            'slow_moving': int(slow_n or 0),
            'not_moving': int(not_n or 0),
            'out_of_stock': int(oos_n or 0),
            'window_units': int(win_units or 0),
        },
        'thresholds': {
            'fast_cut': float(fast_cut) if fast_cut is not None else None,
            'normal_cut': float(normal_cut) if normal_cut is not None else None,
        },
    }


def time_now():
    return datetime.datetime.now(datetime.timezone.utc).timestamp()


def ensure_fresh(force=False):
    """Make the summary table usable; rebuild only when actually stale.

    Returns the state snapshot. Reads state in a single round-trip; if the
    table does not exist yet (fresh deployment) the schema is created and built
    on demand. A concurrent caller waiting on the rebuild lock finds the state
    already refreshed, so no double rebuild.
    """
    state = state_snapshot()
    if state is None:
        # Table / state row missing -> build from scratch.
        ensure_schema()
        rebuild_metrics()
        return state_snapshot()

    fresh = bool(
        state['refreshed_at'] is not None
        and state['product_count'] > 0
        and (time_now() - state['refreshed_at']) < METRICS_TTL_SECONDS
    )
    if force or not fresh:
        rebuild_metrics()
        state = state_snapshot()
    return state


def mark_metrics_stale():
    """Invalidate the cached metrics after an order or stock mutation.

    Best-effort: a failure to invalidate (e.g. the table does not exist yet in
    a brand-new environment) must never break a checkout or a goods receipt --
    the TTL rebuild keeps the metrics correct regardless.
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                f"UPDATE public.{STATE_TABLE} SET refreshed_at = NULL WHERE id = 1")
    except Exception:  # noqa: BLE001 - invalidation is strictly best-effort
        try:
            connection.close()
        except Exception:  # noqa: BLE001
            pass


def classify(units, fast_cut, normal_cut, stock=None, window_days=None):
    """Python mirror of the SQL sales-quantity tiering (tests / callers).

    Tier is decided by ACTUAL sales quantity only; ``stock`` is used just for
    the days-of-stock helper value and never moves a product up a tier.
    Returns (movement_status, avg_daily_sales, days_of_stock) where
    days_of_stock is None for a no-sales product with stock on hand.
    """
    window_days = window_days or SALES_WINDOW_DAYS
    units = int(units or 0)
    avg_daily = round(units / window_days, 2) if units else 0.0
    if units <= 0:
        days = None if (stock or 0) > 0 else 0.0
        return MOVEMENT_NOT, avg_daily, days
    if units > fast_cut:
        status = MOVEMENT_FAST
    elif units > normal_cut:
        status = MOVEMENT_NORMAL
    else:
        status = MOVEMENT_SLOW
    if stock is None:
        return status, avg_daily, None
    if stock <= 0:
        return status, avg_daily, 0.0
    days = float(-(-stock // avg_daily)) if avg_daily > 0 else None
    return status, avg_daily, days
