import re

from django.db import models  # type: ignore[reportMissingModuleSource]


def parse_product_price(raw_value):
    """
    Parse a TEXT price column into a float.

    ``products.actual_price`` is TEXT and may carry thousands separators or a
    currency symbol (e.g. '599', '1,099', '₹1,233.00'), so strip everything but
    digits and the decimal point first. Returns None when no numeric value can
    be extracted, which lets callers fall back instead of inventing a price.
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
    Maps the real `public.products` table.

    Legacy Python attribute names (product_id, product_name, selling_price,
    base_price) are preserved via db_column / properties so existing
    serializers, services and frontend contracts keep working unchanged.

    Price columns, verified against the connected Neon database (every one of
    the 90,041 product rows agrees with this layout):

      * ``actual_price``      TEXT    -> the ORIGINAL product price
      * ``discount_price``    float   -> the discount AMOUNT in currency
      * ``discounted_price``  numeric -> the FINAL selling price, and it equals
        ``parsed(actual_price) - discount_price`` on every row.

    There is no ``initial_price`` column in this schema: the original price
    already lives in ``actual_price``. (A former ``initial_price`` field here
    mapped to that non-existent column, which made *every* product SELECT fail
    with ``column products.initial_price does not exist``. It is now a read and
    write alias of the original price, so legacy callers keep working without
    ever reaching for a missing column.)

    The percentage is never stored and never taken from ``discount_price``
    blindly: it is always derived from the two prices that are displayed,
    ``((actual_price - discounted_price) / actual_price) * 100``.
    """
    product_id = models.CharField(max_length=255, primary_key=True, db_column='product_key')
    product_name = models.CharField(max_length=1000, blank=True, null=True, db_column='name')
    main_category = models.CharField(max_length=255, blank=True, null=True, db_column='main_category')
    sub_category = models.CharField(max_length=255, blank=True, null=True, db_column='sub_category')
    image = models.CharField(max_length=2000, blank=True, null=True, db_column='image')
    link = models.CharField(max_length=2000, blank=True, null=True, db_column='link')
    # Discount AMOUNT in currency (never a percentage).
    discount_price = models.FloatField(blank=True, null=True, db_column='discount_price')
    # The ORIGINAL price. The column is TEXT, so it is parsed before any maths.
    actual_price_text = models.TextField(blank=True, null=True, db_column='actual_price')
    # The FINAL selling price the customer pays.
    discounted_price = models.FloatField(blank=True, null=True, db_column='discounted_price')
    # Real stock/availability source for the new `public.products` schema.
    # There is no separate inventory table in this database; availability is
    # carried directly on the product row as a numeric quantity.
    available_quantity = models.FloatField(blank=True, null=True, db_column='available_quantity')
    is_active = models.BooleanField(default=True, db_column='is_active')
    is_image_valid = models.BooleanField(default=True, db_column='is_image_valid')

    # Stylist classification attributes
    slot_type = models.CharField(max_length=50, blank=True, null=True, db_column='slot_type')
    formality = models.IntegerField(default=3, db_column='formality')
    pattern = models.CharField(max_length=50, default='solid', db_column='pattern')
    dominant_colours = models.TextField(default='[]', db_column='dominant_colours')
    style_family = models.CharField(max_length=50, default='western', db_column='style_family')
    season = models.CharField(max_length=50, default='all', db_column='season')
    footwear_type = models.CharField(max_length=50, blank=True, null=True, db_column='footwear_type')
    accessory_type = models.CharField(max_length=50, blank=True, null=True, db_column='accessory_type')
    subtype = models.CharField(max_length=50, default='other', db_column='subtype')
    includes_blouse = models.BooleanField(default=False, db_column='includes_blouse')
    includes_dupatta = models.BooleanField(default=False, db_column='includes_dupatta')
    metal_tone = models.CharField(max_length=50, default='unknown', db_column='metal_tone')
    confidence = models.FloatField(default=0.0, db_column='confidence')
    hidden = models.BooleanField(default=False, db_column='hidden',blank=True, null=True)

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
    def original_price(self):
        """The ORIGINAL price -> parsed `actual_price` TEXT column.

        When that text is unparsable the original is rebuilt from the final
        price plus the discount amount, so one damaged cell cannot silently
        remove the strikethrough price from a listing.
        """
        parsed = parse_product_price(self.actual_price_text)
        if parsed is not None:
            return parsed
        if self.discounted_price is not None:
            return float(self.discounted_price) + float(self.discount_price or 0.0)
        return None

    @property
    def base_price(self):
        """Legacy API key for the original (strikethrough) price."""
        return self.original_price

    @property
    def selling_price(self):
        """FINAL selling price -> real `discounted_price` column.

        Falls back to the original price when no discounted value is stored (no
        discount means it sells at its original price), never to an invented one.
        """
        if self.discounted_price is not None:
            return float(self.discounted_price)
        return self.original_price

    @property
    def initial_price(self):
        """Backward-compatible alias for the original price."""
        return self.original_price

    @initial_price.setter
    def initial_price(self, value):
        # In this schema the original price IS the TEXT `actual_price` column,
        # so a writer that still speaks `initial_price` lands in the right place.
        self.actual_price_text = value

    @property
    def discount_amount(self):
        """Discount AMOUNT in currency, implied by the two stored prices.

        Derived from the prices rather than read straight from `discount_price`
        so the amount can never contradict what the shopper sees; the column is
        used only when a price is missing.
        """
        original = self.original_price
        final = self.selling_price
        if original is not None and final is not None:
            return max(0.0, round(float(original) - float(final), 2))
        if self.discount_price is not None:
            return max(0.0, float(self.discount_price))
        return 0.0

    @property
    def discount_percentage(self):
        """((actual_price - discounted_price) / actual_price) * 100, max 2 dp.

        Never negative (a final price at or above the original is "no discount",
        not a negative badge), capped at 100, and a zero / missing original price
        returns 0.0 instead of dividing by zero.
        """
        original = self.original_price
        final = self.selling_price
        if not original or original <= 0 or final is None:
            return 0.0
        percentage = (float(original) - float(final)) / float(original) * 100
        if percentage <= 0:
            return 0.0
        return round(min(percentage, 100.0), 2)


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
