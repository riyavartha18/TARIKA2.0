from django.db import models
from accounts.models import Customer, Warehouse


class Order(models.Model):
    order_id = models.CharField(max_length=255, primary_key=True)

    customer = models.ForeignKey(
        Customer,
        to_field='customer_id',
        db_column='customer_id',
        on_delete=models.DO_NOTHING,
        related_name='customer_orders'
    )

    warehouse = models.ForeignKey(
        Warehouse,
        to_field='warehouse_id',
        db_column='warehouse_id',
        on_delete=models.DO_NOTHING,
        related_name='warehouse_orders'
    )

    order_date = models.DateField(blank=True, null=True)
    order_status = models.CharField(max_length=50, blank=True, null=True)
    payment_status = models.CharField(max_length=50, blank=True, null=True)

    total_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True
    )

    discount_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True
    )

    shipping_address = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = 'orders'
        managed = False
        ordering = ['-order_date']

    def __str__(self):
        return f"Order {self.order_id}"


class Payment(models.Model):
    payment_id = models.CharField(max_length=255, primary_key=True)

    order = models.ForeignKey(
        Order,
        to_field='order_id',
        db_column='order_id',
        on_delete=models.DO_NOTHING,
        related_name='payments'
    )

    customer = models.ForeignKey(
        Customer,
        to_field='customer_id',
        db_column='customer_id',
        on_delete=models.DO_NOTHING,
        related_name='customer_payments'
    )

    payment_method = models.CharField(
        max_length=50,
        blank=True,
        null=True
    )

    payment_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True
    )

    payment_status = models.CharField(
        max_length=50,
        blank=True,
        null=True
    )

    payment_date = models.DateField(blank=True, null=True)

    transaction_reference = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    class Meta:
        db_table = 'payments'
        managed = False
        ordering = ['-payment_date']

    def __str__(self):
        return f"Payment {self.payment_id} for Order {self.order_id}"