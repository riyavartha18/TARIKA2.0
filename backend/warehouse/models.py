from django.db import models

from accounts.models import Warehouse, Employee, Customer
from catalog.models import Category, Product, Inventory, Manufacturer, OrderItem


class Order(models.Model):
    """Row of the real ``public.orders`` table.

    The dataset records **one product per order row** (``orderid`` is the primary
    key and there is no order-items table), so the line details — product,
    quantity and prices — live on the order itself. Column names that differ from
    the keys the warehouse API already returns are mapped with ``db_column`` /
    properties, so the serializers and the React dashboard keep speaking
    ``order_id``, ``total_amount`` and ``order_status``.

    Verified against the connected Neon database:

    ======================  ====================================================
    real column             meaning
    ======================  ====================================================
    ``orderid``             order reference (e.g. ``ORD0103473``)
    ``product_id``          ``products.product_key``
    ``customer_id``         ``customers.customer_id``
    ``quantity``            units on the line
    ``initial_price``       line price before the order's own discount
    ``additional_discount`` coupon amount applied to the line
    ``final_price``         what the customer paid for the line (the order total)
    ``purchase_date``       TEXT in ``DD-MM-YYYY`` form
    ``delivery_status``     ``Delivered`` / ``In Transit`` / ``Returned``
    ``shipping_time_days``  promised transit time
    ``payment_method``      e.g. UPI / Credit Card / Cash on Delivery
    ``rating``              customer rating of the purchased product
    ======================  ====================================================

    There is no ``order_status``, ``payment_status``, ``warehouse_id``,
    ``shipping_address``, ``created_at`` or ``updated_at`` column, and no
    ``deliveries`` table. Those keys are therefore reported as ``None`` instead
    of being invented, and the only real fulfilment signal this schema carries is
    ``delivery_status`` — which is what ``order_status`` is derived from.
    """
    order_id = models.CharField(max_length=32, primary_key=True, db_column='orderid')
    product = models.ForeignKey(
        Product,
        to_field='product_id',
        db_column='product_id',
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
        related_name='warehouse_orders'
    )
    customer = models.ForeignKey(
        Customer,
        to_field='customer_id',
        db_column='customer_id',
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
        related_name='warehouse_orders'
    )

    quantity = models.BigIntegerField(blank=True, null=True)
    initial_price = models.FloatField(blank=True, null=True)
    additional_discount = models.FloatField(blank=True, null=True)
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

    # The only real progression signal in this schema, mapped onto the status
    # words the warehouse dashboard already classifies on.
    DELIVERY_STATUS_MAP = {
        'delivered': 'delivered',
        'in transit': 'shipped',
        'delayed': 'processing',
        'returned': 'returned',
    }

    @property
    def order_date(self):
        """Real purchase date (TEXT ``DD-MM-YYYY`` in the dataset)."""
        return self.purchase_date

    @property
    def order_status(self):
        """Derived from ``delivery_status``; never a stored column here."""
        return Order.DELIVERY_STATUS_MAP.get(
            (self.delivery_status or '').strip().lower(), 'processing'
        )

    @property
    def total_amount(self):
        """The line total the customer actually paid."""
        return self.final_price

    @property
    def discount_amount(self):
        """Coupon amount taken off this line."""
        return self.additional_discount

    @property
    def item_count(self):
        """One product per row, so the item count is the ordered quantity."""
        return int(self.quantity or 0)

    @property
    def customer_name(self):
        return self.customer.customer_name if self.customer else None

    @property
    def customer_email(self):
        return self.customer.email if self.customer else None

    @property
    def product_name(self):
        return self.product.product_name if self.product else None

    def __str__(self):
        return f"Order {self.order_id} ({self.order_status})"


class Return(models.Model):
    """Row of the real ``public.returns`` table.

    The dataset imported ``return.csv`` into this table, and it records one
    return per (customer, product) pair:

    ==================  =========================================================
    real column         meaning
    ==================  =========================================================
    ``return_id``       integer reference, unique per return
    ``customer_id``     ``customers.customer_id``
    ``product_id``      ``products.product_key``
    ``return_reason``   e.g. 'Defective/Broken', 'Wrong Item Sent', 'Too Large'
    ``abuse_type``      internal fraud classification ('Legitimate',
                        'Wardrobing', 'Fraudulent Return', …)
    ==================  =========================================================

    There is no ``return_status``, ``return_date``, ``refund_amount``,
    ``condition_on_return``, pickup or courier column, and no link to an order
    row — an order is only inferable from (customer, product), which is not
    unique. Those keys are reported as ``None`` rather than fabricated, and the
    accept / reject / pickup workflow cannot be persisted against this schema
    (see ``WarehouseService.RETURN_WORKFLOW_UNAVAILABLE``).
    """
    return_id = models.IntegerField(primary_key=True)
    customer = models.ForeignKey(
        Customer,
        to_field='customer_id',
        db_column='customer_id',
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
        related_name='warehouse_returns'
    )
    product = models.ForeignKey(
        Product,
        to_field='product_id',
        db_column='product_id',
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
        related_name='warehouse_returns'
    )
    return_reason = models.CharField(max_length=255, blank=True, null=True)
    abuse_type = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        db_table = 'returns'
        managed = False
        ordering = ['return_id']

    @property
    def customer_name(self):
        return self.customer.customer_name if self.customer else None

    @property
    def customer_email(self):
        return self.customer.email if self.customer else None

    @property
    def product_name(self):
        return self.product.product_name if self.product else None

    def __str__(self):
        return f"Return {self.return_id} ({self.customer_id}/{self.product_id})"


class Delivery(models.Model):
    """Legacy delivery model kept only so existing imports keep resolving.

    ``public.deliveries`` does not exist in the connected database, so nothing
    in the warehouse flow queries this model any more — delivery state is read
    from ``orders.delivery_status`` instead. Do not build new queries on it
    without a table behind it.
    """
    delivery_id = models.CharField(max_length=255, primary_key=True)
    order = models.ForeignKey(
        Order,
        to_field='order_id',
        db_column='order_id',
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
        related_name='deliveries'
    )
    warehouse = models.ForeignKey(
        Warehouse,
        to_field='warehouse_id',
        db_column='warehouse_id',
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
        related_name='deliveries'
    )
    delivery_partner = models.CharField(max_length=255, blank=True, null=True)
    assigned_employee = models.ForeignKey(
        Employee,
        to_field='employee_id',
        db_column='assigned_employee_id',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='assigned_deliveries'
    )
    dispatch_date = models.CharField(max_length=100, blank=True, null=True)
    expected_delivery_date = models.CharField(max_length=100, blank=True, null=True)
    actual_delivery_date = models.CharField(max_length=100, blank=True, null=True)
    delivery_status = models.CharField(max_length=100, blank=True, null=True)
    failure_reason = models.TextField(blank=True, null=True)
    delivery_type = models.CharField(max_length=50, blank=True, null=True, default='FORWARD')

    class Meta:
        db_table = 'deliveries'
        managed = False
        ordering = ['-dispatch_date']

    def __str__(self):
        return f"Delivery {self.delivery_id} ({self.delivery_status})"


class Payment(models.Model):
    """Legacy payment model kept only so existing imports keep resolving.

    ``public.payments`` does not exist in the connected database; the real
    per-order payment columns (``payment_method``) live on ``public.orders``.
    """
    payment_id = models.CharField(max_length=255, primary_key=True)
    order = models.ForeignKey(
        Order,
        to_field='order_id',
        db_column='order_id',
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
        related_name='payments'
    )
    customer = models.ForeignKey(
        Customer,
        to_field='customer_id',
        db_column='customer_id',
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
        related_name='payments'
    )
    payment_method = models.CharField(max_length=100, blank=True, null=True)
    payment_amount = models.FloatField(blank=True, null=True)
    payment_status = models.CharField(max_length=100, blank=True, null=True)
    payment_date = models.CharField(max_length=100, blank=True, null=True)
    transaction_reference = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        db_table = 'payments'
        managed = False
        ordering = ['-payment_date']

    def __str__(self):
        return f"Payment {self.payment_id} ({self.payment_status})"


__all__ = [
    'Warehouse',
    'Employee',
    'Customer',
    'Category',
    'Product',
    'Inventory',
    'Manufacturer',
    'OrderItem',
    'Order',
    'Delivery',
    'Return',
    'Payment',
]
