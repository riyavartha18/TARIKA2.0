from django.db import models


class Category(models.Model):
    category_id = models.CharField(max_length=255, primary_key=True)
    category_name = models.CharField(max_length=255, blank=True, null=True)
    parent_category_id = models.BigIntegerField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        db_table = 'categories'
        managed = False
        ordering = ['category_name']

    def __str__(self):
        return self.category_name or self.category_id


class Manufacturer(models.Model):
    manufacturer_id = models.CharField(max_length=255, primary_key=True)
    manufacturer_name = models.CharField(max_length=255, blank=True, null=True)
    contact_person = models.CharField(max_length=255, blank=True, null=True)
    email = models.CharField(max_length=255, blank=True, null=True)
    phone = models.CharField(max_length=50, blank=True, null=True)
    country = models.CharField(max_length=100, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=100, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'manufacturers'
        managed = False
        ordering = ['manufacturer_name']

    def __str__(self):
        return self.manufacturer_name or self.manufacturer_id


class Product(models.Model):
    product_id = models.CharField(max_length=255, primary_key=True)
    product_name = models.CharField(max_length=255, blank=True, null=True)
    category = models.ForeignKey(
        Category,
        to_field='category_id',
        db_column='category_id',
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
        related_name='products'
    )
    manufacturer = models.ForeignKey(
        Manufacturer,
        to_field='manufacturer_id',
        db_column='manufacturer_id',
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
        related_name='products'
    )
    sku = models.CharField(max_length=100, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    gender = models.CharField(max_length=50, blank=True, null=True)
    color = models.CharField(max_length=100, blank=True, null=True)
    size = models.CharField(max_length=50, blank=True, null=True)
    material = models.CharField(max_length=100, blank=True, null=True)
    cost_price = models.BigIntegerField(blank=True, null=True)
    base_price = models.BigIntegerField(blank=True, null=True)
    selling_price = models.BigIntegerField(blank=True, null=True)
    launch_date = models.CharField(max_length=100, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.CharField(max_length=100, blank=True, null=True)
    updated_at = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        db_table = 'products'
        managed = False
        ordering = ['-launch_date', 'product_name']

    def __str__(self):
        return f"{self.product_name or 'Product'} ({self.sku or self.product_id})"


class Inventory(models.Model):
    inventory_id = models.CharField(max_length=255, primary_key=True)
    product = models.ForeignKey(
        Product,
        to_field='product_id',
        db_column='product_id',
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
        related_name='inventory_items'
    )
    warehouse = models.ForeignKey(
        'accounts.Warehouse',
        to_field='warehouse_id',
        db_column='warehouse_id',
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
        related_name='inventory_items'
    )
    stock_quantity = models.BigIntegerField(blank=True, null=True, default=0)
    reorder_level = models.BigIntegerField(blank=True, null=True)
    last_restock_date = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        db_table = 'inventory'
        managed = False

    def __str__(self):
        return f"Inv {self.inventory_id}: Product {self.product_id} @ Warehouse {self.warehouse_id} ({self.stock_quantity})"


class Review(models.Model):
    review_id = models.CharField(max_length=255, primary_key=True)
    product = models.ForeignKey(
        Product,
        to_field='product_id',
        db_column='product_id',
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
        related_name='reviews'
    )
    customer_id = models.CharField(max_length=255, blank=True, null=True)
    order_id = models.CharField(max_length=255, blank=True, null=True)
    rating = models.BigIntegerField(blank=True, null=True)
    review_text = models.TextField(blank=True, null=True)
    sentiment_label = models.CharField(max_length=100, blank=True, null=True)
    sentiment_score = models.CharField(max_length=100, blank=True, null=True)
    is_verified_purchase = models.BooleanField(blank=True, null=True)
    review_date = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        db_table = 'reviews'
        managed = False

    def __str__(self):
        return f"Review {self.review_id} for {self.product_id}: {self.rating} stars"


class OrderItem(models.Model):
    order_item_id = models.CharField(max_length=255, primary_key=True)
    order_id = models.CharField(max_length=255, blank=True, null=True)
    product = models.ForeignKey(
        Product,
        to_field='product_id',
        db_column='product_id',
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
        related_name='order_items'
    )
    quantity = models.BigIntegerField(blank=True, null=True)
    unit_price = models.BigIntegerField(blank=True, null=True)
    discount = models.FloatField(blank=True, null=True)
    subtotal = models.FloatField(blank=True, null=True)

    class Meta:
        db_table = 'order_items'
        managed = False

    def __str__(self):
        return f"OrderItem {self.order_item_id} (Product {self.product_id} x {self.quantity})"
