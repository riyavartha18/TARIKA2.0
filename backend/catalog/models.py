import re

from django.db import models


def parse_product_price(raw_value):
    """
    Parse the real products.actual_price TEXT column into a float.

    The Supabase column is TEXT (e.g. '599' or '1,099'), so strip any
    currency symbols / thousands separators defensively. Returns None
    when no numeric value can be extracted.
    """
    if raw_value is None:
        return None
    cleaned = re.sub(r'[^\d.]', '', str(raw_value))
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


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
    """
    Maps the real Supabase `public.products` table.

    Legacy Python attribute names (product_id, product_name, selling_price,
    base_price) are preserved via db_column / properties so existing
    serializers, services and frontend contracts keep working unchanged.
    """
    product_id = models.CharField(max_length=255, primary_key=True, db_column='product_key')
    product_name = models.CharField(max_length=1000, blank=True, null=True, db_column='name')
    main_category = models.CharField(max_length=255, blank=True, null=True, db_column='main_category')
    sub_category = models.CharField(max_length=255, blank=True, null=True, db_column='sub_category')
    image = models.CharField(max_length=2000, blank=True, null=True, db_column='image')
    link = models.CharField(max_length=2000, blank=True, null=True, db_column='link')
    discount_price = models.FloatField(blank=True, null=True, db_column='discount_price')
    # NOTE: the real column is TEXT, not numeric.
    actual_price_text = models.TextField(blank=True, null=True, db_column='actual_price')
    # Real stock/availability source for the new `public.products` schema.
    # There is no separate inventory table in this database; availability is
    # carried directly on the product row as a numeric quantity.
    available_quantity = models.FloatField(blank=True, null=True, db_column='available_quantity')
    # Soft-delete / archive flag added by `ensure_inventory_schema`. A product
    # that still has order/cart/wishlist history is archived (is_active=False)
    # instead of hard-deleted, so it disappears from every storefront while the
    # historical rows keep their foreign key. Default TRUE keeps existing rows
    # active.
    is_active = models.BooleanField(default=True, db_column='is_active')

    class Meta:
        db_table = 'products'
        managed = False
        ordering = ['product_name', 'product_id']

    def __str__(self):
        return f"{self.product_name or 'Product'} ({self.product_id})"

    # ------------------------------------------------------------------
    # Legacy field-name compatibility (mapping layer for the new schema)
    # ------------------------------------------------------------------
    @property
    def selling_price(self):
        """Current/discounted price -> real `discount_price` column."""
        return self.discount_price

    @property
    def base_price(self):
        """List/original price -> real `actual_price` TEXT column, parsed."""
        return parse_product_price(self.actual_price_text)


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
