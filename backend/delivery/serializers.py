from rest_framework import serializers
from warehouse.models import Delivery, Order, Return
from accounts.models import Employee, Customer
from catalog.models import OrderItem, Product
from catalog.serializers import CATEGORY_IMAGE_MAPPING


class DeliveryEmployeeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Employee
        fields = [
            'employee_id',
            'auth_user_id',
            'full_name',
            'email',
            'phone',
            'role',
            'courier_company',
            'is_active',
        ]


class DeliveryOrderItemSerializer(serializers.ModelSerializer):
    product_id = serializers.CharField(source='product.product_id', read_only=True, default='')
    product_name = serializers.CharField(source='product.product_name', read_only=True, default='Apparel Item')
    sku = serializers.CharField(source='product.sku', read_only=True, default='')
    color = serializers.CharField(source='product.color', read_only=True, default='')
    size = serializers.CharField(source='product.size', read_only=True, default='')
    material = serializers.CharField(source='product.material', read_only=True, default='')
    image = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = [
            'order_item_id',
            'product_id',
            'product_name',
            'sku',
            'color',
            'size',
            'material',
            'quantity',
            'unit_price',
            'subtotal',
            'image',
        ]

    def get_image(self, obj):
        if obj.product and obj.product.category:
            cat_name = (obj.product.category.category_name or '').strip().lower()
            return CATEGORY_IMAGE_MAPPING.get(cat_name, None)
        return None


class DeliveryPartnerListSerializer(serializers.ModelSerializer):
    customer_name = serializers.SerializerMethodField()
    customer_phone = serializers.SerializerMethodField()
    customer_city = serializers.SerializerMethodField()
    customer_address = serializers.SerializerMethodField()
    order_date = serializers.SerializerMethodField()
    order_status = serializers.SerializerMethodField()
    total_amount = serializers.SerializerMethodField()
    item_count = serializers.SerializerMethodField()

    class Meta:
        model = Delivery
        fields = [
            'delivery_id',
            'order_id',
            'delivery_partner',
            'assigned_employee_id',
            'customer_name',
            'customer_phone',
            'customer_city',
            'customer_address',
            'order_date',
            'order_status',
            'total_amount',
            'item_count',
            'dispatch_date',
            'expected_delivery_date',
            'actual_delivery_date',
            'delivery_status',
            'failure_reason',
        ]

    def get_customer_name(self, obj):
        if obj.order and obj.order.customer:
            return obj.order.customer.full_name or 'Valued Customer'
        return 'Valued Customer'

    def get_customer_phone(self, obj):
        if obj.order and obj.order.customer:
            return str(obj.order.customer.phone or '')
        return ''

    def get_customer_city(self, obj):
        if obj.order and obj.order.customer:
            return obj.order.customer.city or ''
        return ''

    def get_customer_address(self, obj):
        if obj.order:
            return obj.order.shipping_address or ''
        return ''

    def get_order_date(self, obj):
        return obj.order.order_date if obj.order else ''

    def get_order_status(self, obj):
        return obj.order.order_status if obj.order else ''

    def get_total_amount(self, obj):
        return obj.order.total_amount if obj.order else 0.0

    def get_item_count(self, obj):
        if obj.order:
            return OrderItem.objects.filter(order_id=obj.order.order_id).count()
        return 0


class DeliveryPartnerDetailSerializer(serializers.ModelSerializer):
    customer_name = serializers.SerializerMethodField()
    customer_email = serializers.SerializerMethodField()
    customer_phone = serializers.SerializerMethodField()
    customer_city = serializers.SerializerMethodField()
    customer_state = serializers.SerializerMethodField()
    customer_country = serializers.SerializerMethodField()
    shipping_address = serializers.SerializerMethodField()
    order_date = serializers.SerializerMethodField()
    order_status = serializers.SerializerMethodField()
    payment_status = serializers.SerializerMethodField()
    total_amount = serializers.SerializerMethodField()
    items = serializers.SerializerMethodField()
    assigned_employee_name = serializers.SerializerMethodField()

    class Meta:
        model = Delivery
        fields = [
            'delivery_id',
            'order_id',
            'warehouse_id',
            'delivery_partner',
            'assigned_employee_id',
            'assigned_employee_name',
            'customer_name',
            'customer_email',
            'customer_phone',
            'customer_city',
            'customer_state',
            'customer_country',
            'shipping_address',
            'order_date',
            'order_status',
            'payment_status',
            'total_amount',
            'dispatch_date',
            'expected_delivery_date',
            'actual_delivery_date',
            'delivery_status',
            'failure_reason',
            'items',
        ]

    def get_customer_name(self, obj):
        if obj.order and obj.order.customer:
            return obj.order.customer.full_name or 'Valued Customer'
        return 'Valued Customer'

    def get_customer_email(self, obj):
        if obj.order and obj.order.customer:
            return obj.order.customer.email or ''
        return ''

    def get_customer_phone(self, obj):
        if obj.order and obj.order.customer:
            return str(obj.order.customer.phone or '')
        return ''

    def get_customer_city(self, obj):
        if obj.order and obj.order.customer:
            return obj.order.customer.city or ''
        return ''

    def get_customer_state(self, obj):
        if obj.order and obj.order.customer:
            return obj.order.customer.state or ''
        return ''

    def get_customer_country(self, obj):
        if obj.order and obj.order.customer:
            return obj.order.customer.country or ''
        return ''

    def get_shipping_address(self, obj):
        return obj.order.shipping_address if obj.order else ''

    def get_order_date(self, obj):
        return obj.order.order_date if obj.order else ''

    def get_order_status(self, obj):
        return obj.order.order_status if obj.order else ''

    def get_payment_status(self, obj):
        return obj.order.payment_status if obj.order else ''

    def get_total_amount(self, obj):
        return obj.order.total_amount if obj.order else 0.0

    def get_assigned_employee_name(self, obj):
        return obj.assigned_employee.full_name if obj.assigned_employee else ''

    def get_items(self, obj):
        if not obj.order:
            return []
        items = OrderItem.objects.filter(order_id=obj.order.order_id).select_related('product__category')
        return DeliveryOrderItemSerializer(items, many=True).data


class DeliveryStatusUpdateSerializer(serializers.Serializer):
    ALLOWED_STATUSES = ['Assigned', 'Picked Up', 'In Transit', 'Delivered', 'Delayed', 'Failed']

    status = serializers.CharField(required=True)
    reason = serializers.CharField(required=False, allow_blank=True, default='')

    def validate_status(self, value):
        normalized = value.strip()
        # Find exact case match or title case match
        for s in self.ALLOWED_STATUSES:
            if s.lower() == normalized.lower():
                return s
        raise serializers.ValidationError(
            f"Invalid status '{value}'. Allowed statuses: {', '.join(self.ALLOWED_STATUSES)}"
        )


class DeliveryReturnPickupSerializer(serializers.ModelSerializer):
    """
    Serializes a Return item for the Delivery Partner Return Pickup portal.
    Exposes all essential information needed by the driver to complete pickup.
    """
    order_id = serializers.SerializerMethodField()
    customer_name = serializers.CharField(source='customer.full_name', read_only=True, default='Valued Customer')
    customer_phone = serializers.CharField(source='customer.phone', read_only=True, default='')
    customer_email = serializers.CharField(source='customer.email', read_only=True, default='')
    customer_address = serializers.SerializerMethodField()
    customer_city = serializers.CharField(source='customer.city', read_only=True, default='')
    product_id = serializers.SerializerMethodField()
    product_name = serializers.SerializerMethodField()
    sku = serializers.SerializerMethodField()
    quantity = serializers.SerializerMethodField()
    pickup_status = serializers.CharField(source='return_status', read_only=True)
    assigned_employee_name = serializers.CharField(source='assigned_employee.full_name', read_only=True, default='')
    image = serializers.SerializerMethodField()

    class Meta:
        model = Return
        fields = [
            'return_id',
            'order_id',
            'customer_name',
            'customer_phone',
            'customer_email',
            'customer_address',
            'customer_city',
            'product_id',
            'product_name',
            'sku',
            'quantity',
            'return_reason',
            'condition_on_return',
            'refund_amount',
            'pickup_status',
            'return_status',
            'return_date',
            'pickup_date',
            'delivery_partner',
            'assigned_employee_id',
            'assigned_employee_name',
            'image',
        ]

    def get_order_id(self, obj):
        return obj.order_item.order_id if obj.order_item else None

    def get_customer_address(self, obj):
        if obj.order_item and obj.order_item.order_id:
            order = Order.objects.filter(order_id=obj.order_item.order_id).first()
            if order and order.shipping_address:
                return order.shipping_address
        if obj.customer:
            parts = [getattr(obj.customer, p, '') for p in ['city', 'state', 'country'] if getattr(obj.customer, p, '')]
            return ', '.join(parts)
        return 'Customer address on file'

    def get_product_id(self, obj):
        return obj.order_item.product_id if obj.order_item else None

    def get_product_name(self, obj):
        if obj.order_item and obj.order_item.product:
            return obj.order_item.product.product_name or 'Boutique Apparel'
        return 'Boutique Apparel'

    def get_sku(self, obj):
        if obj.order_item and obj.order_item.product:
            return obj.order_item.product.sku or ''
        return ''

    def get_quantity(self, obj):
        return getattr(obj.order_item, 'quantity', 1) if obj.order_item else 1

    def get_image(self, obj):
        if obj.order_item and obj.order_item.product and obj.order_item.product.category:
            cat_name = (obj.order_item.product.category.category_name or '').strip().lower()
            return CATEGORY_IMAGE_MAPPING.get(cat_name, None)
        return None


class ReturnPickupStatusUpdateSerializer(serializers.Serializer):
    ALLOWED_STATUSES = ['Pickup Accepted', 'Picked Up', 'Received at Warehouse', 'Failed']

    status = serializers.CharField(required=True)
    reason = serializers.CharField(required=False, allow_blank=True, default='')

    def validate_status(self, value):
        normalized = value.strip().lower()
        for s in self.ALLOWED_STATUSES:
            if s.lower() == normalized:
                return s
        raise serializers.ValidationError(
            f"Invalid status '{value}'. Allowed return pickup statuses: {', '.join(self.ALLOWED_STATUSES)}"
        )
