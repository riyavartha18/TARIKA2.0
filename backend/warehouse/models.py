from django.db import models
from accounts.models import Warehouse, Employee, Customer
from catalog.models import Category, Product, Inventory, Manufacturer, OrderItem


class Order(models.Model):
    order_id = models.CharField(max_length=255, primary_key=True)
    customer = models.ForeignKey(
        Customer,
        to_field='customer_id',
        db_column='customer_id',
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
        related_name='orders'
    )
    warehouse = models.ForeignKey(
        Warehouse,
        to_field='warehouse_id',
        db_column='warehouse_id',
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
        related_name='orders'
    )
    order_date = models.CharField(max_length=100, blank=True, null=True)
    order_status = models.CharField(max_length=100, blank=True, null=True)
    payment_status = models.CharField(max_length=100, blank=True, null=True)
    total_amount = models.FloatField(blank=True, null=True)
    discount_amount = models.FloatField(blank=True, null=True)
    shipping_address = models.TextField(blank=True, null=True)
    created_at = models.CharField(max_length=100, blank=True, null=True)
    updated_at = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        db_table = 'orders'
        managed = False
        ordering = ['-order_date', '-created_at']

    def __str__(self):
        return f"Order {self.order_id} ({self.order_status})"


class Delivery(models.Model):
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
    return_record = models.ForeignKey(
        'Return',
        to_field='return_id',
        db_column='return_id',
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
        related_name='deliveries'
    )

    class Meta:
        db_table = 'deliveries'
        managed = False
        ordering = ['-dispatch_date']

    def __str__(self):
        return f"Delivery {self.delivery_id} ({self.delivery_status})"


class Return(models.Model):
    return_id = models.CharField(max_length=255, primary_key=True)
    order_item = models.ForeignKey(
        OrderItem,
        to_field='order_item_id',
        db_column='order_item_id',
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
        related_name='returns'
    )
    customer = models.ForeignKey(
        Customer,
        to_field='customer_id',
        db_column='customer_id',
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
        related_name='returns'
    )
    return_reason = models.CharField(max_length=255, blank=True, null=True)
    return_date = models.CharField(max_length=100, blank=True, null=True)
    return_status = models.CharField(max_length=100, blank=True, null=True)
    refund_amount = models.FloatField(blank=True, null=True)
    condition_on_return = models.TextField(blank=True, null=True)
    assigned_employee = models.ForeignKey(
        Employee,
        to_field='employee_id',
        db_column='assigned_employee_id',
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
        related_name='assigned_returns'
    )
    delivery_partner = models.CharField(max_length=100, blank=True, null=True)
    pickup_date = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        db_table = 'returns'
        managed = False
        ordering = ['-return_date']

    def __str__(self):
        return f"Return {self.return_id} ({self.return_status})"


class Payment(models.Model):
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
