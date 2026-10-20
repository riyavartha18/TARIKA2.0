from django.db.models import Q
from rest_framework import serializers
from catalog.models import Category, Product, Inventory, Manufacturer, OrderItem
from catalog.serializers import CATEGORY_IMAGE_MAPPING, ManufacturerSerializer
from .models import Order, Delivery, Return, Payment
import datetime


class WarehouseProductSerializer(serializers.ModelSerializer):
    category_id = serializers.CharField(source='category.category_id', read_only=True)
    category_name = serializers.CharField(source='category.category_name', read_only=True)
    manufacturer_id = serializers.CharField(source='manufacturer.manufacturer_id', read_only=True)
    manufacturer_name = serializers.CharField(source='manufacturer.manufacturer_name', read_only=True, default=None)
    in_stock = serializers.SerializerMethodField()
    total_stock = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'product_id',
            'product_name',
            'category_id',
            'category_name',
            'manufacturer_id',
            'manufacturer_name',
            'sku',
            'description',
            'gender',
            'color',
            'size',
            'material',
            'base_price',
            'selling_price',
            'launch_date',
            'is_active',
            'in_stock',
            'total_stock',
            'image'
        ]

    def get_total_stock(self, obj):
        if hasattr(obj, 'total_stock_annotated') and obj.total_stock_annotated is not None:
            return int(obj.total_stock_annotated)
        if hasattr(obj, '_prefetched_objects_cache') and 'inventory_items' in obj._prefetched_objects_cache:
            items = obj._prefetched_objects_cache['inventory_items']
            return sum(item.stock_quantity or 0 for item in items)
        try:
            return sum(item.stock_quantity or 0 for item in obj.inventory_items.all())
        except (Exception, AssertionError):
            return 0

    def get_in_stock(self, obj):
        return self.get_total_stock(obj) > 0

    def get_image(self, obj):
        cat_name = (obj.category.category_name if obj.category else '').strip().lower()
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
    Includes all editable fields, read-only metadata, and inventory-derived
    stock figures. All availability/status logic is computed here — React
    simply displays what Django returns.
    """
    category_id = serializers.CharField(source='category.category_id', read_only=True)
    category_name = serializers.CharField(source='category.category_name', read_only=True)
    manufacturer_id = serializers.CharField(source='manufacturer.manufacturer_id', read_only=True)
    manufacturer_name = serializers.CharField(
        source='manufacturer.manufacturer_name', read_only=True, default=None
    )
    in_stock = serializers.SerializerMethodField()
    total_stock = serializers.SerializerMethodField()
    availability_label = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            # Identifiers / read-only metadata
            'product_id',
            'sku',
            'category_id',
            'category_name',
            'manufacturer_id',
            'manufacturer_name',
            'cost_price',
            'created_at',
            'updated_at',
            'launch_date',
            # Editable fields
            'product_name',
            'description',
            'gender',
            'color',
            'size',
            'material',
            'base_price',
            'selling_price',
            'is_active',
            # Inventory / availability (computed by Django)
            'in_stock',
            'total_stock',
            'availability_label',
            'image',
        ]

    def get_total_stock(self, obj):
        """Sum stock_quantity across all inventory rows for this product."""
        if hasattr(obj, 'total_stock_annotated') and obj.total_stock_annotated is not None:
            return int(obj.total_stock_annotated)
        if hasattr(obj, '_prefetched_objects_cache') and 'inventory_items' in obj._prefetched_objects_cache:
            items = obj._prefetched_objects_cache['inventory_items']
            return sum(item.stock_quantity or 0 for item in items)
        try:
            return sum(item.stock_quantity or 0 for item in obj.inventory_items.all())
        except (Exception, AssertionError):
            return 0

    def get_in_stock(self, obj):
        """Django determines availability: total_stock > 0 means in-stock."""
        return self.get_total_stock(obj) > 0

    def get_availability_label(self, obj):
        """
        Authoritative availability label computed by Django.
        React must display this value directly — no client-side logic.
        """
        total = self.get_total_stock(obj)
        if total > 0:
            return 'Available'
        return 'Out of Stock'

    def get_image(self, obj):
        cat_name = (obj.category.category_name if obj.category else '').strip().lower()
        return CATEGORY_IMAGE_MAPPING.get(cat_name, None)


class WarehouseProductUpdateSerializer(serializers.Serializer):
    """
    Write serializer for PUT /api/warehouse/products/<id>/.
    Validates all editable product fields — all business rules are enforced
    here in Django, not in React.
    """
    product_name = serializers.CharField(max_length=255)
    description = serializers.CharField(allow_blank=True, required=False, default='')
    gender = serializers.CharField(max_length=50, allow_blank=True, required=False, default='')
    color = serializers.CharField(max_length=100, allow_blank=True, required=False, default='')
    size = serializers.CharField(max_length=50, allow_blank=True, required=False, default='')
    material = serializers.CharField(max_length=100, allow_blank=True, required=False, default='')
    base_price = serializers.IntegerField(required=False, allow_null=True)
    selling_price = serializers.IntegerField(required=False, allow_null=True)
    stock_quantity = serializers.IntegerField(required=False, allow_null=True)
    launch_date = serializers.CharField(max_length=100, allow_blank=True, required=False, default='')
    is_active = serializers.BooleanField(required=False, default=True)

    def validate_product_name(self, value):
        """Product name must be a non-empty, non-whitespace string."""
        stripped = (value or '').strip()
        if not stripped:
            raise serializers.ValidationError('Product name cannot be empty.')
        if len(stripped) < 2:
            raise serializers.ValidationError('Product name must be at least 2 characters.')
        return stripped

    def validate_base_price(self, value):
        """Base price must be a non-negative integer if provided."""
        if value is not None and value < 0:
            raise serializers.ValidationError('Base price cannot be negative.')
        return value

    def validate_selling_price(self, value):
        """Selling price must be a non-negative integer if provided."""
        if value is not None and value < 0:
            raise serializers.ValidationError('Selling price cannot be negative.')
        return value

    def validate_stock_quantity(self, value):
        """Stock quantity must be a non-negative integer if provided."""
        if value is not None and value < 0:
            raise serializers.ValidationError('Stock quantity cannot be negative.')
        return value

    def validate(self, data):
        """Cross-field validation."""
        base = data.get('base_price')
        selling = data.get('selling_price')
        if base is not None and selling is not None and selling > base * 2:
            # Soft warning — allow but flag; strict constraint can be added here
            pass
        return data


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

