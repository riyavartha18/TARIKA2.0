"""
services.py
-----------
Revenue Forecasting orchestration layer.

This service does NOT implement a second demand model. It consumes the two
outputs that already exist in the project:

  1. ``stock_to_be_ordered.services.forecasting.run_stock_forecast``
        -> predicted sales QUANTITY per product_key (OLS Multiple Linear
           Regression over the existing fact_demand / dim_time warehouse).

  2. ``demand_prediction.engine.DecisionTreeEngine.run_pipeline``
        -> predicted demand TIER (High / Medium / Low) per product_key
           (manual Decision Tree classifier).

It reads ``selling_price`` from ``dim_product`` and converts predicted sales
into expected revenue using the Decimal logic in ``revenue_forecast.py``.

Data flow:
    Supabase (fact_demand, dim_product, dim_time)
        -> existing Demand Prediction / Stock Forecast
        -> predicted sales quantity
        -> Revenue Forecasting (this module)
        -> expected_revenue = predicted_sales * selling_price
        -> Django API -> React Admin Analysis
"""
from django.db import connection

from stock_to_be_ordered.services.forecasting import run_stock_forecast
from demand_prediction.engine import DecisionTreeEngine

from revenue_forecasting.revenue_forecast import (
    build_product_forecast,
    summarise_forecast,
)


def get_selling_price_map():
    """
    Build a ``{product_key: selling_price}`` map from the existing schema.

    Uses the existing ``dim_product`` row as the single source of truth for
    selling price, keyed by its warehouse product key.
    """
    price_map = {}
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT
                dp.product_key,
                dp.selling_price
            FROM dim_product dp
        """)
        for product_key, selling_price in cursor.fetchall():
            price_map[product_key] = selling_price
    return price_map


def get_demand_tier_map():
    """
    Build a ``{product_key: 'High'|'Medium'|'Low'}`` map by reusing the existing
    Demand Prediction classifier output.

    Wrapped defensively: revenue forecasting must still work (using predicted
    sales quantities alone) even if the demand-tier pipeline is unavailable.
    """
    tier_map = {}
    try:
        results = DecisionTreeEngine.run_pipeline()
        if results.get('success'):
            for pred in results.get('product_predictions', []):
                tier_map[pred.get('product_key')] = pred.get('predicted_demand')
    except Exception:
        # A tier lookup failure must never break the revenue forecast.
        tier_map = {}
    return tier_map


def run_revenue_forecast():
    """
    Full end-to-end Revenue Forecasting pipeline.

    Returns a dict::

        {
            'success': bool,
            'error': str | None,
            'forecast_month': '2026-10',
            'forecast_month_label': 'October 2026',
            'summary': {...},          # aggregate metrics + category breakdown
            'products': [ {...}, ... ] # product-level forecast rows
        }
    """
    # 1. Reuse the existing predicted-sales quantity pipeline (never re-modelled).
    stock_forecast = run_stock_forecast()
    if not stock_forecast.get('success'):
        return {
            'success': False,
            'error': stock_forecast.get('error') or 'Upstream demand forecast unavailable.',
        }

    forecast_products = stock_forecast.get('products', [])
    forecast_month = stock_forecast.get('forecast_month')
    forecast_month_label = stock_forecast.get('forecast_month_label')

    # 2. Reuse the existing demand-tier classifier output (optional enrichment).
    tier_map = get_demand_tier_map()

    # 3. Existing selling prices keyed by product_key.
    price_map = get_selling_price_map()

    # 4. Convert predicted sales -> expected revenue (Decimal, in Python).
    product_rows = []
    for product in forecast_products:
        product_key = product.get('product_key')
        predicted_sales = product.get('predicted_demand')  # existing quantity output
        selling_price = price_map.get(product_key)
        predicted_demand = tier_map.get(product_key)

        product_rows.append(
            build_product_forecast(
                product=product,
                predicted_sales=predicted_sales,
                selling_price=selling_price,
                predicted_demand=predicted_demand,
            )
        )

    # 5. Aggregate summary metrics (all in Python).
    summary = summarise_forecast(product_rows)
    summary['forecast_month'] = forecast_month
    summary['forecast_month_label'] = forecast_month_label

    return {
        'success': True,
        'error': None,
        'forecast_month': forecast_month,
        'forecast_month_label': forecast_month_label,
        'summary': summary,
        'products': product_rows,
    }
