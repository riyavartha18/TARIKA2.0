from rest_framework import serializers
from django.db.models import Sum
from catalog.pricing import get_dim_product_selling_price_map
from catalog.models import Product, Inventory
from catalog.serializers import ProductListSerializer, CATEGORY_IMAGE_MAPPING
from .models import WishlistItem, CartItem


class WishlistProductSummarySerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.category_name', read_only=True)
    in_stock = serializers.SerializerMethodField()
    total_stock = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'product_id',
            'product_name',
            'category_name',
            'sku',
            'color',
            'size',
            'material',
            'base_price',
            'selling_price',
            'in_stock',
            'total_stock',
            'image'
        ]

    def get_total_stock(self, obj):
        if hasattr(obj, '_total_stock_cached'):
            return obj._total_stock_cached
        try:
            total = sum(i.stock_quantity or 0 for i in obj.inventory_items.all())
            return total
        except Exception:
            return 0

    def get_in_stock(self, obj):
        return self.get_total_stock(obj) > 0

    def get_image(self, obj):
        cat_name = (obj.category.category_name if obj.category else '').strip().lower()
        return CATEGORY_IMAGE_MAPPING.get(cat_name, None)


class WishlistItemSerializer(serializers.ModelSerializer):
    product = WishlistProductSummarySerializer(read_only=True)
    product_id = serializers.CharField(source='product.product_id', read_only=True)

    class Meta:
        model = WishlistItem
        fields = [
            'id',
            'product_id',
            'product',
            'created_at'
        ]


class AddToWishlistSerializer(serializers.Serializer):
    product_id = serializers.CharField(required=True)

    def validate_product_id(self, value):
        value = str(value).strip()
        try:
            product = Product.objects.get(product_id=value, is_active=True)
        except Product.DoesNotExist:
            raise serializers.ValidationError("Product not found or is currently inactive.")
        return value


class CartProductSummarySerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.category_name', read_only=True)
    selling_price = serializers.SerializerMethodField()
    available_stock = serializers.SerializerMethodField()
    in_stock = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'product_id',
            'product_name',
            'category_name',
            'sku',
            'color',
            'size',
            'material',
            'base_price',
            'selling_price',
            'in_stock',
            'available_stock',
            'image'
        ]

    def get_available_stock(self, obj):
        if hasattr(obj, '_available_stock_cached'):
            return obj._available_stock_cached
        try:
            return sum(i.stock_quantity or 0 for i in obj.inventory_items.all())
        except Exception:
            return 0

    def get_selling_price(self, obj):
        if not hasattr(obj, '_dim_product_selling_price'):
            price_map = get_dim_product_selling_price_map([obj.product_id])
            obj._dim_product_selling_price = price_map.get(str(obj.product_id)) or 0
        return obj._dim_product_selling_price

    def get_in_stock(self, obj):
        return self.get_available_stock(obj) > 0

    def get_image(self, obj):
        cat_name = (obj.category.category_name if obj.category else '').strip().lower()
        return CATEGORY_IMAGE_MAPPING.get(cat_name, None)


class CartItemSerializer(serializers.ModelSerializer):
    product = CartProductSummarySerializer(read_only=True)
    product_id = serializers.CharField(source='product.product_id', read_only=True)
    unit_price = serializers.SerializerMethodField()
    line_total = serializers.SerializerMethodField()
    is_stock_available = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = [
            'id',
            'product_id',
            'product',
            'quantity',
            'unit_price',
            'line_total',
            'is_stock_available',
            'created_at',
            'updated_at'
        ]

    def get_unit_price(self, obj):
        return self._get_dim_product_selling_price(obj.product)

    def get_line_total(self, obj):
        price = self._get_dim_product_selling_price(obj.product)
        return (obj.quantity or 0) * price

    @staticmethod
    def _get_dim_product_selling_price(product):
        if not product:
            return 0
        if not hasattr(product, '_dim_product_selling_price'):
            price_map = get_dim_product_selling_price_map([product.product_id])
            product._dim_product_selling_price = price_map.get(str(product.product_id)) or 0
        return product._dim_product_selling_price

    def get_is_stock_available(self, obj):
        if not obj.product:
            return False
        try:
            available = sum(i.stock_quantity or 0 for i in obj.product.inventory_items.all())
            return available >= (obj.quantity or 0)
        except Exception:
            return True


class AddToCartSerializer(serializers.Serializer):
    product_id = serializers.CharField(required=True)
    quantity = serializers.IntegerField(default=1, min_value=1)

    def validate_product_id(self, value):
        value = str(value).strip()
        try:
            product = Product.objects.get(product_id=value, is_active=True)
        except Product.DoesNotExist:
            raise serializers.ValidationError("Product not found or is currently inactive.")
        return value


class UpdateCartQuantitySerializer(serializers.Serializer):
    quantity = serializers.IntegerField(required=True, min_value=1)
