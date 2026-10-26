"""Serializers for customer order payloads built from `public.orders` rows.

The response keeps the keys the customer pages already render (order_id,
order_date, order_status, total_amount, items[], delivery) but only fills them
from columns that exist. Fields the schema does not carry - shipping address,
payment status, warehouse, return records - are returned as null so the UI shows
its own neutral label instead of invented data.
"""

from rest_framework import serializers

from cart.serializers import build_product_payload
from .models import Order


def _iso_date(day_month_year):
    """'DD-MM-YYYY' (the stored text) -> 'YYYY-MM-DD', or None if unparsable."""
    raw = str(day_month_year or '').strip()
    parts = raw.split('-')
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        return None
    day, month, year = parts
    return f"{year}-{month.zfill(2)}-{day.zfill(2)}"


def build_order_item(order):
    """The single line of an order row, with product details joined in."""
    payload = build_product_payload(order.product)
    quantity = int(order.quantity or 1)
    # final_price is what the customer paid for this order (see services docstring).
    total = float(order.final_price or 0)
    unit_price = round(total / quantity, 2) if quantity else total
    rating = order.rating

    return {
        'order_item_id': order.order_id,
        'order_id': order.order_id,
        'product_id': payload['product_id'] or order.product_id,
        'product_name': payload['product_name'] or 'Fashion Apparel',
        'sku': payload['product_id'] or '',
        'image': payload['image'],
        'category_name': payload['category_name'],
        'sub_category': payload['sub_category'],
        'quantity': quantity,
        'unit_price': unit_price,
        'discount': float(order.additional_discount or 0),
        'subtotal': round(total, 2),
        # No returns table exists in this database.
        'return_info': None,
        # `orders.rating` is the only review column the schema has.
        'customer_review': (
            {
                'rating': rating,
                'review_text': None,
                'review_date': None,
                'is_verified_purchase': True,
            }
            if rating is not None else None
        ),
    }


class OrderDetailSerializer(serializers.Serializer):
    """One order, as returned to the My Orders and confirmation pages."""

    def to_representation(self, instance):
        order = instance
        item = build_order_item(order)
        customer = getattr(order, 'customer', None)
        iso_date = _iso_date(order.purchase_date)

        return {
            'order_id': order.order_id,
            # ISO for logic, the stored text for display.
            'order_date': iso_date,
            'order_date_display': order.purchase_date,
            'order_status': order.order_status,
            'delivery_status': order.delivery_status,
            # Not columns in this schema.
            'payment_status': None,
            'shipping_address': None,
            'warehouse_name': None,
            'payment_method': order.payment_method,
            'transaction_reference': None,
            'total_amount': item['subtotal'],
            'discount_amount': item['discount'],
            'initial_price': float(order.initial_price or 0),
            'customer_name': getattr(customer, 'full_name', None) or '',
            'customer_email': getattr(customer, 'email', None) or '',
            'items': [item],
            'delivery': {
                'delivery_status': order.delivery_status,
                'shipping_time_days': order.shipping_time_days,
            },
        }


class CheckoutRequestSerializer(serializers.Serializer):
    """
    Validates the checkout payload submitted from the frontend.

    Only Cash on Delivery is accepted (the schema has no payment records), and
    the address is validated for the confirmation message - `public.orders` has
    no address column, so nothing is persisted from it.
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
    payment_method = serializers.CharField(required=False, default='COD')

    def validate_shipping_address(self, value):
        cleaned = value.strip()
        if len(cleaned) < 5:
            raise serializers.ValidationError("Delivery address must be at least 5 characters long.")
        return cleaned

    def validate_payment_method(self, value):
        val = str(value or '').strip().upper()
        if val in ('COD', 'CASH ON DELIVERY'):
            return 'COD'
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
