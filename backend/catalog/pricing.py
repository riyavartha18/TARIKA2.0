from django.db import connection


def get_dim_product_selling_price_map(product_ids):
    """Return selling prices keyed by product_id from the warehouse dimension."""
    normalized_ids = list(dict.fromkeys(
        str(product_id) for product_id in product_ids if product_id is not None
    ))
    if not normalized_ids:
        return {}

    placeholders = ', '.join(['%s'] * len(normalized_ids))
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
                SELECT product_id, selling_price
                FROM dim_product
                WHERE product_id IN ({placeholders})
            """,
            normalized_ids,
        )
        return {
            str(product_id): selling_price
            for product_id, selling_price in cursor.fetchall()
        }