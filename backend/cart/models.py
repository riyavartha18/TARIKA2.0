from django.db import models


class WishlistItem(models.Model):
    id = models.BigAutoField(primary_key=True)
    customer = models.ForeignKey(
        'accounts.Customer',
        to_field='customer_id',
        db_column='customer_id',
        on_delete=models.CASCADE,
        related_name='wishlist_items'
    )
    product = models.ForeignKey(
        'catalog.Product',
        to_field='product_id',
        db_column='product_id',
        on_delete=models.CASCADE,
        related_name='wishlist_items'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'wishlist_items'
        managed = False
        ordering = ['-created_at']
        unique_together = ('customer', 'product')

    def __str__(self):
        return f"Wishlist: Customer {self.customer_id} -> Product {self.product_id}"


class CartItem(models.Model):
    id = models.BigAutoField(primary_key=True)
    customer = models.ForeignKey(
        'accounts.Customer',
        to_field='customer_id',
        db_column='customer_id',
        on_delete=models.CASCADE,
        related_name='cart_items'
    )
    product = models.ForeignKey(
        'catalog.Product',
        to_field='product_id',
        db_column='product_id',
        on_delete=models.CASCADE,
        related_name='cart_items'
    )
    quantity = models.IntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'cart_items'
        managed = False
        ordering = ['-created_at']
        unique_together = ('customer', 'product')

    def __str__(self):
        return f"Cart: Customer {self.customer_id} -> Product {self.product_id} (Qty: {self.quantity})"
