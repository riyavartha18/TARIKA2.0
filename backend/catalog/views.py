import math
import uuid
from datetime import datetime
from django.db import DatabaseError
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework.pagination import PageNumberPagination
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404

from accounts.permissions import IsCustomer
from orders.models import Order
from .models import Category, Product, Review, OrderItem
from .serializers import (
    CategorySerializer,
    ProductListSerializer,
    ProductDetailSerializer,
    CategoryGroupedProductsSerializer,
    ReviewDetailSerializer,
    CATEGORY_IMAGE_MAPPING,
)


class GroupedCategoryProductsView(APIView):
    """
    GET /api/catalog/grouped-products/
    Returns products grouped according to their actual database categories.
    Publicly accessible or authenticated for Warehouse Manager.
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        categories = (
            Category.objects.annotate(
                active_prod_count=Count('products', filter=Q(products__is_active=True))
            )
            .filter(active_prod_count__gt=0)
            .order_by('category_name')
            .prefetch_related('products__category', 'products__manufacturer')
        )
        serializer = CategoryGroupedProductsSerializer(categories, many=True)
        return Response({
            'count': len(serializer.data),
            'categories': serializer.data
        }, status=status.HTTP_200_OK)

from .services import CatalogService


class StandardCatalogPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 20

    def get_paginated_response(self, data):
        total_pages = math.ceil(self.page.paginator.count / self.get_page_size(self.request))
        return Response({
            'count': self.page.paginator.count,
            'total_pages': total_pages,
            'current_page': self.page.number,
            'page_size': self.get_page_size(self.request),
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'results': data
        })


class CategoryListView(APIView):
    """
    GET /api/catalog/categories/
    Returns all available product categories with product count and image URLs.
    Publicly accessible.
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        # New `public.products` schema has no separate `categories` table.
        # Customer-facing categories are derived from the real `main_category`
        # column so navigation and filtering use actual database values.
        # One grouped query returns main_category + sub_category counts together
        # (avoids a second per-category query for subcategory navigation).
        rows = (
            Product.objects
            .exclude(main_category__isnull=True)
            .exclude(main_category='')
            .values('main_category', 'sub_category')
            .annotate(product_count=Count('product_id'))
            .order_by('main_category')
        )
        cat_map = {}
        for row in rows:
            name = (row['main_category'] or '').strip()
            if not name:
                continue
            entry = cat_map.setdefault(name, {
                'category_id': name,
                'category_name': name,
                'id': name,
                'name': name,
                'slug': name,
                'image': CATEGORY_IMAGE_MAPPING.get(name.lower(), None),
                'product_count': 0,
                'sub_categories': [],
            })
            entry['product_count'] += row['product_count']
            sub_name = (row['sub_category'] or '').strip()
            if sub_name and sub_name.lower() != name.lower():
                entry['sub_categories'].append({
                    'sub_category': sub_name,
                    'product_count': row['product_count'],
                })
        data = sorted(cat_map.values(), key=lambda c: c['category_name'])
        return Response(data, status=status.HTTP_200_OK)


class ProductListView(APIView):
    """
    GET /api/catalog/products/
    Returns paginated list of active products with support for:
      - category / sub_category and text search over product name/category columns
      - min_price / max_price, stock, sale, size, and color filters
      - sort: newest, price_low_high, price_high_low, name
    Responses contain at most 20 products; filtering and ordering happen before
    the database page slice.
    Publicly accessible.
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        category = request.query_params.get('category')
        sub_category = request.query_params.get('sub_category')
        search = request.query_params.get('search')
        min_price = request.query_params.get('min_price')
        max_price = request.query_params.get('max_price')
        in_stock = request.query_params.get('in_stock')
        on_sale = request.query_params.get('on_sale')
        size = request.query_params.get('size')
        color = request.query_params.get('color')
        subcategory_search = request.query_params.get('subcategory_search')
        sort = request.query_params.get('sort')

        queryset = CatalogService.filter_and_sort_products(
            category=category,
            sub_category=sub_category,
            search=search,
            min_price=min_price,
            max_price=max_price,
            in_stock=in_stock,
            sort=sort or 'newest',
            on_sale=on_sale,
            size=size,
            color=color,
            subcategory_search=subcategory_search,
        )

        queryset = queryset.only(*CatalogService.PRODUCT_LIST_FIELDS)
        paginator = StandardCatalogPagination()
        page = paginator.paginate_queryset(queryset, request)
        if page is not None:
            serializer = ProductListSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        serializer = ProductListSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ProductDetailView(APIView):
    """
    GET /api/catalog/products/<product_id>/
    Returns complete product details including:
      - All database columns
      - Category details
      - Total stock and in_stock flag
      - Warehouse inventory breakdown
      - Rating summary from reviews
    Publicly accessible.
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, product_id):
        # New `public.products` schema has no inventory/reviews tables, so the
        # product is fetched plainly. The serializer still exposes the same
        # response shape (total_stock / inventory_breakdown / rating_summary /
        # reviews default to safe empty values when those tables are absent).
        product = get_object_or_404(Product.objects.all(), product_id=product_id)
        serializer = ProductDetailSerializer(product)
        return Response(serializer.data, status=status.HTTP_200_OK)


class NewArrivalsView(APIView):
    """
    GET /api/catalog/new-arrivals/
    Returns the newest launched / added products.
    Supports standard page/page_size pagination (20 items maximum); retains a
    capped ?limit= response for existing homepage callers.
    Publicly accessible.
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        return _paginated_curated_products(request, CatalogService.get_new_arrivals())


class TrendingView(APIView):
    """
    GET /api/catalog/trending/
    Returns trending products based on total sales volume in order_items.
    Supports standard page/page_size pagination (20 items maximum); retains a
    capped ?limit= response for existing homepage callers.
    Publicly accessible.
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        try:
            queryset = CatalogService.get_trending()
            return _paginated_curated_products(request, queryset)
        except DatabaseError:
            return _paginated_curated_products(request, CatalogService.get_new_arrivals())


class SaleView(APIView):
    """
    GET /api/catalog/sale/
    Returns products on sale or promotional clearance.
    Supports standard page/page_size pagination (20 items maximum); retains a
    capped ?limit= response for existing homepage callers.
    Publicly accessible.
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        return _paginated_curated_products(request, CatalogService.get_sale_products())


def _paginated_curated_products(request, queryset):
    filters = {
        key: request.query_params.get(key)
        for key in (
            'category', 'sub_category', 'search', 'min_price', 'max_price',
            'in_stock', 'on_sale', 'size', 'color', 'subcategory_search'
        )
    }
    sort = request.query_params.get('sort')
    queryset = CatalogService.filter_and_sort_products(
        queryset=queryset,
        **filters,
        sort=sort if sort and sort != 'newest' else None,
    ).only(*CatalogService.PRODUCT_LIST_FIELDS)

    legacy_limit = request.query_params.get('limit')
    if legacy_limit is not None and 'page' not in request.query_params and 'page_size' not in request.query_params:
        try:
            limit = min(max(int(legacy_limit), 0), 20)
        except (TypeError, ValueError):
            limit = 20
        products = list(queryset[:limit])
        serializer = ProductListSerializer(products, many=True)
        return Response({
            'count': len(serializer.data),
            'results': serializer.data,
        }, status=status.HTTP_200_OK)

    paginator = StandardCatalogPagination()
    page = paginator.paginate_queryset(queryset, request)
    serializer = ProductListSerializer(page, many=True)
    return paginator.get_paginated_response(serializer.data)


class ProductReviewsView(APIView):
    """
    GET /api/catalog/products/<product_id>/reviews/
    Returns rating summary and reviews for a product. Publicly accessible.

    POST /api/catalog/products/<product_id>/reviews/
    Submits or updates a rating and written review for a product.
    Requires authenticated customer who has actually purchased this product.
    """
    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsCustomer()]
        return [AllowAny()]

    def get(self, request, product_id):
        product = get_object_or_404(Product, product_id=product_id)
        reviews = list(product.reviews.all())
        reviews.sort(key=lambda r: (r.review_date or '', r.review_id or ''), reverse=True)
        ratings = [r.rating for r in reviews if r.rating is not None]
        review_count = len(ratings)
        average_rating = round(sum(ratings) / review_count, 1) if review_count > 0 else None

        return Response({
            'product_id': product_id,
            'rating_summary': {
                'average_rating': average_rating,
                'review_count': review_count,
            },
            'count': len(reviews),
            'reviews': ReviewDetailSerializer(reviews[:100], many=True).data
        }, status=status.HTTP_200_OK)

    def post(self, request, product_id):
        product = get_object_or_404(Product, product_id=product_id)
        customer = getattr(request.user, 'profile', None)
        if not customer or not hasattr(customer, 'customer_id'):
            from accounts.models import Customer
            # The verified token subject is the public.customers primary key.
            customer = Customer.objects.filter(
                customer_id=getattr(request.user, 'auth_user_id', None)
            ).first()
        if not customer:
            return Response(
                {'detail': 'Customer account profile could not be found.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate input
        rating = request.data.get('rating')
        review_text = (request.data.get('review_text') or '').strip()

        try:
            rating = int(rating)
            if rating < 1 or rating > 5:
                raise ValueError()
        except (TypeError, ValueError):
            return Response(
                {'detail': 'Please select a star rating between 1 and 5.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not review_text:
            return Response(
                {'detail': 'Please write your review thoughts before submitting.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Purchase verification: Customer must have purchased this product
        customer_order_ids = Order.objects.filter(customer=customer).values_list('order_id', flat=True)
        purchased_item = OrderItem.objects.filter(
            product_id=product_id,
            order_id__in=customer_order_ids
        ).first()

        if not purchased_item:
            return Response(
                {'detail': 'Verified purchase required. You can only rate and review products you have purchased.'},
                status=status.HTTP_403_FORBIDDEN
            )

        order_id = purchased_item.order_id

        # Check for existing review by this customer for this product to prevent duplicate submissions
        existing_review = Review.objects.filter(
            customer_id=customer.customer_id,
            product_id=product_id
        ).first()

        today_str = datetime.now().strftime('%Y-%m-%d')

        if existing_review:
            existing_review.rating = rating
            existing_review.review_text = review_text
            existing_review.review_date = today_str
            existing_review.is_verified_purchase = True
            if order_id and not existing_review.order_id:
                existing_review.order_id = order_id
            existing_review.save()
            review = existing_review
            created = False
        else:
            review = Review.objects.create(
                review_id=str(uuid.uuid4()),
                product_id=product_id,
                customer_id=customer.customer_id,
                order_id=order_id,
                rating=rating,
                review_text=review_text,
                is_verified_purchase=True,
                review_date=today_str
            )
            created = True

        # Calculate authoritative updated rating summary from database
        all_reviews = Review.objects.filter(product_id=product_id)
        ratings = [r.rating for r in all_reviews if r.rating is not None]
        review_count = len(ratings)
        average_rating = round(sum(ratings) / review_count, 1) if review_count > 0 else float(rating)

        return Response({
            'message': 'Review submitted successfully.' if created else 'Review updated successfully.',
            'review': ReviewDetailSerializer(review).data,
            'rating_summary': {
                'average_rating': average_rating,
                'review_count': review_count,
            }
        }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)
