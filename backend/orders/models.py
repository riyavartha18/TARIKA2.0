from django.db import models

from accounts.models import Customer
from catalog.models import Product


class Order(models.Model):
    """Row of the existing `public.orders` table.

    The dataset records one product per order: `orderid` is the primary key and
    there is no separate order-items table, so the line details (product,
    quantity, prices) live on the order row itself. Column names that differ
    from the API keys are mapped with `db_column`, so the rest of the project
    keeps using `order_id`, `total_amount` and friends.

    `purchase_date` is TEXT in 'DD-MM-YYYY' form, which is why ordering uses a
    parsed date rather than the raw string.

    There is no warehouse, shipping-address, payment or return table in this
    database, so none are modelled here - the API only reports what exists.
    """
    order_id = models.CharField(max_length=32, primary_key=True, db_column='orderid')
    product = models.ForeignKey(
        Product,
        to_field='product_id',
        db_column='product_id',
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
        related_name='orders'
    )
    customer = models.ForeignKey(
        Customer,
        to_field='customer_id',
        db_column='customer_id',
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
        related_name='customer_orders'
    )

    quantity = models.BigIntegerField(blank=True, null=True)
    # `initial_price` is the unit price before the order's own discount.
    initial_price = models.FloatField(blank=True, null=True)
    additional_discount = models.FloatField(blank=True, null=True)
    # `final_price` is what the customer paid for the line - the order total.
    final_price = models.FloatField(blank=True, null=True)

    purchase_date = models.CharField(max_length=32, blank=True, null=True)
    delivery_status = models.CharField(max_length=50, blank=True, null=True)
    shipping_time_days = models.BigIntegerField(blank=True, null=True)
    payment_method = models.CharField(max_length=50, blank=True, null=True)
    rating = models.FloatField(blank=True, null=True)

    class Meta:
        db_table = 'orders'
        managed = False
        ordering = ['-order_id']

    @property
    def total_amount(self):
        return self.final_price

    @property
    def order_status(self):
        """The forward status word the customer pages classify on."""
        return Order.DELIVERY_STATUS_MAP.get(
            (self.delivery_status or '').strip().lower(), 'processing'
        )

    # public.orders has no status column of its own; delivery_status carries the
    # only real progression signal (Delivered / In Transit / Delayed / Returned)
    # and is mapped onto the vocabulary the frontend already understands.
    DELIVERY_STATUS_MAP = {
        'delivered': 'delivered',
        'in transit': 'shipped',
        'delayed': 'processing',
        'returned': 'returned',
    }

    def __str__(self):
        return f"Order {self.order_id}"
