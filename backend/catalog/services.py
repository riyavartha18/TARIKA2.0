from django.db.models import (
    Q, Sum, F, OuterRef, Subquery, IntegerField, BigIntegerField
)
from django.db.models.functions import Coalesce
from django.db.models.expressions import RawSQL
from .models import Category, Product, Inventory, OrderItem, Review


class CatalogService:
    @staticmethod
    def get_annotated_products_queryset():
        """
        Returns a base queryset for active products with aggregated total_stock
        annotated using a subquery to avoid join Cartesian products.
        """
        stock_subquery = (
            Inventory.objects.filter(product=OuterRef('pk'))
            .values('product')
            .annotate(total=Sum('stock_quantity'))
            .values('total')
        )

        return (
            Product.objects.filter(is_active=True)
            .select_related('category')
            .annotate(
                total_stock_annotated=Coalesce(
                    Subquery(stock_subquery, output_field=IntegerField()),
                    0
                ),
                dim_selling_price=RawSQL(
                    '(SELECT dp.selling_price FROM dim_product dp '
                    'WHERE dp.product_id = products.product_id LIMIT 1)',
                    [],
                    output_field=BigIntegerField(),
                ),
            )
        )

    @classmethod
    def filter_and_sort_products(
        cls,
        queryset=None,
        category=None,
        search=None,
        min_price=None,
        max_price=None,
        sort=None
    ):
        if queryset is None:
            queryset = cls.get_annotated_products_queryset()

        # 1. Category filter: support category_id (UUID) or category_name (string)
        if category:
            category_str = str(category).strip()
            cat_lower = category_str.lower()
            if cat_lower in ['tops', 'top']:
                queryset = queryset.filter(
                    Q(category__category_name__iexact='Tops') |
                    Q(category__category_name__iexact='T-Shirts') |
                    Q(category__category_name__icontains='T-Shirt')
                )
            elif cat_lower in ['bottom wear', 'bottoms', 'bottom']:
                queryset = queryset.filter(
                    Q(category__category_name__iexact='Bottom Wear') |
                    Q(category__category_name__iexact='Trousers') |
                    Q(category__category_name__icontains='Trouser')
                )
            else:
                queryset = queryset.filter(
                    Q(category__category_id__iexact=category_str) |
                    Q(category__category_name__iexact=category_str) |
                    Q(category__category_name__icontains=category_str)
                )

        # 2. Text search across product_name, description, color, material, sku
        if search:
            search_str = str(search).strip()
            search_query = (
                Q(product_name__icontains=search_str) |
                Q(description__icontains=search_str) |
                Q(color__icontains=search_str) |
                Q(material__icontains=search_str) |
                Q(sku__icontains=search_str)
            )
            queryset = queryset.filter(search_query)

        # 3. Min price filter
        if min_price is not None:
            try:
                min_p = float(min_price)
                queryset = queryset.filter(dim_selling_price__gte=min_p)
            except (ValueError, TypeError):
                pass

        # 4. Max price filter
        if max_price is not None:
            try:
                max_p = float(max_price)
                queryset = queryset.filter(dim_selling_price__lte=max_p)
            except (ValueError, TypeError):
                pass

        # 5. Sorting
        sort_option = (sort or 'newest').lower().strip()
        if sort_option == 'newest':
            queryset = queryset.order_by('-launch_date', '-created_at', 'product_id')
        elif sort_option == 'price_low_high':
            queryset = queryset.order_by('dim_selling_price', 'product_name', 'product_id')
        elif sort_option == 'price_high_low':
            queryset = queryset.order_by('-dim_selling_price', 'product_name', 'product_id')
        elif sort_option == 'name':
            queryset = queryset.order_by('product_name', 'product_id')
        else:
            queryset = queryset.order_by('-launch_date', 'product_id')

        return queryset

    @classmethod
    def get_new_arrivals(cls, limit=12):
        """
        Returns latest launched / created active products.
        """
        qs = cls.get_annotated_products_queryset().order_by(
            '-launch_date',
            '-created_at',
            'product_id'
        )
        return qs[:limit] if limit else qs

    @classmethod
    def get_trending(cls, limit=12):
        """
        Returns trending products based on aggregated order sales volume (units ordered in order_items).
        Falls back to review count or launch date if order history is sparse.
        """
        sales_subquery = (
            OrderItem.objects.filter(product=OuterRef('pk'))
            .values('product')
            .annotate(total_sold=Sum('quantity'))
            .values('total_sold')
        )

        qs = cls.get_annotated_products_queryset().annotate(
            sales_volume=Coalesce(
                Subquery(sales_subquery, output_field=IntegerField()),
                0
            )
        ).order_by('-sales_volume', '-launch_date', 'product_id')

        return qs[:limit] if limit else qs

    @classmethod
    def get_sale_products(cls, limit=12):
        """
        Returns products currently on sale.
        Primary criterion: base_price > selling_price.
        Fallback criterion: If base_price == selling_price across the database,
        derives products that have historical promotional discounts recorded in order_items,
        or products offering the lowest clearance pricing.
        """
        base_qs = cls.get_annotated_products_queryset()

        # Primary: products where base_price > the warehouse selling price.
        sale_qs = base_qs.filter(
            base_price__gt=F('dim_selling_price')
        ).order_by('dim_selling_price')
        if sale_qs.exists():
            return sale_qs[:limit] if limit else sale_qs

        # Fallback 1: Products that have historical discounts in order_items
        discounted_product_ids = list(
            OrderItem.objects.filter(discount__gt=0)
            .values_list('product_id', flat=True)
            .distinct()[:50]
        )

        if discounted_product_ids:
            discount_qs = base_qs.filter(product_id__in=discounted_product_ids).order_by('dim_selling_price', 'product_id')
            return discount_qs[:limit] if limit else discount_qs

        # Fallback 2: Lowest price clearance
        clearance_qs = base_qs.order_by('dim_selling_price', 'product_id')
        return clearance_qs[:limit] if limit else clearance_qs
