import re

from django.db import connection
# from django.db.models import Q, F, FloatField, RawSQL
from django.db.models import Q, F, FloatField
from django.db.models.expressions import RawSQL
from .models import Product
from .category_mapping import get_editorial_filter


class CatalogService:
    PRODUCT_LIST_FIELDS = (
        'product_id',
        'product_name',
        'main_category',
        'sub_category',
        'link',
        'discount_price',
        'actual_price_text',
        'discounted_price',
        'available_quantity',
        'image',
        'is_image_valid',
    )

    # The selling price the customer actually pays: the real `discounted_price`
    # column, falling back to the parsed TEXT `actual_price` (the ORIGINAL price)
    # for a row that carries no discounted value. Both columns exist in this
    # schema; `initial_price` does not, so nothing here may reference it.
    SELLING_PRICE_SQL = (
        "COALESCE(products.discounted_price, "
        "NULLIF(regexp_replace(products.actual_price, '[^0-9.]', '', 'g'), '')::float8)"
    )
    # The original (strikethrough) price = parsed TEXT `actual_price`.
    ORIGINAL_PRICE_SQL = (
        "NULLIF(regexp_replace(products.actual_price, '[^0-9.]', '', 'g'), '')::float8"
    )

    @staticmethod
    def get_annotated_products_queryset():
        """
        Returns a base queryset over the real public.products table.

        Customer-facing visibility rules, both read from the product row:
          * ``is_active`` - an archived (soft-deleted) product is gone from every
            storefront, search and curated rail;
          * ``hidden`` - a hidden product stays in the catalog for the warehouse
            and admin views but is never offered to a shopper.
        Stock is carried on the row itself (`available_quantity`); this schema has
        no inventory table.
        """
        # return Product.objects.filter(is_active=True).exclude(hidden=True)
        return Product.objects.filter(
            is_image_valid=True,
            is_active=True,
            hidden=False,
        ).exclude(
            Q(image__isnull=True) | Q(image='')
        )

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
        sort=None,
        on_sale=None,
        size=None,
        color=None,
        subcategory_search=None,
        starts_with=None,
    ):
        if queryset is None:
            queryset = cls.get_annotated_products_queryset()

        # 1. Category filter: supports editorial titles (e.g. "The Dress Story", "Dresses")
        #    as well as real schema main_category / sub_category
        if category:
            category_str = str(category).strip()
            editorial_q = get_editorial_filter(category_str)
            if editorial_q is not None:
                queryset = queryset.filter(editorial_q)
            else:
                queryset = queryset.filter(
                    Q(main_category__iexact=category_str) |
                    Q(main_category__icontains=category_str) |
                    Q(sub_category__iexact=category_str) |
                    Q(sub_category__icontains=category_str)
                )

        # 2. Sub-category filter on real sub_category column or product name
        if sub_category:
            sub_str = str(sub_category).strip()
            if sub_str and not sub_str.lower().startswith('all'):
                sub_editorial_q = get_editorial_filter(sub_str)
                if sub_editorial_q is not None:
                    queryset = queryset.filter(sub_editorial_q)
                else:
                    queryset = queryset.filter(
                        Q(sub_category__iexact=sub_str) |
                        Q(sub_category__icontains=sub_str) |
                        Q(product_name__icontains=sub_str)
                    )

        # 3. Text search across real schema text columns
        if search:
            search_str = str(search).strip()
            search_query = (
                Q(product_id__icontains=search_str) |
                Q(product_name__icontains=search_str) |
                Q(main_category__icontains=search_str) |
                Q(sub_category__icontains=search_str)
            )
            queryset = queryset.filter(search_query)

        # 3b. Custom letter filter ("Sort By Custom"): keep products whose
        #     name starts with a single A-Z letter, matched case-insensitively
        #     so 'a' and 'A' behave the same. Invalid input is ignored so the
        #     regular listing keeps working.
        letter = str(starts_with or '').strip()
        if re.fullmatch(r'[A-Za-z]', letter):
            queryset = queryset.filter(product_name__istartswith=letter)

        if subcategory_search:
            keyword = str(subcategory_search).strip()
            if keyword:
                queryset = queryset.filter(
                    Q(product_name__icontains=keyword) |
                    Q(sub_category__icontains=keyword)
                )

        # 3b. Alphabetical starts_with filter on actual product_name (case-insensitive)
        if starts_with:
            letter = str(starts_with).strip()
            if letter and letter.lower() != 'all' and len(letter) == 1 and letter.isalpha():
                queryset = queryset.filter(product_name__istartswith=letter)

        if size:
            # Size is not a column in the current Supabase products schema.
            # Match it as a whole token in the product name rather than
            # filtering a page of products in the client.
            size_token = str(size).strip()
            if size_token:
                queryset = queryset.filter(
                    product_name__iregex=rf'(^|[^[:alnum:]]){re.escape(size_token)}([^[:alnum:]]|$)'
                )

        if color:
            color_term = str(color).strip()
            if color_term:
                queryset = queryset.filter(
                    Q(product_name__icontains=color_term) |
                    Q(main_category__icontains=color_term) |
                    Q(sub_category__icontains=color_term)
                )

        min_p = cls._parse_price_filter(min_price)
        max_p = cls._parse_price_filter(max_price)
        sort_option = str(sort or '').lower().strip()
        needs_price_annotation = (
            min_p is not None or max_p is not None or
            (on_sale is not None and str(on_sale).strip().lower() in ('true', '1', 'yes')) or
            sort_option in ('price_low_high', 'price_high_low')
        )
        # Price filtering, "on sale" and price sorting all work on the FINAL
        # selling price (`discounted_price`), with the original price annotated
        # alongside so a real discount can be recognised as
        # selling < original rather than as a non-zero discount amount column.
        if needs_price_annotation:
            queryset = queryset.annotate(
                parsed_selling_price=RawSQL(
                    cls.SELLING_PRICE_SQL, [], output_field=FloatField(),
                ),
                parsed_original_price=RawSQL(
                    cls.ORIGINAL_PRICE_SQL, [], output_field=FloatField(),
                ),
            )

        # 4. Min price filter uses the effective displayed (final) price.
        if min_p is not None:
            queryset = queryset.filter(parsed_selling_price__gte=min_p)

        # 5. Max price filter
        if max_p is not None:
            queryset = queryset.filter(parsed_selling_price__lte=max_p)

        # 6. In-stock filter uses the real `available_quantity` column
        #    (the new schema has no separate inventory table).
        if in_stock is not None and str(in_stock).strip().lower() in ('true', '1', 'yes'):
            queryset = queryset.filter(available_quantity__gt=0)

        # "On sale" means the selling price really is below the original price.
        # `discount_price` holds a currency AMOUNT, so a positive amount alone is
        # not evidence of a discount (and can never be read as a percentage).
        if on_sale is not None and str(on_sale).strip().lower() in ('true', '1', 'yes'):
            queryset = queryset.filter(parsed_selling_price__lt=F('parsed_original_price'))

        # 7. Sorting (real schema has no launch_date / created_at columns,
        #    so 'newest' falls back to a stable product_key order)
        if sort is not None:
            if sort_option == 'price_low_high':
                queryset = queryset.order_by(
                    'parsed_selling_price',
                    'product_name',
                    'product_id',
                )
            elif sort_option == 'price_high_low':
                queryset = queryset.order_by(
                    F('parsed_selling_price').desc(),
                    'product_name',
                    'product_id',
                )
            elif sort_option == 'name':
                queryset = queryset.order_by('product_name', 'product_id')
            elif sort_option == 'custom_letter':
                # Custom-letter mode lists the letter-matched names A to Z
                queryset = queryset.order_by('product_name', 'product_id')
            elif sort_option == 'newest':
                queryset = queryset.order_by('product_id')

        return queryset

    NEW_ARRIVALS_KEYS = [f"P1000{i:02d}" for i in range(1, 41)]

    @classmethod
    def get_new_arrivals(cls, limit=None):
        """
        Returns exclusively the 40 newly added curated products (P100001 - P100040),
        removing all legacy catalog items from the New In section.
        """
        qs = cls.get_annotated_products_queryset().filter(
            product_id__in=cls.NEW_ARRIVALS_KEYS
        ).order_by('product_id')
        return qs[:limit] if limit else qs

    @classmethod
    def get_trending(cls, limit=None):
        """
        Returns trending products ranked by real sales volume.

        Volume is the quantity sold from DELIVERED orders only (a returned or
        in-transit order is not a completed sale), aggregated from the real
        `public.orders` table that this schema actually has. The legacy
        `order_items` table this method used to read does not exist here, so the
        aggregation is done in one grouped query and the products are then
        fetched in that rank order. If the aggregation is unavailable for any
        reason the stable catalogue order is used instead of failing.
        """
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT o.product_id
                      FROM public.orders o
                     WHERE LOWER(TRIM(COALESCE(o.delivery_status, ''))) = 'delivered'
                       AND o.product_id IS NOT NULL
                     GROUP BY o.product_id
                     ORDER BY SUM(COALESCE(o.quantity, 0)) DESC, o.product_id
                     LIMIT %s
                    """,
                    [limit or 12],
                )
                ranked_ids = [row[0] for row in cursor.fetchall()]
        except Exception:
            ranked_ids = []

        if not ranked_ids:
            return cls.get_new_arrivals(limit=limit)

        by_id = {
            p.product_id: p
            for p in cls.get_annotated_products_queryset().filter(product_id__in=ranked_ids)
        }
        ordered = [by_id[pid] for pid in ranked_ids if pid in by_id]
        if not ordered:
            return cls.get_new_arrivals(limit=limit)

        # Fewer eligible products than the rail asked for: top up with the
        # stable catalogue order so the rail still fills.
        if limit and len(ordered) < limit:
            existing = {p.product_id for p in ordered}
            filler = [p for p in cls.get_new_arrivals(limit=limit * 2) if p.product_id not in existing]
            ordered.extend(filler[:limit - len(ordered)])
        return ordered[:limit] if limit else ordered

    @classmethod
    def get_sale_products(cls, limit=None):
        """
        Returns products that are genuinely on sale: the FINAL selling price
        (`discounted_price`) below the original price held in the TEXT
        `actual_price` column, biggest currency saving first.

        `discount_price` is an AMOUNT, so a positive amount alone is not proof of
        a discount; the two prices decide.
        Fallback criterion: lowest final selling price (mirrors the original
        fallback when no discounted products exist).
        """
        base_qs = cls.get_annotated_products_queryset()

        sale_qs = base_qs.annotate(
            parsed_selling_price=RawSQL(
                cls.SELLING_PRICE_SQL, [], output_field=FloatField(),
            ),
            parsed_original_price=RawSQL(
                cls.ORIGINAL_PRICE_SQL, [], output_field=FloatField(),
            ),
            parsed_discount_value=RawSQL(
                f"COALESCE({cls.ORIGINAL_PRICE_SQL}, 0)"
                f" - COALESCE({cls.SELLING_PRICE_SQL}, 0)",
                [], output_field=FloatField(),
            ),
        ).filter(
            parsed_discount_value__gt=0
        ).order_by('-parsed_discount_value', 'product_id')
        if sale_qs.exists():
            return sale_qs[:limit] if limit else sale_qs

        # Fallback: lowest price clearance — cheapest final selling price
        # first (parsed actual_price TEXT column).
        clearance_qs = base_qs.annotate(
            parsed_selling_price=RawSQL(
                cls.SELLING_PRICE_SQL, [], output_field=FloatField(),
            )
        ).order_by('parsed_selling_price', 'product_id')
        return clearance_qs[:limit] if limit else clearance_qs
