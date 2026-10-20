from rest_framework import serializers
from .models import Order, Payment
from catalog.models import OrderItem, Review
from catalog.serializers import CATEGORY_IMAGE_MAPPING
from warehouse.models import Delivery, Return


class CheckoutRequestSerializer(serializers.Serializer):
    """
    Validates customer checkout payload submitted from the frontend.
    Currently, ONLY Cash on Delivery (COD) is permitted.
    Online Payment / UPI is disabled and will be rejected with an informative notice.
    """
    shipping_address = serializers.CharField(
        required=True,
        max_length=500,
        trim_whitespace=True,
        error_messages={'blank': 'Please enter a valid delivery address.'}
    )
    city = serializers.CharField(required=False, allow_blank=True, max_length=100, default='')
    state = serializers.CharField(required=False, allow_blank=True, max_length=100, default='')
    postal_code = serializers.CharField(required=False, allow_blank=True, max_length=20, default='')
    payment_method = serializers.CharField(
        required=False,
        default='COD'
    )

    def validate_shipping_address(self, value):
        cleaned = value.strip()
        if len(cleaned) < 5:
            raise serializers.ValidationError("Delivery address must be at least 5 characters long.")
        return cleaned

    def validate_payment_method(self, value):
        val = str(value).strip().upper()
        if val in ['COD', 'CASH ON DELIVERY']:
            return 'COD'
        if val in ['ONLINE', 'ONLINE PAYMENT', 'UPI', 'CREDIT CARD', 'DEBIT CARD', 'NET BANKING']:
            raise serializers.ValidationError(
                "Online payment is launching soon. Please choose Cash on Delivery to place your order."
            )
        raise serializers.ValidationError(
            "Online payment is launching soon. Please choose Cash on Delivery to place your order."
        )


class OrderReturnRequestSerializer(serializers.Serializer):
    order_item_id = serializers.CharField(
        required=True,
        error_messages={'blank': 'Please specify an item to return.'}
    )
    return_reason = serializers.CharField(
        required=True,
        max_length=255,
        error_messages={'blank': 'Please select a reason for returning.'}
    )
    condition_on_return = serializers.CharField(
        required=False,
        allow_blank=True,
        default='Unused, original packaging'
    )


class OrderItemDetailSerializer(serializers.ModelSerializer):
    """
    Serializes an order item for order detail, my orders, and confirmation views.
    Includes real catalog product images, customer's submitted review, and return/refund tracking data if applicable.
    """
    product_name = serializers.SerializerMethodField()
    sku = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()
    return_info = serializers.SerializerMethodField()
    customer_review = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = [
            'order_item_id',
            'order_id',
            'product_id',
            'product_name',
            'sku',
            'image',
            'quantity',
            'unit_price',
            'discount',
            'subtotal',
            'return_info',
            'customer_review',
        ]

    def get_product_name(self, obj):
        return obj.product.product_name if obj.product else 'Fashion Apparel'

    def get_sku(self, obj):
        return obj.product.sku if obj.product else ''

    def get_image(self, obj):
        if obj.product:
            if hasattr(obj.product, 'category') and obj.product.category:
                cat_name = (obj.product.category.category_name or '').strip().lower()
                if cat_name in CATEGORY_IMAGE_MAPPING:
                    return CATEGORY_IMAGE_MAPPING[cat_name]
            if getattr(obj.product, 'primary_image', None):
                return obj.product.primary_image
        return 'https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?auto=format&fit=crop&w=600&q=80'

    def get_return_info(self, obj):
        ret = Return.objects.filter(order_item_id=obj.order_item_id).first()
        if not ret:
            return None
        return {
            'return_id': ret.return_id,
            'return_status': ret.return_status,
            'return_reason': ret.return_reason,
            'return_date': ret.return_date,
            'refund_amount': ret.refund_amount,
            'condition_on_return': ret.condition_on_return,
            'assigned_employee_id': ret.assigned_employee_id,
            'delivery_partner': ret.delivery_partner,
            'pickup_date': ret.pickup_date,
        }

    def get_customer_review(self, obj):
        try:
            customer_id = self.context.get('customer_id')
            if not customer_id and obj.order_id:
                order = Order.objects.filter(order_id=obj.order_id).first()
                if order and order.customer:
                    customer_id = order.customer.customer_id
            if not customer_id:
                return None
            review = Review.objects.filter(product_id=obj.product_id, customer_id=customer_id).first()
            if not review:
                return None
            return {
                'review_id': review.review_id,
                'rating': review.rating,
                'review_text': review.review_text,
                'review_date': review.review_date,
                'is_verified_purchase': review.is_verified_purchase,
            }
        except Exception:
            return None


class OrderDetailSerializer(serializers.ModelSerializer):
    """
    Serializes complete order details including line items, payment info,
    and genuine delivery/tracking data.
    """
    items = serializers.SerializerMethodField()
    payment_method = serializers.SerializerMethodField()
    transaction_reference = serializers.SerializerMethodField()
    customer_name = serializers.SerializerMethodField()
    customer_email = serializers.SerializerMethodField()
    warehouse_name = serializers.SerializerMethodField()
    delivery = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            'order_id',
            'order_date',
            'order_status',
            'payment_status',
            'total_amount',
            'discount_amount',
            'shipping_address',
            'created_at',
            'updated_at',
            'customer_name',
            'customer_email',
            'warehouse_name',
            'payment_method',
            'transaction_reference',
            'items',
            'delivery',
        ]

    def get_items(self, obj):
        items = OrderItem.objects.filter(order_id=obj.order_id).select_related('product', 'product__category')
        cust_id = obj.customer.customer_id if obj.customer else None
        return OrderItemDetailSerializer(items, many=True, context={'customer_id': cust_id, 'order_id': obj.order_id}).data

    def get_payment_method(self, obj):
        payment = obj.payments.first()
        return payment.payment_method if payment else 'COD'

    def get_transaction_reference(self, obj):
        payment = obj.payments.first()
        return payment.transaction_reference if payment else ''

    def get_customer_name(self, obj):
        return obj.customer.full_name if obj.customer else ''

    def get_customer_email(self, obj):
        return obj.customer.email if obj.customer else ''

    def get_warehouse_name(self, obj):
        return obj.warehouse.warehouse_name if obj.warehouse else ''

    def get_delivery(self, obj):
        delivery = Delivery.objects.filter(order_id=obj.order_id).exclude(delivery_type__iexact='RETURN').first()
        if not delivery:
            return None
        return {
            'delivery_id': delivery.delivery_id,
            'delivery_type': delivery.delivery_type or 'FORWARD',
            'delivery_status': delivery.delivery_status,
            'delivery_partner': delivery.delivery_partner,
            'dispatch_date': delivery.dispatch_date,
            'expected_delivery_date': delivery.expected_delivery_date,
            'actual_delivery_date': delivery.actual_delivery_date,
            'failure_reason': delivery.failure_reason,
        }

