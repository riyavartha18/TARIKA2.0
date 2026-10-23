from django.db import DatabaseError
from django.db.models import Q, Sum, F, OuterRef, Subquery, IntegerField
from django.db.models.functions import Coalesce
from .models import Product, OrderItem


class CatalogService:
    @staticmethod
    def get_annotated_products_queryset():
        """
        Returns a base queryset over the real public.products table.
        (Legacy stock annotation removed: the new schema has no inventory data.)
        """
        return Product.objects.all()

    @staticmethod
    def _parse_price_filter(value):
        """Parse a numeric query-string price filter defensively."""
        from .models import parse_product_price
        if value is None:
            return None
        cleaned = str(value).replace(',', '').strip()
        if not cleaned:
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None

    @classmethod
    def filter_and_sort_products(
        cls,
        queryset=None,
        category=None,
        sub_category=None,
        search=None,
        min_price=None,
        max_price=None,
        in_stock=None,
        sort=None
    ):
        if queryset is None:
            queryset = cls.get_annotated_products_queryset()

        # 1. Category filter: real schema has main_category / sub_category
        if category:
            category_str = str(category).strip()
            cat_lower = category_str.lower()
            if cat_lower in ['tops', 'top']:
                queryset = queryset.filter(
                    Q(sub_category__icontains='top') |
                    Q(sub_category__icontains='t-shirt')
                )
            elif cat_lower in ['bottom wear', 'bottoms', 'bottom']:
                queryset = queryset.filter(
                    Q(sub_category__icontains='bottom') |
                    Q(sub_category__icontains='trouser') |
                    Q(sub_category__icontains='jean')
                )
            else:
                queryset = queryset.filter(
                    Q(main_category__iexact=category_str) |
                    Q(main_category__icontains=category_str) |
                    Q(sub_category__iexact=category_str) |
                    Q(sub_category__icontains=category_str)
                )

        # 2. Sub-category filter on the real `sub_category` column
        if sub_category:
            sub_str = str(sub_category).strip()
            if sub_str:
                queryset = queryset.filter(
                    Q(sub_category__iexact=sub_str) |
                    Q(sub_category__icontains=sub_str)
                )

        # 3. Text search across real schema text columns
        if search:
            search_str = str(search).strip()
            search_query = (
                Q(product_name__icontains=search_str) |
                Q(main_category__icontains=search_str) |
                Q(sub_category__icontains=search_str)
            )
            queryset = queryset.filter(search_query)

        # 4. Min price filter (discount_price is the real discounted price)
        min_p = cls._parse_price_filter(min_price)
        if min_p is not None:
            queryset = queryset.filter(discount_price__gte=min_p)

        # 5. Max price filter
        max_p = cls._parse_price_filter(max_price)
        if max_p is not None:
            queryset = queryset.filter(discount_price__lte=max_p)

        # 6. In-stock filter uses the real `available_quantity` column
        #    (the new schema has no separate inventory table).
        if in_stock is not None and str(in_stock).strip().lower() in ('true', '1', 'yes'):
            queryset = queryset.filter(available_quantity__gt=0)

        # 7. Sorting (real schema has no launch_date / created_at columns,
        #    so 'newest' falls back to a stable product_key order)
        sort_option = (sort or 'newest').lower().strip()
        if sort_option == 'price_low_high':
            queryset = queryset.order_by('discount_price', 'product_name', 'product_id')
        elif sort_option == 'price_high_low':
            queryset = queryset.order_by('-discount_price', 'product_name', 'product_id')
        elif sort_option == 'name':
            queryset = queryset.order_by('product_name', 'product_id')
        else:
            queryset = queryset.order_by('product_id')

        return queryset

    @classmethod
    def get_new_arrivals(cls, limit=12):
        """
        Returns latest products. The new schema has no launch/created date
        column, so ordering is by product_key (stable catalogue order).
        """
        qs = cls.get_annotated_products_queryset().order_by('product_id')
        return qs[:limit] if limit else qs

    @classmethod
    def get_trending(cls, limit=12):
        """
        Returns trending products based on aggregated order sales volume,
        preserving the original sales-volume logic using the real orders
        table: SUM(orders."Quantity") per product_id.
        """
        sales_subquery = (
            OrderItem.objects.filter(product=OuterRef('pk'))
            .values('product')
            .annotate(total_sold=Sum('quantity'))
            .values('total_sold')
        )

        try:
            qs = cls.get_annotated_products_queryset().annotate(
                sales_volume=Coalesce(
                    Subquery(sales_subquery, output_field=IntegerField()),
                    0
                )
            ).order_by('-sales_volume', 'product_id')

            # Evaluate inside the try block so a missing source table is
            # detected here rather than during serialization in the view.
            return list(qs[:limit]) if limit else list(qs)
        except DatabaseError:
            # The legacy order_items source table may not exist in the new
            # database. Fall back to the stable catalogue order so the
            # trending endpoint keeps working with the same response shape.
            return cls.get_new_arrivals(limit=limit)

    @classmethod
    def get_sale_products(cls, limit=12):
        """
        Returns products currently on sale.
        Primary criterion (unchanged logic): base_price > selling_price,
        i.e. parsed actual_price (TEXT) > discount_price.
        Fallback criterion: lowest clearance pricing (mirrors the original
        fallback when no discounted products exist).
        """
        base_qs = cls.get_annotated_products_queryset()

        # Primary: products where actual_price (parsed) > discount_price.
        # Use an annotate + filter approach with RawSQL-free parsing done in
        # Python only when the queryset is small is NOT possible at 90k rows,
        # so parse via SQL: strip non-numeric characters then cast to float.
        from django.db.models.expressions import RawSQL

        base_qs = base_qs.annotate(
            parsed_base_price=RawSQL(
                "NULLIF(regexp_replace(products.actual_price, '[^0-9.]', '', 'g'), '')::float8",
                []
            )
        )

        sale_qs = base_qs.filter(
            parsed_base_price__gt=F('discount_price')
        ).order_by('discount_price', 'product_id')
        if sale_qs.exists():
            return sale_qs[:limit] if limit else sale_qs

        # Fallback: lowest price clearance (same as original fallback path)
        clearance_qs = base_qs.order_by('discount_price', 'product_id')
        return clearance_qs[:limit] if limit else clearance_qs
