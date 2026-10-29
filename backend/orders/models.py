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

    There is no warehouse, shipping-address or payment table in this database,
    so none are modelled here - the API only reports what exists. Return
    reasons live in `public.returns`, modelled separately below.
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


class CustomerReturnRecord(models.Model):
    """Row of the existing `public.returns` table.

    The table arrived with the dataset (`return.csv` was imported into it) and
    records one return per (customer, product) pair: `return_id` is the primary
    key and the lookup columns are the natural keys used across the schema, so
    there is no order-line reference here - an order's return is found through
    its customer and product.

    `abuse_type` is an internal fraud/wardrobing classification. It is modelled
    so the column exists for backend analytics, but it must never be serialized
    into a customer-facing response.

    `customer` is not declared as a FK: `public.orders` already owns the
    (orderid) -> customers relationship used by `Order`, and a second managed
    FK to the same table from this unmodelled-row app would only add duplicate
    constraints Postgres cannot verify against existing data. The text column
    is enough for the customer-scoped read.
    """
    return_id = models.IntegerField(primary_key=True)
    customer_id = models.CharField(max_length=32, blank=True, null=True)
    product_id = models.CharField(max_length=32, blank=True, null=True)
    return_reason = models.CharField(max_length=255, blank=True, null=True)
    abuse_type = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        db_table = 'returns'
        managed = False
        ordering = ['return_id']

    def __str__(self):
        return f"Return {self.return_id} ({self.customer_id}/{self.product_id})"
