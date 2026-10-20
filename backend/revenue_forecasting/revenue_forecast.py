"""
revenue_forecast.py
-------------------
Core, reusable Revenue Forecasting business logic (pure Python + Decimal).

The fundamental calculation is:

    expected_revenue = predicted_sales * selling_price

This module deliberately keeps ALL currency arithmetic in Python using
``decimal.Decimal`` so the React frontend never re-implements (or re-rounds)
business logic and never introduces floating-point inaccuracies.

Design rules honoured here:
  * No hard-coded HIGH/MEDIUM/LOW -> units mappings. The predicted sales
    quantity is always supplied by the caller (the existing demand
    prediction / stock forecasting pipeline).
  * Robust handling of missing predicted sales, missing selling price,
    zero values, negative values and invalid / null products.
  * Indian Rupee amounts are whole rupees in this catalog (selling_price is
    stored as an integer), so results are quantised to integer rupees while
    still using Decimal arithmetic end-to-end.
"""
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation


# Whole-rupee precision (catalog prices are integers). Kept as a constant so
# the rounding convention lives in exactly one place.
RUPEE = Decimal('1')


def _to_decimal(value):
    """
    Safely coerce an arbitrary input into a non-negative ``Decimal``.

    Returns ``None`` when the value is missing or cannot be interpreted as a
    number, so callers can distinguish "no data" from a genuine zero.
    """
    if value is None:
        return None
    if isinstance(value, Decimal):
        dec = value
    else:
        try:
            # Normalise to string first so floats don't leak binary error.
            dec = Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError):
            return None
    if dec < 0:
        # Negative sales / prices are never meaningful for a forecast.
        return Decimal('0')
    return dec


def calculate_expected_revenue(predicted_sales, selling_price):
    """
    Calculate expected revenue for a single product.

        expected_revenue = predicted_sales * selling_price

    Args:
        predicted_sales: predicted unit quantity (from the existing demand
            prediction / regression pipeline). May be None / invalid.
        selling_price: expected selling price in INR. May be None / invalid.

    Returns:
        ``Decimal`` expected revenue quantised to whole rupees. Returns
        ``Decimal('0')`` when either input is missing, invalid or zero, so a
        product with incomplete data never breaks the aggregate forecast.
    """
    sales = _to_decimal(predicted_sales)
    price = _to_decimal(selling_price)

    if sales is None or price is None:
        return Decimal('0')

    revenue = sales * price
    return revenue.quantize(RUPEE, rounding=ROUND_HALF_UP)


def build_product_forecast(product, predicted_sales, selling_price, predicted_demand=None):
    """
    Assemble a single product-level revenue forecast record.

    Keeps the per-product shape consistent for the API layer and the admin UI.

    Args:
        product: dict carrying identity/dimension fields (product_key,
            product_id, product_name, category_name, color, size, ...).
        predicted_sales: predicted unit quantity (existing model output).
        selling_price: expected selling price in INR.
        predicted_demand: optional demand tier label (High/Medium/Low) coming
            from the existing Demand Prediction classifier.

    Returns:
        dict with normalised numeric fields plus ``expected_revenue``.
    """
    product = product or {}

    sales_dec = _to_decimal(predicted_sales)
    price_dec = _to_decimal(selling_price)
    revenue_dec = calculate_expected_revenue(predicted_sales, selling_price)

    has_price = price_dec is not None and price_dec > 0
    has_sales = sales_dec is not None and sales_dec > 0

    return {
        'product_key': product.get('product_key'),
        'product_id': product.get('product_id'),
        'product_name': product.get('product_name') or (
            f"Product #{product.get('product_key')}" if product.get('product_key') is not None else 'Unknown Product'
        ),
        'category_name': product.get('category_name') or 'General Catalog',
        'color': product.get('color') or '',
        'size': product.get('size') or '',
        'predicted_demand': predicted_demand or 'Unrated',
        'predicted_sales': int(sales_dec) if sales_dec is not None else 0,
        'selling_price': int(price_dec) if price_dec is not None else 0,
        'expected_revenue': int(revenue_dec),
        'current_stock': product.get('current_stock', 0),
        # Flags let the UI explain why a row forecasts to zero without the
        # frontend having to re-derive business rules.
        'has_selling_price': has_price,
        'has_predicted_sales': has_sales,
    }


def summarise_forecast(product_rows):
    """
    Aggregate product-level rows into the summary metrics + category breakdown
    consumed by the Admin Analysis card and detailed view.

    All aggregation happens in Python (Decimal) so totals always reconcile with
    the per-product figures.
    """
    total_predicted_units = 0
    total_expected_revenue = Decimal('0')
    high_demand_products = 0
    forecastable_products = 0

    category_totals = {}

    for row in product_rows:
        revenue = Decimal(row.get('expected_revenue') or 0)
        units = int(row.get('predicted_sales') or 0)

        total_predicted_units += units
        total_expected_revenue += revenue

        if str(row.get('predicted_demand', '')).lower() == 'high':
            high_demand_products += 1

        if revenue > 0:
            forecastable_products += 1

        cat = row.get('category_name') or 'General Catalog'
        bucket = category_totals.setdefault(
            cat, {'category_name': cat, 'predicted_units': 0, 'expected_revenue': Decimal('0'), 'product_count': 0}
        )
        bucket['predicted_units'] += units
        bucket['expected_revenue'] += revenue
        bucket['product_count'] += 1

    # Finalise category breakdown: sort by revenue contribution descending.
    category_breakdown = []
    for bucket in category_totals.values():
        rev = bucket['expected_revenue'].quantize(RUPEE, rounding=ROUND_HALF_UP)
        share = Decimal('0')
        if total_expected_revenue > 0:
            share = ((rev / total_expected_revenue) * Decimal('100')).quantize(
                Decimal('0.1'), rounding=ROUND_HALF_UP
            )
        category_breakdown.append({
            'category_name': bucket['category_name'],
            'product_count': bucket['product_count'],
            'predicted_units': bucket['predicted_units'],
            'expected_revenue': int(rev),
            'revenue_share_percent': float(share),
        })
    category_breakdown.sort(key=lambda c: c['expected_revenue'], reverse=True)

    # Top revenue-contributing products (already whole-rupee ints).
    top_products = sorted(
        product_rows, key=lambda r: r.get('expected_revenue', 0), reverse=True
    )[:5]

    return {
        'total_products_forecasted': len(product_rows),
        'forecastable_products': forecastable_products,
        'total_predicted_units': total_predicted_units,
        'total_expected_revenue': int(total_expected_revenue.quantize(RUPEE, rounding=ROUND_HALF_UP)),
        'high_demand_products': high_demand_products,
        'category_breakdown': category_breakdown,
        'top_products': [
            {
                'product_key': p.get('product_key'),
                'product_name': p.get('product_name'),
                'category_name': p.get('category_name'),
                'predicted_sales': p.get('predicted_sales'),
                'selling_price': p.get('selling_price'),
                'expected_revenue': p.get('expected_revenue'),
            }
            for p in top_products
        ],
    }
