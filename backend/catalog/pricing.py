from django.db import connection


def get_dim_product_selling_price_map(product_ids):
    """Return the effective selling price for products, keyed by product id.

    The real `public.products` table stores the current price in
    `discount_price` (there is no `selling_price` column), so that is what the
    map returns. Values are floats and missing products are simply absent from
    the map, letting callers decide how to treat an unknown price.
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
                SELECT product_key, discount_price
                FROM public.products
                WHERE product_key IN ({placeholders})
            """,
            normalized_ids,
        )
        return {
            str(product_key): discount_price
            for product_key, discount_price in cursor.fetchall()
        }
