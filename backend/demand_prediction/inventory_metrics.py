"""Inventory-velocity metrics: cached summary table + single-query rebuild.

The Admin "Inventory Velocity" analysis needs, for EVERY active product, its
current stock, units sold in the last 30 days, average daily sales, days of
stock and a fast / normal / slow / non-moving classification. Computing that
by joining + aggregating the ~1M-row ``orders`` table on every dashboard
render is far too expensive, and doing it per page would re-run the aggregate
on every click-through. This module keeps a summary table
(``inventory_velocity_metrics``) that is:

  * rebuilt in ONE SQL statement (sales are aggregated database-side with a
    GROUP BY -- no order rows ever stream to Python),
  * reused for every page / filter / sort combination via indexes, so paging
    through the full ~90k catalog is a cheap indexed read,
  * invalidated (``mark_metrics_stale``) whenever orders or stock change, and
  * rebuilt lazily at most once per TTL (default 900s).

Sales rule (verified against the real Neon schema): a valid sale is a row in
``public.orders`` with ``delivery_status = 'Delivered'``; ``In Transit`` and
``Returned`` are NOT completed sales and are excluded -- the same rule the
demand engine uses for ``units_sold``. Quantities come from ``orders.quantity``
so a multi-unit order counts its units. ``purchase_date`` is TEXT DD-MM-YYYY;
only well-formed dates are converted (``to_date`` silently rolls impossible
days such as '31-02-2025' forward, so a parsed-dates-within-2000-days guard
drops that junk).

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

IDX_MOVEMENT = 'inv_velocity_movement_sales_idx'
IDX_DAYS = 'inv_velocity_days_idx'
IDX_NAME = 'inv_velocity_name_idx'
IDX_SALES = 'inv_velocity_sales_idx'
LOCK_KEY = 82300701  # advisory-lock namespace for rebuilds

# ---- Configurable, transparent classification thresholds -------------------
SALES_WINDOW_DAYS = int(os.getenv('INVENTORY_SALES_WINDOW_DAYS', '30'))
FAST_MAX_DAYS = int(os.getenv('INVENTORY_FAST_MAX_DAYS', '15'))
NORMAL_MAX_DAYS = int(os.getenv('INVENTORY_NORMAL_MAX_DAYS', '60'))
SLOW_MAX_DAYS = int(os.getenv('INVENTORY_SLOW_MAX_DAYS', '180'))
METRICS_TTL_SECONDS = int(os.getenv('INVENTORY_METRICS_TTL_SECONDS', '900'))

MOVEMENT_FAST = 'FAST MOVING'
MOVEMENT_NORMAL = 'NORMAL'
MOVEMENT_SLOW = 'SLOW'
MOVEMENT_NON_MOVING = 'NON MOVING'
MOVEMENT_LABELS = (MOVEMENT_FAST, MOVEMENT_NORMAL, MOVEMENT_SLOW, MOVEMENT_NON_MOVING)

# Well-formed delivered-sale rows, newest date guarded (internal constants).
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

# Days-of-stock and movement tier shared by SQL and Python so both agree.
# `t` is the joined source CTE exposing (product_row, stock, units_sold,
# avg_daily). Zero sales keep avg_daily / days_of_stock NULL in SQL, which the
# API layer renders as "No Sales" / infinity.
DAYS_OF_STOCK_SQL = (
    "CASE WHEN t.avg_daily > 0 "
    "THEN CEIL(t.stock / t.avg_daily) END"
)
_MOVEMENT_CASE_SQL = (
    "CASE"
    "  WHEN t.units_sold = 0 THEN 'NON MOVING'"
    f"  WHEN t.stock <= 0 THEN 'FAST MOVING'"
    f"  WHEN CEIL(t.stock / t.avg_daily) <= {FAST_MAX_DAYS} THEN 'FAST MOVING'"
    f"  WHEN CEIL(t.stock / t.avg_daily) <= {NORMAL_MAX_DAYS} THEN 'NORMAL'"
    f"  WHEN CEIL(t.stock / t.avg_daily) <= {SLOW_MAX_DAYS} THEN 'SLOW'"
    "  ELSE 'NON MOVING'"
    "END"
)

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
    is_out_of_stock    boolean NOT NULL DEFAULT false
)
"""

_CREATE_STATE_SQL = f"""
CREATE TABLE IF NOT EXISTS public.{STATE_TABLE} (
    id            integer PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    refreshed_at  double precision,
    window_start  date,
    window_end    date,
    product_count integer NOT NULL DEFAULT 0,
    fast_moving   integer NOT NULL DEFAULT 0,
    normal        integer NOT NULL DEFAULT 0,
    slow          integer NOT NULL DEFAULT 0,
    non_moving    integer NOT NULL DEFAULT 0,
    out_of_stock  integer NOT NULL DEFAULT 0,
    window_units  bigint  NOT NULL DEFAULT 0
)
"""

# Summary tiles only change when the metrics table is rebuilt, so their counts
# live on the state row and are read for free with it (no per-request 88k scan).
_STATE_ADD_COLUMN_SQLS = (
    "ALTER TABLE public.{t} ADD COLUMN IF NOT EXISTS fast_moving integer NOT NULL DEFAULT 0",
    "ALTER TABLE public.{t} ADD COLUMN IF NOT EXISTS normal integer NOT NULL DEFAULT 0",
    "ALTER TABLE public.{t} ADD COLUMN IF NOT EXISTS slow integer NOT NULL DEFAULT 0",
    "ALTER TABLE public.{t} ADD COLUMN IF NOT EXISTS non_moving integer NOT NULL DEFAULT 0",
    "ALTER TABLE public.{t} ADD COLUMN IF NOT EXISTS out_of_stock integer NOT NULL DEFAULT 0",
    "ALTER TABLE public.{t} ADD COLUMN IF NOT EXISTS window_units bigint NOT NULL DEFAULT 0",
)

_CREATE_INDEX_SQLS = (
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
    start_sql = f"({end_sql} - INTERVAL '{SALES_WINDOW_DAYS - 1} days')::date"
    return f"""
INSERT INTO public.{METRICS_TABLE} (
    product_key, product_name, main_category, sub_category,
    current_stock, sales_last_30_days, avg_daily_sales,
    days_of_stock, movement_status, is_out_of_stock
)
WITH s AS (
    SELECT o.product_id, SUM(o.quantity)::bigint AS units_sold
    FROM orders o
    WHERE o.delivery_status = 'Delivered'
      AND o.purchase_date ~ '^[0-9]{{2}}-[0-9]{{2}}-[0-9]{{4}}$'
      AND to_date(o.purchase_date, 'DD-MM-YYYY') BETWEEN {start_sql} AND {end_sql}
    GROUP BY o.product_id
),
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
)
SELECT
    (t.product_row).product_key,
    (t.product_row).name,
    (t.product_row).main_category,
    (t.product_row).sub_category,
    t.stock,
    t.units_sold,
    COALESCE(t.avg_daily, 0),
    {DAYS_OF_STOCK_SQL},
    {_MOVEMENT_CASE_SQL},
    t.stock <= 0
FROM t
"""


def ensure_schema():
    """Idempotently create the summary tables + supporting indexes."""
    with connection.cursor() as cursor:
        cursor.execute(_CREATE_METRICS_SQL)
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
    """Recompute every active product's metrics in one SQL statement.

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
            cursor.execute(f"TRUNCATE public.{METRICS_TABLE}")
            cursor.execute(_insert_sql(end_sql))
            inserted = cursor.rowcount
            # Compute the whole-table tier/summary counts exactly once (here),
            # then the dashboard reuses them from the state row on every read.
            cursor.execute(f"""
                SELECT COUNT(*) FILTER (WHERE movement_status = '{MOVEMENT_FAST}')::int,
                       COUNT(*) FILTER (WHERE movement_status = '{MOVEMENT_NORMAL}')::int,
                       COUNT(*) FILTER (WHERE movement_status = '{MOVEMENT_SLOW}')::int,
                       COUNT(*) FILTER (WHERE movement_status = '{MOVEMENT_NON_MOVING}')::int,
                       COUNT(*) FILTER (WHERE is_out_of_stock)::int,
                       COALESCE(SUM(sales_last_30_days), 0)::bigint
                FROM public.{METRICS_TABLE}
            """)
            fast_n, normal_n, slow_n, non_n, oos_n, win_units = cursor.fetchone()
            cursor.execute(f"""
                UPDATE public.{STATE_TABLE}
                   SET refreshed_at = EXTRACT(EPOCH FROM (now() AT TIME ZONE 'utc')),
                       window_start = ({end_sql} - INTERVAL '{SALES_WINDOW_DAYS - 1} days')::date,
                       window_end = ({end_sql}),
                       product_count = %s,
                       fast_moving = %s,
                       normal = %s,
                       slow = %s,
                       non_moving = %s,
                       out_of_stock = %s,
                       window_units = %s
                 WHERE id = 1
            """, [inserted, fast_n, normal_n, slow_n, non_n, oos_n, win_units])


def state_snapshot():
    # Trivial single-row read: the state row now carries the cached product
    # count and every summary-tile count, so the dashboard never re-scans the
    # metrics table for them. Returns None when the tables are not created yet
    # (fresh deploy), so ensure_fresh can build on demand.
    try:
        with connection.cursor() as cursor:
            cursor.execute(f"""
                SELECT refreshed_at, window_start::text, window_end::text,
                       product_count, fast_moving, normal, slow, non_moving,
                       out_of_stock, window_units
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
     fast_n, normal_n, slow_n, non_n, oos_n, win_units) = row
    return {
        'refreshed_at': float(refreshed_at) if refreshed_at is not None else None,
        'window_start': window_start,
        'window_end': window_end,
        'product_count': int(product_count or 0),
        'summary': {
            'fast_moving': int(fast_n or 0),
            'normal': int(normal_n or 0),
            'slow': int(slow_n or 0),
            'non_moving': int(non_n or 0),
            'out_of_stock': int(oos_n or 0),
            'window_units': int(win_units or 0),
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


def classify(stock, units, window_days=None):
    """Python mirror of the SQL classification (used by tests and callers)."""
    window_days = window_days or SALES_WINDOW_DAYS
    avg_daily = round(units / window_days, 2) if units else 0.0
    if units <= 0:
        return MOVEMENT_NON_MOVING, avg_daily, (None if stock > 0 else 0.0)
    if stock <= 0:
        return MOVEMENT_FAST, avg_daily, 0.0
    days = -(-stock // avg_daily)  # ceiling division, matching CEIL()
    if days <= FAST_MAX_DAYS:
        return MOVEMENT_FAST, avg_daily, float(days)
    if days <= NORMAL_MAX_DAYS:
        return MOVEMENT_NORMAL, avg_daily, float(days)
    if days <= SLOW_MAX_DAYS:
        return MOVEMENT_SLOW, avg_daily, float(days)
    return MOVEMENT_NON_MOVING, avg_daily, float(days)
