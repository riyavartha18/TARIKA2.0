"""
forecasting.py
--------------
Orchestrates product-wise next-month demand forecasting using:
  warehouse_data  → fetches historical DW records + current_stock from dim_product
  feature_builder → builds regression features (no future data leakage)
  regression      → OLS Multiple Linear Regression

Flow:
  1. Detect latest historical month dynamically
  2. Calculate next forecast month
  3. Fetch all historical records from DW (one efficient query)
  4. Fetch all catalog products with current_stock from dim_product
  5. For each product:
       a. Build training dataset (X, Y)
       b. If insufficient data → use avg or fallback
       c. Else → fit OLS, predict next-month demand
  6. Compute need_to_order = max(0, predicted_demand - current_stock)
  7. Return clean, minimal API payload

Performance notes:
  - All DB queries are bulk (no N+1 queries)
  - Regression runs once per product, not per request for same month
  - Fallback: products with insufficient data use their last known demand
"""

from stock_to_be_ordered.services.warehouse_data import (
    get_latest_historical_month,
    get_next_forecast_month,
    get_historical_demand_records,
    group_records_by_product,
    get_all_active_catalog_products,
)
from stock_to_be_ordered.services.feature_builder import (
    build_training_dataset,
    build_prediction_features,
    MIN_HISTORY_MONTHS,
)
from stock_to_be_ordered.services.regression import run_regression


def run_stock_forecast():
    """
    Full end-to-end pipeline for Stock to Be Ordered.

    Returns a dict:
    {
        'success': bool,
        'error': str | None,
        'forecast_month': '2026-10',        ← YYYY-MM for the UI header
        'forecast_month_label': 'October 2026',
        'products': [
            {
                'product_key': int,         ← SKU-level key (unique per color/size)
                'product_id': str,
                'product_name': str,
                'color': str,               ← from operational products table
                'size': str,                ← from operational products table
                'current_stock': int,       ← from dim_product.current_stock
                'predicted_demand': int,    ← OLS regression result
                'need_to_order': int,       ← max(0, predicted - current)
            },
            ...
        ]
    }
    """
    # 1. Determine the latest available month in the DW
    latest = get_latest_historical_month()
    if not latest:
        return {
            'success': False,
            'error': 'No historical data found in fact_demand table.',
        }

    # 2. Compute next (forecast) month
    next_month = get_next_forecast_month(latest)
    forecast_label = f"{next_month['month_name']} {next_month['year']}"

    # 3. Fetch all historical DW records in ONE bulk query
    all_records = get_historical_demand_records()
    if not all_records:
        return {
            'success': False,
            'error': 'No records returned from fact_demand.',
        }

    product_record_map = group_records_by_product(all_records)

    # 4. Fetch all catalog products with current_stock (ONE bulk query)
    catalog_products = get_all_active_catalog_products()

    # 5. Forecast each product
    products_out = []

    for product in catalog_products:
        p_key = product['product_key']
        p_id = str(product['product_id']) if product['product_id'] else str(p_key)
        p_name = product['product_name'] or f'Product #{p_key}'
        current_stock = product['current_stock']

        sorted_records = product_record_map.get(p_key, [])
        n_months = len(sorted_records)

        predicted_demand = None

        if n_months >= MIN_HISTORY_MONTHS:
            # Build training dataset
            X_matrix, Y_vector = build_training_dataset(sorted_records)

            if len(X_matrix) >= 2:
                # Build prediction feature vector from the latest available month
                x_predict = build_prediction_features(sorted_records)
                if x_predict is not None:
                    try:
                        result = run_regression(X_matrix, Y_vector, x_predict)
                        if result['predicted_demand'] is not None:
                            predicted_demand = result['predicted_demand']
                    except Exception:
                        pass

        # Fallback: use last known demand if regression failed or insufficient data
        if predicted_demand is None:
            if sorted_records:
                # Use average of last 3 months (or fewer) as a simple fallback
                tail = sorted_records[-3:]
                predicted_demand = max(0, round(
                    sum(r['units_sold'] for r in tail) / len(tail)
                ))
            else:
                predicted_demand = 0

        # 6. Compute need_to_order
        need_to_order = max(0, predicted_demand - current_stock)

        products_out.append({
            'product_key':      p_key,
            'product_id':       p_id,
            'product_name':     p_name,
            'category_name':    product.get('category_name', ''),
            'color':            product.get('color', ''),
            'size':             product.get('size', ''),
            'current_stock':    current_stock,
            'predicted_demand': predicted_demand,
            'need_to_order':    need_to_order,
        })

    return {
        'success': True,
        'error': None,
        'forecast_month': next_month['period_str'],       # e.g. "2026-10"
        'forecast_month_label': forecast_label,           # e.g. "October 2026"
        'products': products_out,
    }
