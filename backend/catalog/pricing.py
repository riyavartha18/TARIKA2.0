from django.db import connection

from .models import parse_product_price


def get_product_selling_price_map(product_ids):
    """Return the effective selling price for products, keyed by product id.

    The real `public.products` table keeps the ORIGINAL price in the TEXT
    `actual_price` column and the FINAL price the customer pays in the numeric
    `discounted_price` column (verified: `discounted_price` equals
    `actual_price - discount_price` on every row). So the selling price is
    `discounted_price`, falling back to the parsed TEXT price for a row that has
    no discounted value — never `discount_price`, which is the discount AMOUNT
    in currency. Values are floats and missing products are simply absent from
    the map, letting callers decide how to treat an unknown price. Parsing
    happens in Python (via the shared helper) so the query stays
    vendor-neutral.
    """
    normalized_ids = list(dict.fromkeys(
        str(product_id) for product_id in product_ids if product_id is not None
    ))
    if not normalized_ids:
        return {}

    placeholders = ', '.join(['%s'] * len(normalized_ids))
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
                SELECT product_key, discounted_price, actual_price
                FROM public.products
                WHERE product_key IN ({placeholders})
            """,
            normalized_ids,
        )
        selling_map = {}
        for product_key, discounted_price, actual_price_raw in cursor.fetchall():
            final_price = (
                float(discounted_price)
                if discounted_price is not None
                else parse_product_price(actual_price_raw)
            )
            if final_price is not None:
                selling_map[str(product_key)] = final_price
        return selling_map


def resolve_product_prices(initial_price, discount_price=None, final_price=None):
    """Authoritatively resolve the three product price fields.

    Stored layout of `public.products`, documented on the Product model:
    the TEXT `actual_price` column is the ORIGINAL price, `discount_price` is a
    currency AMOUNT (never a percentage) and `discounted_price` is the FINAL
    selling price, i.e. ``discounted_price = actual_price - discount_price``.
    The percentage is always derived from the two prices, never stored.

    Accepts either input method used by the warehouse UI:
      * discount amount given, final missing -> final = initial - amount
      * final selling price given, amount missing -> amount = initial - final
      * both given -> they must agree to the cent (synchronised inputs)

    Returns a dict {'initial_price', 'discount_price', 'final_price',
    'discount_percentage'} rounded to 2 decimal places, or raises
    ValueError with a field-oriented message on invalid input. A missing /
    zero initial price is handled safely (percentage 0.0, never divides).
    """
    def _clean(value, label):
        if value is None:
            return None
        value = float(value)
        if value != value or value in (float('inf'), float('-inf')):  # NaN/inf
            raise ValueError(f'{label} must be a finite number.')
        return value

    initial = _clean(initial_price, 'Initial price')
    amount = _clean(discount_price, 'Discount amount')
    final = _clean(final_price, 'Discounted price')

    if initial is not None and initial < 0:
        raise ValueError('Initial price cannot be negative.')
    if amount is not None and amount < 0:
        raise ValueError('Discount amount cannot be negative.')
    if final is not None and final < 0:
        raise ValueError('Discounted price cannot be negative.')

    if initial is not None:
        if amount is not None and amount > initial:
            raise ValueError('Discount amount cannot exceed the original price.')
        if final is not None and final > initial:
            raise ValueError('Discounted price cannot exceed the original price.')

    if amount is not None and final is not None:
        # Both input methods submitted: they must describe the same product
        # price (the UI keeps them synchronised; disagreement is a bug).
        if initial is not None:
            derived_final = round(initial - amount, 2)
            if abs(derived_final - final) > 0.01:
                raise ValueError(
                    'Discount amount and discounted price disagree: '
                    'discounted price must equal initial price minus discount amount.'
                )
        resolved_final = final
        resolved_amount = amount
    elif amount is not None:
        base = initial
        if base is None:
            raise ValueError('Initial price is required to compute the discounted price.')
        resolved_amount = amount
        resolved_final = round(max(0.0, base - amount), 2)
    elif final is not None:
        base = initial
        if base is None:
            raise ValueError('Initial price is required to compute the discount amount.')
        resolved_final = round(final, 2)
        resolved_amount = round(base - resolved_final, 2)
    else:
        # Nothing to resolve: derive the final price from what is stored.
        if initial is None:
            raise ValueError('Initial price is required.')
        resolved_amount = 0.0
        resolved_final = round(initial, 2)

    resolved_initial = round(initial, 2) if initial is not None else None
    # Percentage from the two prices rather than from the amount column, so the
    # badge can never disagree with the prices it sits beside. Never negative.
    discount_value = 0.0
    if resolved_initial is not None:
        discount_value = max(0.0, round(resolved_initial - resolved_final, 2))
    percentage = (
        round(min(discount_value / resolved_initial * 100, 100.0), 2)
        if resolved_initial and resolved_initial > 0 else 0.0
    )
    return {
        'initial_price': resolved_initial,
        'discount_price': round(resolved_amount, 2),
        'final_price': round(resolved_final, 2),
        'discount_percentage': percentage,
    }
