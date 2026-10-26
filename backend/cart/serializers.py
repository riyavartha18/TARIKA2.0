"""Serializers for the wishlist and cart responses.

The shapes here are the ones the customer pages already consume: a flat product
summary on each line (so a card can render name/price/image/category) plus the
nested `product` object the bag page groups by. Everything is derived from the
real `public.products` columns (`name`, `main_category`, `sub_category`,
`image`, `discount_price`, parsed `actual_price`, `available_quantity`) so the
prices shown here always match the catalogue.
"""

from rest_framework import serializers

from catalog.models import Product
from .models import WishlistItem, CartItem


def _stock_of(product):
    """Integer stock from `available_quantity`; None means 'not recorded'."""
    quantity = getattr(product, 'available_quantity', None)
    if quantity is None:
        return None
    try:
        return int(quantity)
    except (TypeError, ValueError):
        return None


def _unit_price(product):
    """Current selling price: `discount_price`, else the parsed list price."""
    price = getattr(product, 'selling_price', None)
    if price is None:
        price = getattr(product, 'base_price', None)
    return float(price) if price is not None else 0.0


def build_product_payload(product):
    """Flat product summary for one line, or blanks for a missing product."""
    if product is None:
        return {
            'product_id': None,
            'product_name': None,
            'category_id': None,
            'category_name': None,
            'sub_category': None,
            'base_price': 0,
            'selling_price': 0,
            'sale_price': 0,
            'primary_image': None,
            'image': None,
            'link': None,
            'total_stock': 0,
            'available_stock': 0,
            'in_stock': False,
        }

    category_name = (product.main_category or '').strip()
    category_id = category_name.lower().replace(' ', '-') if category_name else None
    unit_price = _unit_price(product)
    stock = _stock_of(product)
    image = product.image or None

    return {
        'product_id': product.product_id,
        'product_name': product.product_name,
        'category_id': category_id,
        'category_name': category_name or None,
        'sub_category': product.sub_category,
        # `base_price` is the list price parsed from the TEXT actual_price.
        'base_price': product.base_price if product.base_price is not None else unit_price,
        'selling_price': unit_price,
        # Alias kept for the shared pricing helper.
        'sale_price': unit_price,
        'primary_image': image,
        'image': image,
        'link': product.link,
        'total_stock': stock if stock is not None else 0,
        'available_stock': stock,
        'in_stock': stock is None or stock > 0,
    }


def _flat_line_fields(payload, extra):
    """Spread the product summary onto the line, then layer line-specific keys.

    Keeping one dict for both the flat keys and the nested `product` means a
    page can read `item.product_name` or `item.product.category_name` and get
    the same values.
    """
    line = dict(payload)
    line['product'] = payload
    line.update(extra)
    return line


class WishlistItemSerializer(serializers.Serializer):
    """One saved product for the current customer."""

    def to_representation(self, instance):
        payload = build_product_payload(instance.product)
        return _flat_line_fields(payload, {
            'id': instance.wishkey,
            'wishkey': instance.wishkey,
            'product_id': payload['product_id'] or instance.product_id,
        })


class AddToWishlistSerializer(serializers.Serializer):
    product_id = serializers.CharField(required=True, max_length=64)

    def validate_product_id(self, value):
        value = str(value or '').strip()
        if not value:
            raise serializers.ValidationError("A product id is required.")
        if not Product.objects.filter(product_id=value).exists():
            raise serializers.ValidationError("Product not found.")
        return value


class CartItemSerializer(serializers.Serializer):
    """One cart line, with its unit price, line total and stock flag."""

    def to_representation(self, instance):
        payload = build_product_payload(instance.product)
        quantity = int(instance.quantity or 0)
        unit_price = payload['selling_price']

        return _flat_line_fields(payload, {
            'id': instance.cartkey,
            'cartkey': instance.cartkey,
            'product_id': payload['product_id'] or instance.product_id,
            'quantity': quantity,
            'unit_price': round(unit_price, 2),
            'line_total': round(unit_price * quantity, 2),
            'is_stock_available': (
                payload['available_stock'] is None
                or payload['available_stock'] >= quantity
            ),
        })


class AddToCartSerializer(serializers.Serializer):
    product_id = serializers.CharField(required=True, max_length=64)
    quantity = serializers.IntegerField(required=False, default=1, min_value=1,
                                        max_value=99)

    def validate_product_id(self, value):
        value = str(value or '').strip()
        if not value:
            raise serializers.ValidationError("A product id is required.")
        if not Product.objects.filter(product_id=value).exists():
            raise serializers.ValidationError("Product not found.")
        return value

    def validate_quantity(self, value):
        if value is None:
            return 1
        return int(value)


class UpdateCartQuantitySerializer(serializers.Serializer):
    quantity = serializers.IntegerField(required=True, min_value=1, max_value=99)

    def validate_quantity(self, value):
        # Reject NaN / infinity / negatives before they reach the database.
        if value is None or int(value) < 1:
            raise serializers.ValidationError("Quantity must be at least 1.")
        return int(value)


# Kept so existing imports elsewhere in the project continue to work.
WishlistProductSummarySerializer = WishlistItemSerializer
CartProductSummarySerializer = CartItemSerializer
