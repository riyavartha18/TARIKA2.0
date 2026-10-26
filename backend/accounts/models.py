import uuid
from django.db import models


class Role(models.TextChoices):
    CUSTOMER = 'CUSTOMER', 'Customer'
    ADMIN = 'ADMIN', 'Admin'
    WAREHOUSE_MANAGER = 'WAREHOUSE_MANAGER', 'Warehouse Manager'
    DELIVERY_PARTNER = 'DELIVERY_PARTNER', 'Delivery Partner'


class EmployeeRole(models.TextChoices):
    ADMIN = 'ADMIN', 'Admin'
    WAREHOUSE_MANAGER = 'WAREHOUSE_MANAGER', 'Warehouse Manager'
    DELIVERY_PARTNER = 'DELIVERY_PARTNER', 'Delivery Partner'


class Warehouse(models.Model):
    warehouse_id = models.CharField(max_length=255, primary_key=True)
    warehouse_name = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=100, blank=True, null=True)
    country = models.CharField(max_length=100, blank=True, null=True)
    capacity = models.BigIntegerField(blank=True, null=True)
    manager_name = models.CharField(max_length=255, blank=True, null=True)
    contact_number = models.CharField(max_length=50, blank=True, null=True)
    created_at = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        db_table = 'warehouses'
        managed = False

    def __str__(self):
        return f"{self.warehouse_name or self.warehouse_id} ({self.city or 'Unknown'})"


class Customer(models.Model):
    """Maps the real `public.customers` table.

    Only the four non-secret columns are mapped on purpose: Django builds an
    explicit column list, so `customers.password` is never selected,
    serialized or logged by anything that goes through this model. Password
    verification stays in accounts/services/supabase_auth.py where pgcrypto
    compares it inside PostgreSQL.

    `full_name` is kept as an alias because the API responses and the frontend
    already use that key.
    """
    customer_id = models.CharField(max_length=255, primary_key=True)
    customer_name = models.CharField(max_length=255, blank=True, null=True)
    gender = models.CharField(max_length=50, blank=True, null=True)
    email = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        db_table = 'customers'
        managed = False
        ordering = ['customer_id']

    @property
    def full_name(self):
        return self.customer_name

    def __str__(self):
        return f"{self.customer_name or 'Customer'} ({self.email})"


class Employee(models.Model):
    employee_id = models.BigAutoField(primary_key=True)
    auth_user_id = models.UUIDField(unique=True)
    full_name = models.CharField(max_length=255)
    email = models.CharField(max_length=255, unique=True)
    phone = models.CharField(max_length=50, blank=True, null=True)
    role = models.CharField(max_length=30, choices=EmployeeRole.choices)
    warehouse = models.ForeignKey(
        Warehouse,
        to_field='warehouse_id',
        db_column='warehouse_id',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='employees'
    )
    courier_company = models.CharField(max_length=100, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'employees'
        managed = False

    def __str__(self):
        return f"{self.full_name} ({self.role})"
