from django.db.models import Q
from rest_framework import serializers
from catalog.models import Category, Product, Manufacturer, OrderItem
from catalog.serializers import CATEGORY_IMAGE_MAPPING, ManufacturerSerializer
from .models import Order, Delivery, Return, Payment
import datetime
import math


class WarehouseProductSerializer(serializers.ModelSerializer):
    # New `public.products` schema: no category/manufacturer FKs.
    category_id = serializers.SerializerMethodField()
    category_name = serializers.CharField(source='main_category', read_only=True)
    sub_category = serializers.CharField(read_only=True)
    link = serializers.CharField(read_only=True)
    base_price = serializers.SerializerMethodField()
    selling_price = serializers.SerializerMethodField()
    in_stock = serializers.SerializerMethodField()
    total_stock = serializers.SerializerMethodField()
    available_quantity = serializers.FloatField(read_only=True)
    image = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'product_id',
            'product_name',
            'category_id',
            'category_name',
            'sub_category',
            'link',
            'base_price',
            'selling_price',
            'in_stock',
            'total_stock',
            'available_quantity',
            'image',
        ]

    def get_category_id(self, obj):
        name = (obj.main_category or '').strip().lower()
        return name.replace(' ', '-') if name else None

    def get_base_price(self, obj):
        return obj.base_price

    def get_selling_price(self, obj):
        return obj.selling_price

    def get_total_stock(self, obj):
        # Real stock column on the product row; None means stock data is
        # unavailable and must NOT be shown as a fabricated zero.
        return obj.available_quantity

    def get_in_stock(self, obj):
        return (obj.available_quantity or 0) > 0

    def get_image(self, obj):
        # Use the real `image` column; fall back to category artwork when empty.
        if obj.image:
            return obj.image
        cat_name = (obj.main_category or '').strip().lower()
        return CATEGORY_IMAGE_MAPPING.get(cat_name, None)


class WarehouseProductListSerializer(WarehouseProductSerializer):
    is_active = serializers.BooleanField(read_only=True)
    hidden = serializers.BooleanField(read_only=True)
    confidence = serializers.FloatField(read_only=True)

    class Meta(WarehouseProductSerializer.Meta):
        fields = WarehouseProductSerializer.Meta.fields + [
            'is_active',
            'hidden',
            'confidence',
        ]


class WarehouseCategoryGroupedSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()
    products = serializers.SerializerMethodField()
    product_count = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = [
            'category_id',
            'category_name',
            'parent_category_id',
            'description',
            'image',
            'product_count',
            'products'
        ]

    def get_image(self, obj):
        name = (obj.category_name or '').strip().lower()
        return CATEGORY_IMAGE_MAPPING.get(name, None)

    def get_products(self, obj):
        prods = obj.products.filter(Q(is_active=True) | Q(is_active__isnull=True)).select_related('category', 'manufacturer')
        return WarehouseProductSerializer(prods, many=True).data

    def get_product_count(self, obj):
        return obj.products.filter(Q(is_active=True) | Q(is_active__isnull=True)).count()


class WarehouseProductDetailSerializer(serializers.ModelSerializer):
    """
    Full product detail serializer for Warehouse Manager GET endpoint.
    Exposes the real `public.products` columns (plus the legacy keys the React
    edit form consumes). Stock/availability are computed from the live
    `available_quantity` value returned by Supabase.

    Price layout: `initial_price` = original price, `discount_price` =
    discount AMOUNT in currency, `actual_price` = FINAL discounted selling
    price (TEXT column), `discount_percentage` is always derived
    (amount / initial * 100, max 2 dp) and never stored.
    """
    category_id = serializers.SerializerMethodField()
    category_name = serializers.CharField(source='main_category', read_only=True)
    main_category = serializers.CharField(read_only=True)
    sub_category = serializers.CharField(read_only=True)
    link = serializers.CharField(read_only=True)
    base_price = serializers.SerializerMethodField()
    selling_price = serializers.SerializerMethodField()
    initial_price = serializers.FloatField(read_only=True)
    discount_price = serializers.FloatField(read_only=True)
    discount_percentage = serializers.SerializerMethodField()
    # Real `actual_price` column is TEXT — exposed verbatim for the edit form.
    actual_price = serializers.CharField(source='actual_price_text', read_only=True)
    in_stock = serializers.SerializerMethodField()
    total_stock = serializers.SerializerMethodField()
    availability_label = serializers.SerializerMethodField()
    is_active = serializers.BooleanField(read_only=True)
    image = serializers.SerializerMethodField()
    confidence = serializers.FloatField(read_only=True)

    class Meta:
        model = Product
        fields = [
            # Identifiers / read-only metadata
            'product_id',
            'category_id',
            'category_name',
            'main_category',
            'sub_category',
            'link',
            # Editable fields (mapped to real columns)
            'product_name',
            'base_price',
            'selling_price',
            'initial_price',
            'discount_price',
            'discount_percentage',
            'actual_price',
            'available_quantity',
            # Inventory / availability (computed by Django)
            'in_stock',
            'total_stock',
            'availability_label',
            'is_active',
            'image',
            'confidence',
        ]

    def get_category_id(self, obj):
        name = (obj.main_category or '').strip().lower()
        return name.replace(' ', '-') if name else None

    def get_base_price(self, obj):
        return obj.base_price

    def get_selling_price(self, obj):
        return obj.selling_price

    def get_discount_percentage(self, obj):
        return obj.discount_percentage

    def get_total_stock(self, obj):
        """Live stock straight from the product's `available_quantity` column."""
        return obj.available_quantity

    def get_in_stock(self, obj):
        """Django determines availability: available_quantity > 0 means in-stock."""
        return (obj.available_quantity or 0) > 0

    def get_availability_label(self, obj):
        """
        Authoritative availability label computed by Django.
        A real numeric 0 ('Out of Stock') is distinguished from missing data
        ('Stock Data Unavailable'). React must display this value directly.
        """
        qty = obj.available_quantity
        if qty is None:
            return 'Stock Data Unavailable'
        if qty > 0:
            return 'Available'
        return 'Out of Stock'

    def get_image(self, obj):
        # Detail/edit view: return the RAW `image` column so the edit form
        # never persists a decorative category fallback into the database.
        return obj.image


class WarehouseProductUpdateSerializer(serializers.Serializer):
    """
    Write serializer for PUT /api/warehouse/products/<product_key>/.
    Validates exactly the editable columns of the real `public.products`
    schema — all business rules are enforced here in Django, not in React.

    Price layout (authoritative, resolved and recalculated server-side):
      * `initial_price`  -> original product price (double precision)
      * `discount_price` -> discount AMOUNT in currency, never a percentage
      * `actual_price`   -> FINAL discounted selling price (TEXT column)
        with `actual_price = initial_price - discount_price` (2 dp).

    Both warehouse input methods are supported and cross-checked here:
      1. discount amount entered   -> final price is calculated;
      2. discounted price entered  -> discount amount is calculated;
      3. both entered              -> they must agree to the cent.
    Missing inputs fall back to the stored product row (passed via
    `context['product']`). Any field that is not a real, supported column is
    rejected outright (never silently ignored), so a stale legacy payload from
    the admin editor fails loudly instead of quietly persisting nothing.
    """
    product_name = serializers.CharField(max_length=1000, required=False)
    main_category = serializers.CharField(max_length=255, allow_blank=True, required=False)
    sub_category = serializers.CharField(max_length=255, allow_blank=True, required=False)
    image = serializers.CharField(max_length=2000, allow_blank=True, required=False, allow_null=True)
    link = serializers.CharField(max_length=2000, allow_blank=True, required=False, allow_null=True)
    initial_price = serializers.FloatField(required=False, allow_null=True)
    discount_price = serializers.FloatField(required=False, allow_null=True)
    actual_price = serializers.CharField(max_length=255, allow_blank=True, required=False, allow_null=True)
    available_quantity = serializers.FloatField(required=False, allow_null=True)
    is_active = serializers.BooleanField(required=False)
    hidden = serializers.BooleanField(required=False)
    confidence = serializers.FloatField(required=False)

    @staticmethod
    def _clean_number(value, field_label):
        """Reject NaN/Infinity and non-finite numeric input outright."""
        if value is None:
            return None
        if not math.isfinite(value):
            raise serializers.ValidationError(f'{field_label} must be a finite number.')
        return value

    def validate_product_name(self, value):
        """Product name must be a non-empty, non-whitespace string."""
        stripped = (value or '').strip()
        if not stripped:
            raise serializers.ValidationError('Product name cannot be empty.')
        if len(stripped) < 2:
            raise serializers.ValidationError('Product name must be at least 2 characters.')
        return stripped

    def validate_main_category(self, value):
        return (value or '').strip() or None

    def validate_sub_category(self, value):
        return (value or '').strip() or None

    def validate_initial_price(self, value):
        """Original price must be a finite, non-negative number if provided."""
        value = self._clean_number(value, 'Initial price')
        if value is not None and value < 0:
            raise serializers.ValidationError('Initial price cannot be negative.')
        return value

    def validate_discount_price(self, value):
        """Discount AMOUNT must be a finite, non-negative number if provided.
        It is currency, never a percentage."""
        value = self._clean_number(value, 'Discount price')
        if value is not None and value < 0:
            raise serializers.ValidationError('Discount price cannot be negative.')
        return value

    def validate_actual_price(self, value):
        """`actual_price` is the FINAL selling price. The column is TEXT, so
        accept numeric text ('800', '1,099') but reject anything unparsable
        when a value is supplied. A leading minus is a real negative price
        and must be rejected (the lenient column parser would strip it)."""
        if value is None or (isinstance(value, str) and not value.strip()):
            return value
        import re
        if re.search(r'-\s*\d', str(value)):
            raise serializers.ValidationError(
                'Discounted price cannot be negative.')
        from catalog.models import parse_product_price
        parsed = parse_product_price(value)
        if parsed is None:
            raise serializers.ValidationError(
                'Discounted price must be a numeric value (e.g. 800 or 1,099).')
        if not math.isfinite(parsed):
            raise serializers.ValidationError('Discounted price must be a finite number.')
        return value

    def validate_available_quantity(self, value):
        """Stock must be a finite, non-negative WHOLE number when provided.

        Fractional values are rejected outright rather than silently truncated
        with int(), so a caller can never lose (or invent) stock through a
        rounding side-effect. A null value is preserved (see the null-stock
        policy) and means 'stock unknown'."""
        value = self._clean_number(value, 'Available quantity')
        if value is None:
            return None
        if value < 0:
            raise serializers.ValidationError('Available quantity cannot be negative.')
        if value != int(value):
            raise serializers.ValidationError('Available quantity must be a whole number of units.')
        return float(int(value))

    def validate(self, attrs):
        # Reject any key the real `products` schema does not support instead of
        # silently dropping it (legacy editors sent description/sku/color/...).
        unknown = sorted(set(self.initial_data or {}) - set(self.fields.keys()))
        if unknown:
            raise serializers.ValidationError({
                field: ['This field is not supported by the product schema.']
                for field in unknown
            })

        # ---- Authoritative price resolution (Django, not React) ----------
        from catalog.models import parse_product_price
        from catalog.pricing import resolve_product_prices

        touches_price = any(
            key in attrs for key in ('initial_price', 'discount_price', 'actual_price')
        )
        if not touches_price:
            return attrs

        existing = (self.context or {}).get('product')
        # 'present but explicitly null' keeps the stored value: the edit form
        # always submits the full price triple, so a null here only comes
        # from a partial payload and must not wipe the stored original price.
        initial = attrs.get('initial_price')
        if initial is None and existing is not None:
            initial = existing.initial_price if existing.initial_price is not None \
                else existing.base_price

        amount = attrs['discount_price'] if 'discount_price' in attrs else None
        final_input = attrs.get('actual_price')
        final = parse_product_price(final_input) if final_input not in (None, '') else None
        if final is None and 'actual_price' not in attrs and amount is None and existing is not None:
            # Only the original price was submitted: keep the stored discount
            # amount and recalculate the final price from it.
            amount = existing.discount_price

        try:
            resolved = resolve_product_prices(initial, amount, final)
        except ValueError as exc:
            raise serializers.ValidationError({'non_field_errors': [str(exc)]})

        attrs['initial_price'] = resolved['initial_price']
        attrs['discount_price'] = resolved['discount_price']
        # Keep the TEXT column format the listings already parse: plain
        # numeric text rounded to 2 decimal places.
        attrs['actual_price'] = f"{resolved['final_price']:.2f}"
        # Mirror column kept in sync by the service layer.
        attrs['discounted_price'] = resolved['final_price']
        return attrs


def build_order_lines(orders):
    """Derive the single product line of each order from real columns.

    `public.orders` stores one product per row and there is no order-items table.
    `initial_price` is the line gross written at checkout (unit price x
    quantity), so the unit price is that gross divided back by the quantity; a
    missing or zero quantity falls back to the gross instead of dividing by zero.
    """
    lines = []
    for order in orders:
        product = order.product
        quantity = int(order.quantity or 0)
        gross = float(order.initial_price or 0.0)
        unit_price = round(gross / quantity, 2) if quantity > 0 else gross
        lines.append({
            'order_item_id': order.order_id,
            'order_id': order.order_id,
            'product_id': product.product_id if product else (order.product_id or ''),
            'product_name': (product.product_name if product else None) or 'Catalog product',
            'category_name': (product.main_category if product else None) or '',
            'sub_category': (product.sub_category if product else None) or '',
            'quantity': quantity,
            'unit_price': unit_price,
            'discount': float(order.additional_discount or 0.0),
            'subtotal': float(order.final_price if order.final_price is not None else gross),
            'image': (product.image if product else None) or '',
            'product_url': (product.link if product else None) or '',
        })
    return lines
    def validate_confidence(self, value):
        """Classification confidence is a finite score between 0 and 1."""
        value = self._clean_number(value, 'Confidence')
        if value < 0 or value > 1:
            raise serializers.ValidationError('Confidence must be between 0 and 1.')
        return value


class WarehouseOrderSerializer(serializers.ModelSerializer):
    """Read-only order row for the warehouse Orders tab.

    Every value comes from the real `public.orders` row plus its joined customer
    and product. Keys this schema has no column for (fulfilment warehouse,
    payment status, shipping address, phone) are returned as None, so the
    dashboard can label them "not recorded" instead of inventing a value.
    """
    customer_name = serializers.SerializerMethodField()
    customer_email = serializers.SerializerMethodField()
    customer_phone = serializers.SerializerMethodField()
    warehouse_id = serializers.SerializerMethodField()
    warehouse_name = serializers.SerializerMethodField()
    warehouse_city = serializers.SerializerMethodField()
    order_date = serializers.SerializerMethodField()
    order_status = serializers.SerializerMethodField()
    payment_status = serializers.SerializerMethodField()
    payment_method = serializers.SerializerMethodField()
    total_amount = serializers.SerializerMethodField()
    discount_amount = serializers.SerializerMethodField()
    shipping_address = serializers.SerializerMethodField()
    item_count = serializers.SerializerMethodField()
    product_name = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            'order_id',
            'customer_id',
            'customer_name',
            'customer_email',
            'customer_phone',
            'warehouse_id',
            'warehouse_name',
            'warehouse_city',
            'order_date',
            'order_status',
            'delivery_status',
            'payment_status',
            'payment_method',
            'total_amount',
            'discount_amount',
            'shipping_address',
            'product_name',
            'quantity',
            'item_count',
        ]

    def get_customer_name(self, obj):
        return obj.customer.customer_name if obj.customer else None

    def get_customer_email(self, obj):
        return obj.customer.email if obj.customer else None

    def get_customer_phone(self, obj):
        # public.customers has no phone column.
        return None

    def get_warehouse_id(self, obj):
        # No warehouses table and no warehouse column on orders.
        return None

    def get_warehouse_name(self, obj):
        return None

    def get_warehouse_city(self, obj):
        return None

    def get_order_date(self, obj):
        return obj.purchase_date

    def get_order_status(self, obj):
        return obj.order_status

    def get_payment_status(self, obj):
        # The schema records a payment METHOD but no payment status column.
        return None

    def get_payment_method(self, obj):
        return obj.payment_method

    def get_total_amount(self, obj):
        return obj.final_price

    def get_discount_amount(self, obj):
        return obj.additional_discount

    def get_shipping_address(self, obj):
        return None

    def get_item_count(self, obj):
        # One product per row, so the line quantity IS the item count.
        return int(obj.quantity or 0)

    def get_product_name(self, obj):
        return obj.product.product_name if obj.product else None


class WarehouseOrderItemSerializer(serializers.Serializer):
    """The single product line of an order, derived from the order row.

    Kept as a declared serializer so the shape of an order line stays part of the
    API contract even though `public.order_items` does not exist.
    """
    order_item_id = serializers.CharField(read_only=True)
    order_id = serializers.CharField(read_only=True)
    product_id = serializers.CharField(read_only=True)
    product_name = serializers.CharField(read_only=True)
    category_name = serializers.CharField(read_only=True)
    sub_category = serializers.CharField(read_only=True)
    quantity = serializers.IntegerField(read_only=True)
    unit_price = serializers.FloatField(read_only=True)
    discount = serializers.FloatField(read_only=True)
    subtotal = serializers.FloatField(read_only=True)
    image = serializers.CharField(read_only=True)
    product_url = serializers.CharField(read_only=True)


class WarehouseOrderDetailSerializer(serializers.ModelSerializer):
    """Full order detail for the warehouse modal, from the real order row."""
    customer_name = serializers.SerializerMethodField()
    customer_email = serializers.SerializerMethodField()
    customer_phone = serializers.SerializerMethodField()
    customer_city = serializers.SerializerMethodField()
    customer_state = serializers.SerializerMethodField()
    customer_country = serializers.SerializerMethodField()
    warehouse_id = serializers.SerializerMethodField()
    warehouse_name = serializers.SerializerMethodField()
    warehouse_city = serializers.SerializerMethodField()
    order_date = serializers.SerializerMethodField()
    order_status = serializers.SerializerMethodField()
    payment_status = serializers.SerializerMethodField()
    payment_method = serializers.SerializerMethodField()
    total_amount = serializers.SerializerMethodField()
    discount_amount = serializers.SerializerMethodField()
    shipping_address = serializers.SerializerMethodField()
    items = serializers.SerializerMethodField()
    delivery = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            'order_id',
            'customer_id',
            'customer_name',
            'customer_email',
            'customer_phone',
            'customer_city',
            'customer_state',
            'customer_country',
            'warehouse_id',
            'warehouse_name',
            'warehouse_city',
            'order_date',
            'order_status',
            'delivery_status',
            'payment_status',
            'payment_method',
            'total_amount',
            'discount_amount',
            'shipping_address',
            'quantity',
            'shipping_time_days',
            'rating',
            'items',
            'delivery',
        ]

    def get_customer_name(self, obj):
        return obj.customer.customer_name if obj.customer else None

    def get_customer_email(self, obj):
        return obj.customer.email if obj.customer else None

    def get_customer_phone(self, obj):
        return None

    def get_customer_city(self, obj):
        return None

    def get_customer_state(self, obj):
        return None

    def get_customer_country(self, obj):
        return None

    def get_warehouse_id(self, obj):
        return None

    def get_warehouse_name(self, obj):
        return None

    def get_warehouse_city(self, obj):
        return None

    def get_order_date(self, obj):
        return obj.purchase_date

    def get_order_status(self, obj):
        return obj.order_status

    def get_payment_status(self, obj):
        return None

    def get_payment_method(self, obj):
        return obj.payment_method

    def get_total_amount(self, obj):
        return obj.final_price

    def get_discount_amount(self, obj):
        return obj.additional_discount

    def get_shipping_address(self, obj):
        return None

    def get_items(self, obj):
        return list(build_order_lines([obj]))

    def get_delivery(self, obj):
        # public.deliveries does not exist; the delivery state lives on the
        # order row itself and is returned as its own delivery_status key.
        return None




class WarehouseDeliverySerializer(serializers.Serializer):
    """A delivery row derived from the real `public.orders` table.

    There is no `deliveries` table in this schema, so a delivery IS the order's
    own `delivery_status` (Delivered / In Transit / Returned). Courier partner,
    dispatch date, expected date, assigned employee and failure reason have no
    columns to read from and come back as None rather than being invented.
    `shipping_time_days` is the one real transit figure the dataset carries.
    """
    delivery_id = serializers.CharField(read_only=True)
    order_id = serializers.CharField(read_only=True, default=None, allow_null=True)
    warehouse_id = serializers.CharField(read_only=True, default=None, allow_null=True)
    warehouse_name = serializers.CharField(read_only=True, default=None, allow_null=True)
    warehouse_city = serializers.CharField(read_only=True, default=None, allow_null=True)
    customer_name = serializers.CharField(read_only=True, default=None, allow_null=True)
    customer_city = serializers.CharField(read_only=True, default=None, allow_null=True)
    delivery_partner = serializers.CharField(read_only=True, default=None, allow_null=True)
    dispatch_date = serializers.CharField(read_only=True, default=None, allow_null=True)
    expected_delivery_date = serializers.CharField(read_only=True, default=None, allow_null=True)
    actual_delivery_date = serializers.CharField(read_only=True, default=None, allow_null=True)
    delivery_status = serializers.CharField(read_only=True, default=None, allow_null=True)
    failure_reason = serializers.CharField(read_only=True, default=None, allow_null=True)
    shipping_time_days = serializers.IntegerField(read_only=True, default=None, allow_null=True)
    purchase_date = serializers.CharField(read_only=True, default=None, allow_null=True)


class WarehouseReturnSerializer(serializers.ModelSerializer):
    """A row of the real `public.returns` table, joined to customer and product.

    The table stores return_id / customer / product / return_reason / abuse_type
    and nothing else: no status, date, refund amount, condition or courier
    column, and no link to an order row (the (customer, product) pair is not
    unique in orders, so naming "the" order would be a guess). Those keys are
    returned as None and `workflow_tracked` is False. `abuse_type` is an
    internal fraud classification exposed on this staff endpoint only.
    """
    customer_name = serializers.SerializerMethodField()
    customer_email = serializers.SerializerMethodField()
    order_id = serializers.SerializerMethodField()
    product_id = serializers.SerializerMethodField()
    product_name = serializers.SerializerMethodField()
    product_sku = serializers.SerializerMethodField()
    category_name = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()
    quantity = serializers.SerializerMethodField()
    return_date = serializers.SerializerMethodField()
    return_status = serializers.SerializerMethodField()
    refund_amount = serializers.SerializerMethodField()
    condition_on_return = serializers.SerializerMethodField()
    assigned_employee_id = serializers.SerializerMethodField()
    assigned_employee_name = serializers.SerializerMethodField()
    delivery_partner = serializers.SerializerMethodField()
    pickup_date = serializers.SerializerMethodField()
    workflow_tracked = serializers.SerializerMethodField()

    class Meta:
        model = Return
        fields = [
            'return_id',
            'order_id',
            'customer_id',
            'customer_name',
            'customer_email',
            'product_id',
            'product_name',
            'product_sku',
            'category_name',
            'image',
            'quantity',
            'return_reason',
            'abuse_type',
            'return_date',
            'return_status',
            'refund_amount',
            'condition_on_return',
            'assigned_employee_id',
            'assigned_employee_name',
            'delivery_partner',
            'pickup_date',
            'workflow_tracked',
        ]

    def get_customer_name(self, obj):
        return obj.customer.customer_name if obj.customer else None

    def get_customer_email(self, obj):
        return obj.customer.email if obj.customer else None

    def get_order_id(self, obj):
        return None

    def get_product_id(self, obj):
        return obj.product_id

    def get_product_name(self, obj):
        return obj.product.product_name if obj.product else None

    def get_product_sku(self, obj):
        # products has no sku column; the product_key IS the identifier.
        return obj.product_id

    def get_category_name(self, obj):
        return obj.product.main_category if obj.product else None

    def get_image(self, obj):
        return obj.product.image if obj.product else None

    def get_quantity(self, obj):
        return None

    def get_return_date(self, obj):
        return None

    def get_return_status(self, obj):
        return None

    def get_refund_amount(self, obj):
        return None

    def get_condition_on_return(self, obj):
        return None

    def get_assigned_employee_id(self, obj):
        return None

    def get_assigned_employee_name(self, obj):
        return None

    def get_delivery_partner(self, obj):
        return None

    def get_pickup_date(self, obj):
        return None

    def get_workflow_tracked(self, obj):
        """False: the schema has no return-status column to drive a workflow."""
        return False


class WarehouseReturnAssignSerializer(serializers.Serializer):
    """
    Validates payload submitted by Warehouse Manager when assigning a return pickup.
    Accepts either 'delivery_partner' or 'courier_company' interchangeably.
    """
    delivery_partner = serializers.CharField(
        required=False,
        allow_blank=True,
        default='',
        max_length=255,
        trim_whitespace=True
    )
    courier_company = serializers.CharField(
        required=False,
        allow_blank=True,
        default='',
        max_length=255,
        trim_whitespace=True
    )
    assigned_employee_id = serializers.IntegerField(
        required=True,
        error_messages={'required': 'Please select an active delivery partner employee.'}
    )

    def validate(self, attrs):
        partner = (attrs.get('delivery_partner') or '').strip() or (attrs.get('courier_company') or '').strip()
        if not partner:
            raise serializers.ValidationError({'delivery_partner': 'Please select a courier company.'})
        attrs['delivery_partner'] = partner
        attrs['courier_company'] = partner
        return attrs



class WarehouseOrderDispatchSerializer(serializers.Serializer):
    """
    Validates payload submitted by Warehouse Manager when assigning an order to a delivery partner.
    Ensures courier company is specified, employee is provided, and expected delivery date is explicitly set.
    """
    delivery_partner = serializers.CharField(
        required=True,
        max_length=255,
        trim_whitespace=True,
        error_messages={'blank': 'Please select a courier company.'}
    )
    assigned_employee_id = serializers.IntegerField(
        required=True,
        error_messages={'invalid': 'Please select a valid delivery partner employee.'}
    )
    expected_delivery_date = serializers.CharField(
        required=True,
        max_length=100,
        trim_whitespace=True,
        error_messages={'blank': 'Please specify the expected delivery date.'}
    )

    def validate_delivery_partner(self, value):
        cleaned = (value or '').strip()
        if not cleaned:
            raise serializers.ValidationError("Courier company is required.")
        return cleaned

    def validate_expected_delivery_date(self, value):
        val = (value or '').strip()
        try:
            parsed = datetime.datetime.strptime(val, '%Y-%m-%d').date()
        except ValueError:
            raise serializers.ValidationError("Expected delivery date must be in YYYY-MM-DD format.")
        today = datetime.date.today()
        if parsed < today:
            raise serializers.ValidationError("Expected delivery date cannot be in the past.")
        return val
