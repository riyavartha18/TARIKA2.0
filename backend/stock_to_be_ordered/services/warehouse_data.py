"""
warehouse_data.py
-----------------
Fetches and aggregates existing Data Warehouse historical demand data
from: fact_demand, dim_time, dim_product, dim_category
No new warehouse is created - reuses existing schema.

Optimised: single query fetches all required data with JOIN in one pass.
"""
from django.db import connection
from collections import defaultdict


def get_latest_historical_month():
    """
    Queries fact_demand + dim_time to determine the latest available
    year and month in the Data Warehouse. Returns (year, month, month_name).
    """
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT dt.year, dt.month, dt.month_name, dt.month_start
            FROM fact_demand fd
            JOIN dim_time dt ON fd.time_key = dt.time_key
            WHERE dt.year IS NOT NULL AND dt.month IS NOT NULL
            ORDER BY dt.year DESC, dt.month DESC
            LIMIT 1
        """)
        row = cursor.fetchone()

    if not row:
        return None

    return {
        'year': row[0],
        'month': row[1],
        'month_name': row[2],
        'month_start': row[3],
    }


def get_next_forecast_month(latest):
    """
    Given the latest historical month dict, returns the next month dict.
    Dynamically handles December → January year-rollover.
    """
    MONTH_NAMES = [
        'January', 'February', 'March', 'April', 'May', 'June',
        'July', 'August', 'September', 'October', 'November', 'December'
    ]
    year = latest['year']
    month = latest['month']

    if month == 12:
        next_month_num = 1
        next_year = year + 1
    else:
        next_month_num = month + 1
        next_year = year

    return {
        'year': next_year,
        'month': next_month_num,
        'month_name': MONTH_NAMES[next_month_num - 1],
        'period_str': f"{next_year}-{next_month_num:02d}",
    }


def get_historical_demand_records():
    """
    Fetches all historical demand records ordered by product and month.
    Returns a list of dicts:
      product_key, product_id, product_name, category_name,
      month_start (date), month_num, year,
      units_sold, cart_quantity, wishlist_count, discount_amount,
      discount_percentage
    """
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT
                fd.product_key,
                dp.product_id,
                COALESCE(dp.product_name, CONCAT('Product #', fd.product_key)) AS product_name,
                COALESCE(dc.category_name, 'General Catalog') AS category_name,
                dt.month_start,
                dt.month,
                dt.year,
                COALESCE(p.base_price, dp.selling_price, 0),
                fd.units_sold,
                fd.cart_quantity,
                fd.wishlist_count,
                fd.discount_amount
            FROM fact_demand fd
            JOIN dim_time dt ON fd.time_key = dt.time_key
            LEFT JOIN dim_product dp ON fd.product_key = dp.product_key
            LEFT JOIN products p ON dp.product_id = p.product_id
            LEFT JOIN dim_category dc ON fd.category_key = dc.category_key
            WHERE dt.year IS NOT NULL AND dt.month IS NOT NULL
            ORDER BY fd.product_key ASC, dt.month_start ASC
        """)
        rows = cursor.fetchall()

    records = []
    for r in rows:
        records.append({
            'product_key': r[0],
            'product_id': r[1],
            'product_name': r[2],
            'category_name': r[3],
            'month_start': r[4],
            'month_num': int(r[5]),
            'year': int(r[6]),
            'units_sold': float(r[8] or 0),
            'cart_quantity': float(r[9] or 0),
            'wishlist_count': float(r[10] or 0),
            'discount_amount': float(r[11] or 0),
            'discount_percentage': (
                min(100.0, max(0.0, float(r[11] or 0) / float(r[7]) * 100))
                if r[7] and float(r[7]) > 0 else 0.0
            ),
        })

    return records


def group_records_by_product(records):
    """
    Groups historical demand records by product_key.
    Returns a dict: { product_key -> [record, record, ...] }
    where each product's records are sorted by month_start ascending.
    """
    product_map = defaultdict(list)
    for rec in records:
        product_map[rec['product_key']].append(rec)

    # Sort each product's records by month_start
    for pkey in product_map:
        product_map[pkey].sort(key=lambda x: x['month_start'])

    return dict(product_map)


def get_all_active_catalog_products():
    """
    Returns all products from dim_product + dim_category, including current_stock,
    color, and size from the product dimension.

    Each row is a unique product variant (color × size), because dim_product.product_key
    maps 1-to-1 with the SKU-level products row.

    current_stock is sourced directly from dim_product.current_stock.
    color and size are sourced directly from dim_product.
    """
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT
                dp.product_key,
                dp.product_id,
                dp.product_name,
                COALESCE(dc.category_name, 'General Catalog') AS category_name,
                COALESCE(dp.current_stock, 0)                 AS current_stock,
                COALESCE(dp.color, '')                         AS color,
                COALESCE(dp.size, '')                          AS size
            FROM dim_product dp
            LEFT JOIN dim_category dc ON dp.category_id = dc.category_id
            ORDER BY dp.product_key ASC
        """)
        rows = cursor.fetchall()

    return [
        {
            'product_key':  r[0],
            'product_id':   r[1],
            'product_name': r[2],
            'category_name': r[3],
            'current_stock': int(r[4]) if r[4] is not None else 0,
            'color': r[5] or '',
            'size':  r[6] or '',
        }
        for r in rows
    ]
