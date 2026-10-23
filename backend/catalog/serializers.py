from rest_framework import serializers
from .models import Category, Product, Inventory, Review, Manufacturer


class ManufacturerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Manufacturer
        fields = [
            'manufacturer_id',
            'manufacturer_name',
            'contact_person',
            'email',
            'phone',
            'country',
            'city',
            'state'
        ]


CATEGORY_IMAGE_MAPPING = {
    'dresses': 'https://images.unsplash.com/photo-1595777457583-95e059d581b8?w=600&auto=format&fit=crop&q=80',
    't-shirts': 'https://images.unsplash.com/photo-1521572267360-ee0c2909d518?w=600&auto=format&fit=crop&q=80',
    'tops': 'https://images.unsplash.com/photo-1564257631407-4deb1f99d992?w=600&auto=format&fit=crop&q=80',
    'shirts': 'https://images.unsplash.com/photo-1598033129183-c4f50c736f10?w=600&auto=format&fit=crop&q=80',
    'jeans': 'https://images.unsplash.com/photo-1541099649105-f69ad21f3246?w=600&auto=format&fit=crop&q=80',
    'trousers': 'https://images.unsplash.com/photo-1624378439575-d8705ad7ae80?w=600&auto=format&fit=crop&q=80',
    'bottom wear': 'https://images.unsplash.com/photo-1624378439575-d8705ad7ae80?w=600&auto=format&fit=crop&q=80',
    'kurtis': 'https://images.unsplash.com/photo-1610030469983-98e550d6193c?w=600&auto=format&fit=crop&q=80',
    'sarees': 'https://images.unsplash.com/photo-1617627143750-d86bc21e42bb?w=600&auto=format&fit=crop&q=80',
    'jackets': 'https://images.unsplash.com/photo-1551028719-00167b16eac5?w=600&auto=format&fit=crop&q=80',
    'sweaters': 'https://images.unsplash.com/photo-1576566588028-4147f3842f27?w=600&auto=format&fit=crop&q=80',
    'ethnic wear': 'https://images.unsplash.com/photo-1583391733956-3750e0ff4e8b?w=600&auto=format&fit=crop&q=80',
    'footwear': 'https://images.unsplash.com/photo-1543163521-1bf539c55dd2?w=600&auto=format&fit=crop&q=80',
    'handbags': 'https://images.unsplash.com/photo-1584917865442-de89df76afd3?w=600&auto=format&fit=crop&q=80',
    'accessories': 'https://images.unsplash.com/photo-1611652022419-a9419f74343d?w=600&auto=format&fit=crop&q=80',
    'kids wear': 'https://images.unsplash.com/photo-1514090458221-65bb69cf63e6?w=600&auto=format&fit=crop&q=80',
}


class CategorySerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()
    product_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Category
        fields = [
            'category_id',
            'category_name',
            'parent_category_id',
            'description',
            'image',
            'product_count',
            'created_at'
        ]

    def get_image(self, obj):
        name = (obj.category_name or '').strip().lower()
        return CATEGORY_IMAGE_MAPPING.get(name, None)


class WarehouseStockSerializer(serializers.ModelSerializer):
    warehouse_name = serializers.CharField(source='warehouse.warehouse_name', read_only=True)
    city = serializers.CharField(source='warehouse.city', read_only=True)
    state = serializers.CharField(source='warehouse.state', read_only=True)

    class Meta:
        model = Inventory
        fields = [
            'warehouse_id',
            'warehouse_name',
            'city',
            'state',
            'stock_quantity',
            'reorder_level',
            'last_restock_date'
        ]


class ReviewDetailSerializer(serializers.ModelSerializer):
    customer_name = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = [
            'review_id',
            'product_id',
            'customer_id',
            'customer_name',
            'order_id',
            'rating',
            'review_text',
            'sentiment_label',
            'sentiment_score',
            'is_verified_purchase',
            'review_date'
        ]

    def get_customer_name(self, obj):
        if not obj.customer_id:
            return "Verified Buyer"
        try:
            from accounts.models import Customer
            cust = Customer.objects.filter(customer_id=obj.customer_id).first()
            if cust and cust.full_name:
                return cust.full_name
        except Exception:
            pass
        return "Verified Buyer"


class ProductListSerializer(serializers.ModelSerializer):
    # New `public.products` schema has no category/manufacturer FKs.
    # Map main_category -> legacy response keys the UI already consumes.
    category_id = serializers.SerializerMethodField()
    category_name = serializers.CharField(source='main_category', read_only=True)
    sub_category = serializers.CharField(read_only=True)
    link = serializers.CharField(read_only=True)
    base_price = serializers.SerializerMethodField()
    selling_price = serializers.SerializerMethodField()
    in_stock = serializers.SerializerMethodField()
    total_stock = serializers.SerializerMethodField()
    # Raw nullable stock value straight from `available_quantity` — lets the
    # Warehouse UI tell a real 0 apart from missing/unavailable stock data.
    available_quantity = serializers.FloatField(read_only=True)
    rating_summary = serializers.SerializerMethodField()
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
            'rating_summary',
            'image'
        ]

    def get_category_id(self, obj):
        name = (obj.main_category or '').strip().lower()
        return name.replace(' ', '-') if name else None

    def get_base_price(self, obj):
        # Real `actual_price` TEXT column, parsed to float by the model property.
        return obj.base_price

    def get_selling_price(self, obj):
        # Real `discount_price` column, exposed via the model property.
        return obj.selling_price

    def get_total_stock(self, obj):
        # New schema carries availability directly on the product row
        # (`available_quantity`); there is no separate inventory table.
        if hasattr(obj, 'total_stock_annotated') and obj.total_stock_annotated is not None:
            return int(obj.total_stock_annotated)
        qty = getattr(obj, 'available_quantity', None)
        if qty is None:
            return 0
        try:
            return int(qty)
        except (TypeError, ValueError):
            return 0

    def get_in_stock(self, obj):
        return self.get_total_stock(obj) > 0

    def get_rating_summary(self, obj):
        cache = getattr(obj, '_prefetched_objects_cache', None) or {}
        if 'reviews' not in cache:
            # New schema has no reviews source; return a neutral summary
            # instead of issuing a per-product query.
            return {'average_rating': None, 'review_count': 0}
        try:
            reviews = cache['reviews']
            ratings = [r.rating for r in reviews if getattr(r, 'rating', None) is not None]
            count = len(ratings)
            avg = round(sum(ratings) / count, 1) if count > 0 else None
            return {'average_rating': avg, 'review_count': count}
        except Exception:
            return {'average_rating': None, 'review_count': 0}

    def get_image(self, obj):
        # Use the real `image` column; fall back to category artwork when empty.
        if obj.image:
            return obj.image
        cat_name = (obj.main_category or '').strip().lower()
        return CATEGORY_IMAGE_MAPPING.get(cat_name, None)


class ProductDetailSerializer(serializers.ModelSerializer):
    # New `public.products` schema mapping (see ProductListSerializer above).
    category_id = serializers.SerializerMethodField()
    category_name = serializers.CharField(source='main_category', read_only=True)
    sub_category = serializers.CharField(read_only=True)
    link = serializers.CharField(read_only=True)
    base_price = serializers.SerializerMethodField()
    selling_price = serializers.SerializerMethodField()
    in_stock = serializers.SerializerMethodField()
    total_stock = serializers.SerializerMethodField()
    inventory_breakdown = serializers.SerializerMethodField()
    rating_summary = serializers.SerializerMethodField()
    reviews = serializers.SerializerMethodField()
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
            'inventory_breakdown',
            'rating_summary',
            'reviews',
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
        # New schema carries availability on the product row (`available_quantity`).
        if hasattr(obj, 'total_stock_annotated') and obj.total_stock_annotated is not None:
            return int(obj.total_stock_annotated)
        qty = getattr(obj, 'available_quantity', None)
        if qty is None:
            return 0
        try:
            return int(qty)
        except (TypeError, ValueError):
            return 0

    def get_in_stock(self, obj):
        return self.get_total_stock(obj) > 0

    def get_inventory_breakdown(self, obj):
        cache = getattr(obj, '_prefetched_objects_cache', None) or {}
        if 'inventory_items' not in cache:
            # New schema has no warehouse inventory table; skip the query.
            return []
        return WarehouseStockSerializer(cache['inventory_items'], many=True).data

    def get_rating_summary(self, obj):
        cache = getattr(obj, '_prefetched_objects_cache', None) or {}
        if 'reviews' not in cache:
            return {'average_rating': None, 'review_count': 0}
        try:
            reviews = cache['reviews']
            ratings = [r.rating for r in reviews if getattr(r, 'rating', None) is not None]
            review_count = len(ratings)
            average_rating = round(sum(ratings) / review_count, 1) if review_count > 0 else None
            return {
                'average_rating': average_rating,
                'review_count': review_count
            }
        except (Exception, AssertionError):
            return {'average_rating': None, 'review_count': 0}

    def get_reviews(self, obj):
        cache = getattr(obj, '_prefetched_objects_cache', None) or {}
        if 'reviews' not in cache:
            return []
        try:
            rev_list = list(cache['reviews'])
            # Sort newest first
            rev_list.sort(key=lambda r: (r.review_date or '', r.review_id or ''), reverse=True)
            return ReviewDetailSerializer(rev_list[:50], many=True).data
        except Exception:
            return []

    def get_image(self, obj):
        # Use the real `image` column; fall back to category artwork when empty.
        if obj.image:
            return obj.image
        cat_name = (obj.main_category or '').strip().lower()
        return CATEGORY_IMAGE_MAPPING.get(cat_name, None)


class CategoryGroupedProductsSerializer(serializers.ModelSerializer):
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
        prods = obj.products.filter(is_active=True).select_related('category', 'manufacturer')
        return ProductListSerializer(prods, many=True).data

    def get_product_count(self, obj):
        return obj.products.filter(is_active=True).count()

