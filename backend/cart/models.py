from django.db import models


class WishlistItem(models.Model):
    """Row in the existing `public.wishlist` table.

    Real columns: wishkey (text PK), customer_id, product_id. `wishkey` has no
    sequence or default, so the service layer allocates it in the existing
    'WISH#######' format. There is no timestamp column, so ordering is by
    wishkey, which is allocated sequentially (zero-padded) and therefore
    newest-first when read in descending order.
    """
    wishkey = models.CharField(max_length=32, primary_key=True)
    customer = models.ForeignKey(
        'accounts.Customer',
        to_field='customer_id',
        db_column='customer_id',
        on_delete=models.DO_NOTHING,
        related_name='wishlist_items'
    )
    product = models.ForeignKey(
        'catalog.Product',
        to_field='product_id',
        db_column='product_id',
        on_delete=models.DO_NOTHING,
        related_name='wishlist_items'
    )

    class Meta:
        db_table = 'wishlist'
        managed = False
        ordering = ['-wishkey']

    def __str__(self):
        return f"Wishlist: Customer {self.customer_id} -> Product {self.product_id}"


class CartItem(models.Model):
    """Row in the existing `public.cart` table.

    Real columns: cartkey (text PK), customer_id, product_id, quantity. One
    line per customer + product (enforced by the unique index added by
    `manage.py ensure_ecommerce_indexes`), so quantity changes update the row
    instead of inserting duplicates.
    """
    cartkey = models.CharField(max_length=32, primary_key=True)
    customer = models.ForeignKey(
        'accounts.Customer',
        to_field='customer_id',
        db_column='customer_id',
        on_delete=models.DO_NOTHING,
        related_name='cart_items'
    )
    product = models.ForeignKey(
        'catalog.Product',
        to_field='product_id',
        db_column='product_id',
        on_delete=models.DO_NOTHING,
        related_name='cart_items'
    )
    quantity = models.IntegerField(default=1)

    class Meta:
        db_table = 'cart'
        managed = False
        ordering = ['-cartkey']

    def __str__(self):
        return f"Cart: Customer {self.customer_id} -> Product {self.product_id} (Qty: {self.quantity})"
