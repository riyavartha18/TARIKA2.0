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
    customer_id = models.CharField(max_length=255, primary_key=True)
    auth_user_id = models.UUIDField(unique=True, blank=True, null=True)
    full_name = models.CharField(max_length=255, blank=True, null=True)
    email = models.CharField(max_length=255, blank=True, null=True)
    phone = models.BigIntegerField(blank=True, null=True)
    gender = models.CharField(max_length=50, blank=True, null=True)
    date_of_birth = models.CharField(max_length=50, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=100, blank=True, null=True)
    country = models.CharField(max_length=100, blank=True, null=True)
    postal_code = models.BigIntegerField(blank=True, null=True)
    registration_date = models.CharField(max_length=100, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.CharField(max_length=100, blank=True, null=True)
    updated_at = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        db_table = 'customer'
        managed = False

    def __str__(self):
        return f"{self.full_name or 'Customer'} ({self.email})"


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
