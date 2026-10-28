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
            'image'
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
    """
    category_id = serializers.SerializerMethodField()
    category_name = serializers.CharField(source='main_category', read_only=True)
    main_category = serializers.CharField(read_only=True)
    sub_category = serializers.CharField(read_only=True)
    link = serializers.CharField(read_only=True)
    base_price = serializers.SerializerMethodField()
    selling_price = serializers.SerializerMethodField()
    discount_price = serializers.FloatField(read_only=True)
    # Real `actual_price` column is TEXT — exposed verbatim for the edit form.
    actual_price = serializers.CharField(source='actual_price_text', read_only=True)
    in_stock = serializers.SerializerMethodField()
    total_stock = serializers.SerializerMethodField()
    availability_label = serializers.SerializerMethodField()
    is_active = serializers.BooleanField(read_only=True)
    image = serializers.SerializerMethodField()

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
            'discount_price',
            'actual_price',
            'available_quantity',
            # Inventory / availability (computed by Django)
            'in_stock',
            'total_stock',
            'availability_label',
            'is_active',
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
    `discount_price` is a double precision number; `actual_price` is TEXT in
    the database and stays text here; `available_quantity` is a whole-unit,
    non-negative stock count. Any field that is not a real, supported column is
    rejected outright (never silently ignored), so a stale legacy payload from
    the admin editor fails loudly instead of quietly persisting nothing.
    """
    product_name = serializers.CharField(max_length=1000)
    main_category = serializers.CharField(max_length=255, allow_blank=True, required=False)
    sub_category = serializers.CharField(max_length=255, allow_blank=True, required=False)
    image = serializers.CharField(max_length=2000, allow_blank=True, required=False, allow_null=True)
    link = serializers.CharField(max_length=2000, allow_blank=True, required=False, allow_null=True)
    discount_price = serializers.FloatField(required=False, allow_null=True)
    actual_price = serializers.CharField(max_length=255, allow_blank=True, required=False, allow_null=True)
    available_quantity = serializers.FloatField(required=False, allow_null=True)
    is_active = serializers.BooleanField(required=False)

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

    def validate_discount_price(self, value):
        """Discount price must be a finite, non-negative number if provided."""
        value = self._clean_number(value, 'Discount price')
        if value is not None and value < 0:
            raise serializers.ValidationError('Discount price cannot be negative.')
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
        return attrs


class WarehouseOrderSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.full_name', read_only=True, default='Guest / Online Customer')
    customer_email = serializers.CharField(source='customer.email', read_only=True, default='')
    customer_phone = serializers.CharField(source='customer.phone', read_only=True, default='')
    warehouse_name = serializers.CharField(source='warehouse.warehouse_name', read_only=True, default='Fulfillment Center')
    warehouse_city = serializers.CharField(source='warehouse.city', read_only=True, default='')
    item_count = serializers.SerializerMethodField()

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
            'payment_status',
            'total_amount',
            'discount_amount',
            'shipping_address',
            'item_count',
            'created_at',
            'updated_at'
        ]

    def get_item_count(self, obj):
        try:
            return OrderItem.objects.filter(order_id=obj.order_id).count()
        except Exception:
            return 0


class WarehouseOrderItemSerializer(serializers.ModelSerializer):
    product_id = serializers.CharField(source='product.product_id', read_only=True, default='')
    product_name = serializers.CharField(source='product.product_name', read_only=True, default='Apparel Product')
    sku = serializers.CharField(source='product.sku', read_only=True, default='')
    category_name = serializers.CharField(source='product.category.category_name', read_only=True, default=None)
    manufacturer_name = serializers.CharField(source='product.manufacturer.manufacturer_name', read_only=True, default=None)
    color = serializers.CharField(source='product.color', read_only=True, default='')
    size = serializers.CharField(source='product.size', read_only=True, default='')
    material = serializers.CharField(source='product.material', read_only=True, default='')
    image = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = [
            'order_item_id',
            'order_id',
            'product_id',
            'product_name',
            'sku',
            'category_name',
            'manufacturer_name',
            'color',
            'size',
            'material',
            'quantity',
            'unit_price',
            'discount',
            'subtotal',
            'image',
        ]

    def get_image(self, obj):
        if obj.product and obj.product.category:
            cat_name = (obj.product.category.category_name or '').strip().lower()
            return CATEGORY_IMAGE_MAPPING.get(cat_name, None)
        return None


class WarehouseOrderDetailSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.full_name', read_only=True, default='Guest / Online Customer')
    customer_email = serializers.CharField(source='customer.email', read_only=True, default='')
    customer_phone = serializers.CharField(source='customer.phone', read_only=True, default='')
    customer_city = serializers.CharField(source='customer.city', read_only=True, default='')
    customer_state = serializers.CharField(source='customer.state', read_only=True, default='')
    customer_country = serializers.CharField(source='customer.country', read_only=True, default='')
    warehouse_name = serializers.CharField(source='warehouse.warehouse_name', read_only=True, default='Fulfillment Center')
    warehouse_city = serializers.CharField(source='warehouse.city', read_only=True, default='')
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
            'payment_status',
            'total_amount',
            'discount_amount',
            'shipping_address',
            'created_at',
            'updated_at',
            'items',
            'delivery',
        ]

    def get_items(self, obj):
        items = OrderItem.objects.filter(order_id=obj.order_id).select_related('product__category', 'product__manufacturer')
        return WarehouseOrderItemSerializer(items, many=True).data

    def get_delivery(self, obj):
        deliv = Delivery.objects.filter(order_id=obj.order_id).select_related('assigned_employee').first()
        if not deliv:
            return None
        return {
            'delivery_id': deliv.delivery_id,
            'delivery_status': deliv.delivery_status,
            'delivery_partner': deliv.delivery_partner,
            'assigned_employee_id': deliv.assigned_employee_id,
            'assigned_employee_name': deliv.assigned_employee.full_name if deliv.assigned_employee else None,
            'assigned_employee_phone': deliv.assigned_employee.phone if deliv.assigned_employee else None,
            'dispatch_date': deliv.dispatch_date,
            'expected_delivery_date': deliv.expected_delivery_date,
            'actual_delivery_date': deliv.actual_delivery_date,
            'failure_reason': deliv.failure_reason,
        }



class WarehouseDeliverySerializer(serializers.ModelSerializer):
    warehouse_name = serializers.CharField(source='warehouse.warehouse_name', read_only=True, default='Fulfillment Hub')
    warehouse_city = serializers.CharField(source='warehouse.city', read_only=True, default='')
    customer_name = serializers.SerializerMethodField()
    customer_city = serializers.SerializerMethodField()

    class Meta:
        model = Delivery
        fields = [
            'delivery_id',
            'order_id',
            'warehouse_id',
            'warehouse_name',
            'warehouse_city',
            'customer_name',
            'customer_city',
            'delivery_partner',
            'dispatch_date',
            'expected_delivery_date',
            'actual_delivery_date',
            'delivery_status',
            'failure_reason'
        ]

    def get_customer_name(self, obj):
        if obj.order and obj.order.customer:
            return obj.order.customer.full_name or 'Valued Customer'
        return 'Valued Customer'

    def get_customer_city(self, obj):
        if obj.order and obj.order.customer:
            return obj.order.customer.city or ''
        return ''


class WarehouseReturnSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.full_name', read_only=True, default='Valued Customer')
    customer_email = serializers.CharField(source='customer.email', read_only=True, default='')
    order_id = serializers.SerializerMethodField()
    product_id = serializers.SerializerMethodField()
    product_name = serializers.SerializerMethodField()
    product_sku = serializers.SerializerMethodField()
    quantity = serializers.SerializerMethodField()
    assigned_employee_id = serializers.SerializerMethodField()
    assigned_employee_name = serializers.CharField(source='assigned_employee.full_name', read_only=True, default='')

    def get_assigned_employee_id(self, obj):
        if obj.assigned_employee_id:
            try:
                return int(obj.assigned_employee_id)
            except (ValueError, TypeError):
                return obj.assigned_employee_id
        return None


    class Meta:
        model = Return
        fields = [
            'return_id',
            'order_item_id',
            'order_id',
            'customer_id',
            'customer_name',
            'customer_email',
            'product_id',
            'product_name',
            'product_sku',
            'quantity',
            'return_reason',
            'return_date',
            'return_status',
            'refund_amount',
            'condition_on_return',
            'assigned_employee_id',
            'assigned_employee_name',
            'delivery_partner',
            'pickup_date',
        ]

    def get_order_id(self, obj):
        return obj.order_item.order_id if obj.order_item else None

    def get_product_id(self, obj):
        return obj.order_item.product_id if obj.order_item else None

    def get_product_name(self, obj):
        if obj.order_item and obj.order_item.product:
            return obj.order_item.product.product_name or 'Boutique Apparel'
        return 'Boutique Apparel'

    def get_product_sku(self, obj):
        if obj.order_item and obj.order_item.product:
            return obj.order_item.product.sku or ''
        return ''

    def get_quantity(self, obj):
        return getattr(obj.order_item, 'quantity', 1) if obj.order_item else 1


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

