import logging
from decimal import Decimal
from django.db import connection, transaction
from django.db.models import Q
import pandas as pd
from mlxtend.preprocessing import TransactionEncoder
from mlxtend.frequent_patterns import apriori, association_rules

import re
from catalog.models import Product
from catalog.serializers import sanitize_product_image_url
from accounts.models import Customer
from orders.models import Order
from cart.services import CustomerResolver
from .models import ProductRecommendation
from .outfit_validator import (
    validate_outfit,
    OCCASION_RULES,
    ALLOWED_STYLE_PAIRS,
    NEUTRAL_COLORS,
    COLOR_CLASH_PAIRS,
)

logger = logging.getLogger(__name__)


class RecommendationService:
    """
    Service containing the core business logic for:
      1. Extracting historical transaction data from delivered customer orders.
      2. Mining frequent itemsets with the Apriori algorithm.
      3. Generating directional product association rules.
      4. Persisting updated rules into the product_recommendations table safely.
      5. Retrieving recommendations for individual products.
    """

    DEFAULT_MIN_SUPPORT = 0.001
    DEFAULT_MIN_CONFIDENCE = 0.0

    @classmethod
    def fetch_delivered_order_items(cls):
        """
        Executes a SQL query joining orders and products
        for orders with status 'Delivered' containing multi-item baskets.
        Returns a pandas DataFrame with columns: order_id, product_id, product_name.
        """
        query = """
        SELECT
            CONCAT(o.customer_id, '_', o.purchase_date) AS order_id,
            o.product_id,
            p.name AS product_name
        FROM orders o
        JOIN products p ON o.product_id = p.product_key
        WHERE o.delivery_status = 'Delivered'
          AND p.name IS NOT NULL
          AND TRIM(p.name) != ''
          AND CONCAT(o.customer_id, '_', o.purchase_date) IN (
              SELECT CONCAT(customer_id, '_', purchase_date)
              FROM orders
              WHERE delivery_status = 'Delivered'
              GROUP BY customer_id, purchase_date
              HAVING COUNT(DISTINCT product_id) >= 2
          );
        """
        with connection.cursor() as cursor:
            cursor.execute(query)
            columns = [col[0] for col in cursor.description]
            rows = cursor.fetchall()

        if not rows:
            return pd.DataFrame(columns=['order_id', 'product_id', 'product_name'])

        return pd.DataFrame(rows, columns=columns)

    @classmethod
    def build_transactions(cls, df):
        """
        Groups DataFrame by order_id to construct basket transactions.
        Each transaction is a list of unique product names purchased in an order.
        """
        if df.empty:
            return []

        # Ensure product names are clean strings and remove duplicates per order
        transactions = (
            df.groupby("order_id")["product_name"]
              .apply(lambda names: list(dict.fromkeys(n.strip() for n in names if n and n.strip())))
              .tolist()
        )
        # Filter out empty transactions
        return [t for t in transactions if len(t) > 0]

    @classmethod
    def generate_recommendations(
        cls,
        min_support=DEFAULT_MIN_SUPPORT,
        min_confidence=DEFAULT_MIN_CONFIDENCE
    ):
        """
        Runs the full Apriori association rule mining pipeline:
          1. Fetches delivered order items.
          2. Builds transactions.
          3. Applies TransactionEncoder.
          4. Computes frequent itemsets via Apriori with min_support.
          5. Generates association rules via mlxtend.
          6. Extracts directional 1-to-1 product recommendations.

        Returns a dictionary containing pipeline results, metadata, and the rule records.
        """
        df = cls.fetch_delivered_order_items()

        delivered_orders_count = int(df['order_id'].nunique()) if not df.empty else 0
        products_count = int(df['product_name'].nunique()) if not df.empty else 0

        # Handle no delivered orders
        if df.empty or delivered_orders_count == 0:
            return {
                'success': False,
                'message': 'No delivered orders found in database.',
                'delivered_orders_count': 0,
                'products_count': 0,
                'frequent_itemsets_count': 0,
                'rules_count': 0,
                'rules': []
            }

        transactions = cls.build_transactions(df)

        if not transactions or len(transactions) == 0:
            return {
                'success': False,
                'message': 'No valid transactions found in delivered orders.',
                'delivered_orders_count': delivered_orders_count,
                'products_count': products_count,
                'frequent_itemsets_count': 0,
                'rules_count': 0,
                'rules': []
            }

        if products_count < 2:
            return {
                'success': False,
                'message': 'Insufficient unique products to calculate product associations.',
                'delivered_orders_count': delivered_orders_count,
                'products_count': products_count,
                'frequent_itemsets_count': 0,
                'rules_count': 0,
                'rules': []
            }

        # Apply TransactionEncoder
        te = TransactionEncoder()
        te_ary = te.fit(transactions).transform(transactions)
        basket = pd.DataFrame(te_ary, columns=te.columns_)

        # Run Apriori
        frequent_itemsets = apriori(
            basket,
            min_support=min_support,
            use_colnames=True
        )

        frequent_itemsets_count = len(frequent_itemsets)

        if frequent_itemsets.empty:
            return {
                'success': False,
                'message': f'No frequent itemsets found meeting min_support={min_support}.',
                'delivered_orders_count': delivered_orders_count,
                'products_count': products_count,
                'frequent_itemsets_count': 0,
                'rules_count': 0,
                'rules': []
            }

        # Check for itemsets with length >= 2
        multi_itemsets = frequent_itemsets[
            frequent_itemsets['itemsets'].apply(len) >= 2
        ]

        if multi_itemsets.empty:
            return {
                'success': False,
                'message': 'No frequent itemsets containing 2 or more products were found.',
                'delivered_orders_count': delivered_orders_count,
                'products_count': products_count,
                'frequent_itemsets_count': frequent_itemsets_count,
                'rules_count': 0,
                'rules': []
            }

        # Generate association rules
        try:
            rules = association_rules(
                frequent_itemsets,
                metric="confidence",
                min_threshold=min_confidence
            )
        except Exception as e:
            logger.error(f"Error computing association rules: {e}")
            return {
                'success': False,
                'message': f'Error generating association rules: {str(e)}',
                'delivered_orders_count': delivered_orders_count,
                'products_count': products_count,
                'frequent_itemsets_count': frequent_itemsets_count,
                'rules_count': 0,
                'rules': []
            }

        if rules.empty:
            return {
                'success': False,
                'message': 'No association rules met the specified criteria.',
                'delivered_orders_count': delivered_orders_count,
                'products_count': products_count,
                'frequent_itemsets_count': frequent_itemsets_count,
                'rules_count': 0,
                'rules': []
            }

        # Filter for 1-to-1 directional product rules: (A) -> (B)
        rules_1to1 = rules[
            (rules["antecedents"].apply(len) == 1) &
            (rules["consequents"].apply(len) == 1)
        ].copy()

        if rules_1to1.empty:
            return {
                'success': False,
                'message': 'No 1-to-1 product association rules found.',
                'delivered_orders_count': delivered_orders_count,
                'products_count': products_count,
                'frequent_itemsets_count': frequent_itemsets_count,
                'rules_count': 0,
                'rules': []
            }

        rules_1to1["product"] = rules_1to1["antecedents"].apply(lambda x: next(iter(x)))
        rules_1to1["frequently_bought_with"] = rules_1to1["consequents"].apply(lambda x: next(iter(x)))

        # Format and round support (5 decimals), confidence (4 decimals), lift (6 decimals)
        rules_1to1["support"] = rules_1to1["support"].apply(lambda v: round(float(v), 5))
        rules_1to1["confidence"] = rules_1to1["confidence"].apply(lambda v: round(float(v), 4))
        rules_1to1["lift"] = rules_1to1["lift"].apply(lambda v: round(float(v), 6))

        # Sort rules by lift descending, confidence descending
        rules_1to1 = rules_1to1.sort_values(by=["lift", "confidence"], ascending=[False, False])

        # Remove any duplicate directional pairs keeping the highest lift
        rules_1to1 = rules_1to1.drop_duplicates(subset=["product", "frequently_bought_with"])

        rule_records = []
        for _, row in rules_1to1.iterrows():
            rule_records.append({
                'product': str(row['product']),
                'frequently_bought_with': str(row['frequently_bought_with']),
                'support': Decimal(str(row['support'])),
                'confidence': Decimal(str(row['confidence'])),
                'lift': Decimal(str(row['lift']))
            })

        return {
            'success': True,
            'message': 'Association rules successfully generated.',
            'delivered_orders_count': delivered_orders_count,
            'products_count': products_count,
            'frequent_itemsets_count': frequent_itemsets_count,
            'rules_count': len(rule_records),
            'rules': rule_records
        }

    @classmethod
    def update_recommendations(
        cls,
        min_support=DEFAULT_MIN_SUPPORT,
        min_confidence=DEFAULT_MIN_CONFIDENCE,
        dry_run=False
    ):
        """
        Recalculates recommendations from complete delivered order history
        and updates the product_recommendations table atomically.

        Prevents duplicate rules by replacing existing rules with the newly
        computed dataset inside a database transaction.
        """
        results = cls.generate_recommendations(
            min_support=min_support,
            min_confidence=min_confidence
        )

        if not results['success']:
            return results

        if dry_run:
            results['message'] = (
                f"[DRY RUN] Discovered {results['rules_count']} recommendation rules. "
                "Database was NOT modified."
            )
            return results

        new_rules = results['rules']

        # Atomic replacement: safely clear and re-populate product_recommendations
        try:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    # Truncate / delete existing recommendation rules
                    cursor.execute("DELETE FROM product_recommendations;")

                    # Insert newly mined association rules using batch execute_values
                    from psycopg2.extras import execute_values
                    insert_query = """
                    INSERT INTO product_recommendations
                    (product, frequently_bought_with, support, confidence, lift, created_at)
                    VALUES %s
                    """
                    records_to_insert = [
                        (
                            r['product'],
                            r['frequently_bought_with'],
                            float(r['support']),
                            float(r['confidence']),
                            float(r['lift'])
                        )
                        for r in new_rules
                    ]
                    try:
                        from psycopg2.extras import execute_values
                        execute_values(
                            cursor,
                            insert_query,
                            records_to_insert,
                            template="(%s, %s, %s, %s, %s, NOW())"
                        )
                    except (AttributeError, TypeError):
                        cursor.executemany(
                            "INSERT INTO product_recommendations (product, frequently_bought_with, support, confidence, lift, created_at) VALUES (%s, %s, %s, %s, %s, NOW())",
                            records_to_insert
                        )

            results['message'] = (
                f"Successfully updated recommendation dataset with {len(new_rules)} rules."
            )
            return results

        except Exception as e:
            logger.exception("Failed to update product_recommendations table in database.")
            return {
                'success': False,
                'message': f"Database error during recommendation update: {str(e)}",
                'delivered_orders_count': results.get('delivered_orders_count', 0),
                'products_count': results.get('products_count', 0),
                'frequent_itemsets_count': results.get('frequent_itemsets_count', 0),
                'rules_count': 0,
                'rules': []
            }

    @classmethod
    def get_recommendations_for_product(cls, product_id):
        """
        Resolves a product by product_id and returns all recommended products
        along with association metrics (support, confidence, lift).

        Returns:
            dict: {
                'product_id': ...,
                'product_name': ...,
                'total_recommendations': ...,
                'recommendations': [ ... ]
            }
            or None if the product does not exist.
        """
        product = Product.objects.filter(product_id=product_id).first()
        if not product:
            return None

        # Fetch recommendation rules where product is the antecedent
        rules = ProductRecommendation.objects.filter(
            product=product.product_name
        ).order_by('-lift', '-confidence')

        recommendations_list = []
        for rule in rules:
            target_name = rule.frequently_bought_with
            # Find matching active products in catalog
            matching_products = Product.objects.filter(
                product_name=target_name,
                hidden=False,
                is_active=True
            )

            # Build list of matching product representations
            matched_items = []
            for p in matching_products:
                matched_items.append({
                    'product_id': p.product_id,
                    'product_name': p.product_name,
                    'sku': getattr(p, 'sku', None),
                    'selling_price': int(p.selling_price) if p.selling_price else 0,
                    'base_price': int(p.base_price) if p.base_price else 0,
                    'category_id': getattr(p, 'sub_category', None) or getattr(p, 'main_category', None),
                    'category_name': getattr(p, 'main_category', None),
                    'gender': getattr(p, 'main_category', None),
                    'color': None,
                    'size': None,
                    'material': None,
                    'is_active': (p.available_quantity or 0) > 0
                })

            primary_product = matched_items[0] if matched_items else None

            recommendations_list.append({
                'id': rule.id,
                'product': rule.product,
                'frequently_bought_with': rule.frequently_bought_with,
                'support': float(rule.support) if rule.support is not None else None,
                'confidence': float(rule.confidence) if rule.confidence is not None else None,
                'lift': float(rule.lift) if rule.lift is not None else None,
                'created_at': rule.created_at,
                'recommended_product': primary_product,
                'matching_products': matched_items
            })

        return {
            'product_id': product.product_id,
            'product_name': product.product_name,
            'category_id': product.category_id if hasattr(product, 'category_id') else None,
            'total_recommendations': len(recommendations_list),
            'recommendations': recommendations_list
        }


def get_effective_product_price(p):
    """
    Returns the real selling price for a product.
    Prioritizes valid discount_price (>0); falls back to parsed actual_price (base_price).
    Returns None if neither price is valid (>0).
    """
    if not p:
        return None
    try:
        if p.discount_price is not None and float(p.discount_price) > 0:
            return float(p.discount_price)
    except (ValueError, TypeError):
        pass

    try:
        base = p.base_price
        if base is not None and float(base) > 0:
            return float(base)
    except (ValueError, TypeError):
        pass

    return None


def serialize_catalog_product(p):
    """Unified serialization for frontend ProductCard & Outfit components."""
    if not p:
        return None
    from_wardrobe = bool(getattr(p, 'from_wardrobe', False))
    eff_price = 0.0 if from_wardrobe else (get_effective_product_price(p) or 0.0)
    raw_img = getattr(p, 'image_url', None) or getattr(p, 'thumb_url', None) or getattr(p, 'image', None)
    clean_image = sanitize_product_image_url(raw_img) if not from_wardrobe else raw_img

    dom_cols = getattr(p, 'dominant_colours', [])
    if isinstance(dom_cols, str):
        try:
            import json
            dom_cols = json.loads(dom_cols)
        except Exception:
            dom_cols = [c.strip() for c in dom_cols.replace('[', '').replace(']', '').replace('"', '').split(',') if c.strip()]
    elif not isinstance(dom_cols, list):
        dom_cols = []

    prod_id = getattr(p, 'product_id', str(getattr(p, 'id', '')))
    prod_name = getattr(p, 'product_name', getattr(p, 'item_name', getattr(p, 'name', 'Item')))

    return {
        'product_id': prod_id,
        'id': prod_id,
        'product_name': prod_name,
        'name': prod_name,
        'selling_price': 0 if from_wardrobe else int(round(eff_price)),
        'discount_price': 0.0 if from_wardrobe else (float(getattr(p, 'discount_price', 0)) if getattr(p, 'discount_price', None) and getattr(p, 'discount_price', 0) > 0 else eff_price),
        'base_price': 0 if from_wardrobe else (int(round(float(getattr(p, 'base_price', 0)))) if getattr(p, 'base_price', None) else int(round(eff_price))),
        'actual_price': 0.0 if from_wardrobe else (float(getattr(p, 'base_price', 0)) if getattr(p, 'base_price', None) else eff_price),
        'image': clean_image or '',
        'primary_image': clean_image or '',
        'images': [clean_image] if clean_image else [],
        'main_category': getattr(p, 'main_category', 'Wardrobe'),
        'sub_category': getattr(p, 'sub_category', getattr(p, 'subtype', 'Wardrobe Item')),
        'is_active': True if from_wardrobe else (getattr(p, 'available_quantity', 0) or 0) > 0,
        'is_image_valid': getattr(p, 'is_image_valid', True),
        'total_stock': 1 if from_wardrobe else int(getattr(p, 'available_quantity', 0) or 0),
        'slot_type': getattr(p, 'slot_type', None),
        'subtype': getattr(p, 'subtype', 'other'),
        'formality': getattr(p, 'formality', 3),
        'pattern': getattr(p, 'pattern', 'solid'),
        'dominant_colours': dom_cols,
        'style_family': getattr(p, 'style_family', 'western'),
        'season': getattr(p, 'season', 'all'),
        'footwear_type': getattr(p, 'footwear_type', None),
        'accessory_type': getattr(p, 'accessory_type', None),
        'includes_blouse': bool(getattr(p, 'includes_blouse', False)),
        'includes_dupatta': bool(getattr(p, 'includes_dupatta', False)),
        'metal_tone': getattr(p, 'metal_tone', 'unknown'),
        'confidence': float(getattr(p, 'confidence', 1.0) or 1.0),
        'hidden': bool(getattr(p, 'hidden', False)),
        'from_wardrobe': from_wardrobe,
    }


class PersonalizedRecommendationService:
    """
    Delivers individualized product recommendations matching:
      1. Demographic / Gender segmentation (Men vs Women).
      2. Historical Order Affinity (Subcategories purchased in delivered orders).
      3. Apriori Basket Mining (Products frequently bought with customer's ordered items).
      4. Cold-Start Fallback (Trending & top-rated items for new accounts with 0 orders).
    """

    @classmethod
    def get_recommendations_for_user(cls, user=None, gender_param=None):
        customer = None
        gender = 'men'  # default fallback

        if user and user.is_authenticated:
            try:
                customer = CustomerResolver.get_customer_for_user(user)
            except Exception:
                customer = None

        if customer:
            cg = (customer.gender or '').strip().lower()
            if 'female' in cg or 'women' in cg:
                gender = 'women'
            elif 'male' in cg or 'men' in cg:
                gender = 'men'
            elif gender_param:
                gender = 'women' if 'women' in gender_param.lower() else 'men'
        elif gender_param:
            gender = 'women' if 'women' in gender_param.lower() else 'men'

        gender_label = "Women's" if gender == 'women' else "Men's"

        # 1. Fetch past ordered products
        past_orders = []
        past_product_names = []
        if customer:
            orders_qs = Order.objects.filter(
                customer_id=customer.customer_id
            ).select_related('product')[:15]
            for o in orders_qs:
                if o.product and o.product.product_name:
                    past_orders.append(o.product)
                    past_product_names.append(o.product.product_name)

        because_you_bought = []
        if past_product_names:
            # Query Apriori association rules where past ordered product is antecedent
            rules = ProductRecommendation.objects.filter(
                product__in=past_product_names
            ).order_by('-lift', '-confidence')[:12]

            seen_ids = set()
            for r in rules:
                target_products = Product.objects.filter(
                    product_name=r.frequently_bought_with,
                    main_category__icontains=gender
                )[:2]
                for p in target_products:
                    if p.product_id not in seen_ids:
                        seen_ids.add(p.product_id)
                        because_you_bought.append({
                            'source_product': r.product,
                            'lift': float(r.lift) if r.lift else 1.0,
                            'product': serialize_catalog_product(p)
                        })

        # 2. Trending picks for gender
        trending_picks = Product.objects.filter(
            main_category__icontains=gender,
            discount_price__isnull=False
        ).order_by('-discount_price')[:12]

        trending_serialized = [serialize_catalog_product(p) for p in trending_picks]

        # 3. Category staples for gender
        staples = Product.objects.filter(
            main_category__icontains=gender
        ).order_by('-discount_price')[12:20]

        staples_serialized = [serialize_catalog_product(p) for p in staples]

        return {
            'success': True,
            'customer_name': customer.customer_name if customer else None,
            'gender': gender,
            'gender_label': gender_label,
            'has_order_history': len(past_orders) > 0,
            'past_order_count': len(past_orders),
            'because_you_bought': because_you_bought[:8],
            'trending_for_you': trending_serialized,
            'curated_staples': staples_serialized,
        }


class SmartBudgetOutfitService:
    """
    Intelligent Budget Outfit Engine that coordinates styling harmony and strictly enforces Knapsack constraints:
      - Occasion Compatibility (Casual / Formal / Party / Festive / College)
      - Style Concordance (Minimal / Chic / Streetwear / Traditional / Elegant)
      - Color Theory Matrix (Color palette matching, Light/Dark contrast, and user preferred color)
      - Fashion Category Directions (Western, Ethnic, Indo-Western, Dresses, or All)
      - Dynamic Price Sampling & Knapsack Optimization (Top + Bottom + Shoes <= Selected Budget)
      - Real Catalog Verification (Active inventory, non-zero selling price, image integrity)
    """

    NEUTRAL_COLORS = {'black', 'white', 'grey', 'gray', 'navy', 'beige', 'khaki', 'cream', 'charcoal', 'denim'}
    LIGHT_COLORS = {'white', 'cream', 'beige', 'khaki', 'yellow', 'pink', 'light blue', 'silver'}
    DARK_COLORS = {'black', 'navy', 'charcoal', 'maroon', 'olive', 'dark brown', 'dark blue', 'burgundy'}

    COLOR_SYNONYMS = {
        'black': ['black', 'noir', 'charcoal', 'jet black'],
        'white': ['white', 'ivory', 'off-white', 'snow'],
        'beige': ['beige', 'cream', 'khaki', 'tan', 'nude', 'camel'],
        'pink': ['pink', 'rose', 'blush', 'magenta', 'fuchsia', 'salmon'],
        'maroon': ['maroon', 'burgundy', 'wine', 'crimson', 'red'],
        'navy': ['navy', 'blue', 'indigo', 'azure', 'sky blue', 'cobalt'],
        'green': ['green', 'olive', 'emerald', 'mint', 'sage', 'teal'],
        'yellow': ['yellow', 'mustard', 'ochre', 'gold'],
        'purple': ['purple', 'violet', 'lavender', 'plum', 'lilac'],
        'brown': ['brown', 'chocolate', 'coffee', 'mocha'],
    }

    OCCASION_MAP = {
        'casual': ['casual', 'cotton', 'regular', 'tee', 't-shirt', 'jeans', 'relaxed', 'printed', 'sneakers', 'flat', 'denim'],
        'formal': ['formal', 'office', 'work', 'blazer', 'trouser', 'trousers', 'shirt', 'classic', 'crepe', 'solid', 'suit'],
        'party': ['party', 'cocktail', 'sequin', 'velvet', 'heels', 'metallic', 'shimmer', 'evening', 'satin', 'flared', 'glam'],
        'festive': ['festive', 'embroidery', 'kurta', 'kurti', 'saree', 'silk', 'zari', 'traditional', 'anarkali', 'ethnic', 'chanderi'],
        'college': ['denim', 'graphic', 'crop', 'sneakers', 'hoodie', 'joggers', 't-shirt', 'street', 'college'],
    }

    STYLE_MAP = {
        'minimal': ['solid', 'plain', 'basic', 'minimal', 'classic', 'clean', 'monochrome'],
        'chic': ['chic', 'stylish', 'trendy', 'crop', 'high waist', 'flared', 'blazer', 'crepe'],
        'streetwear': ['oversized', 'graphic', 'hoodie', 'cargo', 'jogger', 'denim', 'sneakers', 'street'],
        'traditional': ['ethnic', 'printed', 'bandhani', 'cotton', 'silk', 'kurta', 'kurti', 'saree', 'embroidered'],
        'elegant': ['elegant', 'dress', 'gown', 'satin', 'lace', 'heels', 'georgette', 'maxi'],
    }

    EXCLUDE_KEYWORDS = [
        'bra', 'panty', 'panties', 'brief', 'briefs', 'shapewear', 'petticoat',
        'boyshorts', 'camisole', 'innerwear', 'nightwear', 'nightdress', 'nighty',
        'pyjama set', 'pajama set', 'boxer', 'underwear'
    ]

    STANDALONE_KEYWORDS = [
        'jumpsuit', 'romper', 'dungaree', 'dress', 'gown', 'maxi dress', 'midi dress', 'saree', 'anarkali suit'
    ]

    WESTERN_TOP_KEYWORDS = ['shirt', 'tee', 't-shirt', 'top', 'crop', 'blouse', 'jacket', 'hoodie', 'sweatshirt', 'shrug', 'blazer', 'polo']
    WESTERN_BOT_KEYWORDS = ['jeans', 'jean', 'trouser', 'trousers', 'pant', 'pants', 'chino', 'chinos', 'shorts', 'skirt', 'jeggings']
    ETHNIC_TOP_KEYWORDS = ['kurta', 'kurti', 'anarkali', 'tunic', 'ethnic top']
    ETHNIC_BOT_KEYWORDS = ['palazzo', 'skirt', 'legging', 'leggings', 'salwar', 'churidar', 'ethnic pant', 'sharara']

    @classmethod
    def _detect_color(cls, name):
        if not name:
            return 'neutral'
        name_lower = name.lower()
        for base_color, synonyms in cls.COLOR_SYNONYMS.items():
            if any(syn in name_lower for syn in synonyms):
                return base_color
        return 'neutral'

    @classmethod
    def _detect_occasion(cls, name, subcat):
        text = f"{name or ''} {subcat or ''}".lower()
        for occ, kws in cls.OCCASION_MAP.items():
            if any(w in text for w in kws):
                return occ
        return 'casual'

    @classmethod
    def _calculate_harmony_score(
        cls,
        top,
        bottom=None,
        shoe=None,
        accessory=None,
        requested_occasion='casual',
        requested_style='chic',
        preferred_color=None,
        budget_utilization=1.0,
        lift=None
    ):
        """
        Calculates stylistic compatibility score (0 - 100) using:
          1. Color Theory & User Color Affinity
          2. Occasion & Style Concordance
          3. Budget Utilization (prefer outfits utilizing available budget effectively)
          4. Apriori Co-Purchase Verification
        """
        score = 65  # baseline
        explanations = []

        top_color = cls._detect_color(top.product_name)
        bot_color = cls._detect_color(bottom.product_name) if bottom else 'neutral'

        # 1. COLOR PREFERENCE MATCH
        matched_pref_color = False
        if preferred_color:
            pref = preferred_color.lower().strip()
            synonyms = cls.COLOR_SYNONYMS.get(pref, [pref])
            top_name_lower = (top.product_name or '').lower()
            bot_name_lower = (bottom.product_name or '').lower() if bottom else ''
            
            if any(s in top_name_lower for s in synonyms) or any(s in bot_name_lower for s in synonyms):
                matched_pref_color = True
                score += 25
                explanations.append(f"Curated with your requested {pref.title()} palette")

        # 2. COLOR THEORY MATRIX
        top_is_neutral = top_color in cls.NEUTRAL_COLORS
        bot_is_neutral = bot_color in cls.NEUTRAL_COLORS

        if bottom:
            if top_is_neutral and bot_is_neutral:
                score += 15
                explanations.append(f"Harmonious neutral pairing ({top_color.title()} & {bot_color.title()})")
            elif top_is_neutral or bot_is_neutral:
                score += 12
                explanations.append(f"Anchored with clean {bot_color if bot_is_neutral else top_color} base")
            else:
                if (top_color in {'maroon', 'red'} and bot_color in {'green', 'olive'}) or \
                   (top_color in {'yellow'} and bot_color in {'purple', 'pink'}):
                    score -= 25
                    explanations.append("High complementary tension")
                else:
                    score += 5

            # Light / Dark Contrast rule
            top_light = top_color in cls.LIGHT_COLORS
            bot_dark = bot_color in cls.DARK_COLORS
            top_dark = top_color in cls.DARK_COLORS
            bot_light = bot_color in cls.LIGHT_COLORS

            if (top_light and bot_dark) or (top_dark and bot_light):
                score += 12
                explanations.append("Balanced light-and-dark tonal contrast")

        # 3. OCCASION & STYLE CONCORDANCE
        occ_kws = cls.OCCASION_MAP.get(requested_occasion, [])
        top_text = (top.product_name or '').lower()
        bot_text = (bottom.product_name or '').lower() if bottom else ''
        all_text = f"{top_text} {bot_text}"

        if any(kw in all_text for kw in occ_kws):
            score += 15
            explanations.append(f"Ideal fit for {requested_occasion.title()} setting")

        style_kws = cls.STYLE_MAP.get(requested_style, [])
        if any(kw in all_text for kw in style_kws):
            score += 12
            explanations.append(f"{requested_style.title()} aesthetic profile")

        # 4. BUDGET UTILIZATION BOOST (Prefer outfits that use 70%-99% of budget)
        if 0.70 <= budget_utilization <= 0.99:
            score += 15
        elif 0.50 <= budget_utilization < 0.70:
            score += 5

        # 5. APRIORI BASKET CO-PURCHASE SIGNAL
        if lift:
            boost = min(int(float(lift) * 10), 20)
            score += boost
            explanations.append(f"Frequently bought together (Apriori Lift: {float(lift):.1f}x)")

        final_score = max(30, min(99, score))
        verdict = " · ".join(explanations[:2]) if explanations else "Contemporary coordinated pairing"

        return final_score, verdict, top_color, bot_color

    @classmethod
    def generate_budget_outfits(
        cls,
        budget=2000,
        gender='women',
        occasion='casual',
        style='chic',
        preferred_color=None,
        fashion_direction='all',
        sort_by='best',
        limit=100,
        **kwargs
    ):
        """
        Delegates to Rebuilt SmartBudgetOutfitService enforcing:
          - Saree and Lehenga structures
          - Flexible tiers (FULL, CORE, BASIC)
          - Compatibility gate (validate_outfit)
          - Honest scoring & score_breakdown
          - Strict budget cap (<= budget)
        """
        from .smart_budget_service import SmartBudgetOutfitService as RebuiltService
        return RebuiltService.generate_budget_outfits(
            budget=budget,
            gender=gender,
            occasion=occasion,
            style=style,
            preferred_color=preferred_color,
            fashion_direction=fashion_direction,
            sort_by=sort_by,
            limit=limit,
            **kwargs
        )

        is_ethnic = direction_clean == 'ethnic'
        is_indo_western = direction_clean == 'indo-western'
        is_dresses = direction_clean == 'dresses'
        is_western = direction_clean == 'western'

        can_include_shoes = budget_float >= 750

        # Compute price windows based on budget
        if is_dresses:
            top_min = max(40.0, budget_float * 0.45)
            top_max = budget_float * 0.85
            bot_min, bot_max = 0, 0
            shoe_min = max(40.0, budget_float * 0.15)
            shoe_max = budget_float * 0.40
        elif can_include_shoes:
            top_min = max(40.0, budget_float * 0.20)
            top_max = budget_float * 0.50
            bot_min = max(40.0, budget_float * 0.25)
            bot_max = budget_float * 0.55
            shoe_min = max(40.0, budget_float * 0.15)
            shoe_max = budget_float * 0.38
        else:
            top_min = max(40.0, budget_float * 0.30)
            top_max = budget_float * 0.65
            bot_min = max(40.0, budget_float * 0.30)
            bot_max = budget_float * 0.65
            shoe_min, shoe_max = 0, 0

        def build_kw_query(kws):
            q = Q()
            for kw in kws:
                q |= Q(product_name__icontains=kw)
            return q

        # Helper to fetch items across price spectrum (both higher-tier and lower-tier)
        def fetch_tiered_candidates(kw_list, min_p, max_p, exclude_standalones=False, limit_each=20):
            kw_q = build_kw_query(kw_list) if kw_list else Q()
            mid_p = (min_p + max_p) / 2.0

            exclude_q = Q()
            for ex in cls.EXCLUDE_KEYWORDS:
                exclude_q |= Q(product_name__icontains=ex)

            if exclude_standalones:
                for st in cls.STANDALONE_KEYWORDS:
                    exclude_q |= Q(product_name__icontains=st)

            valid_image_q = Q(is_image_valid=True) & ~Q(image__isnull=True) & ~Q(image='')

            high_items = list(Product.objects.filter(
                kw_q,
                valid_image_q,
                main_category__startswith=gender_prefix,
                discount_price__gte=mid_p,
                discount_price__lte=max_p,
                available_quantity__gt=0
            ).exclude(exclude_q).order_by('-discount_price')[:limit_each])

            low_items = list(Product.objects.filter(
                kw_q,
                valid_image_q,
                main_category__startswith=gender_prefix,
                discount_price__gte=min_p,
                discount_price__lt=mid_p,
                available_quantity__gt=0
            ).exclude(exclude_q).order_by('discount_price')[:limit_each])

            combined = high_items + low_items
            if not combined:
                combined = list(Product.objects.filter(
                    valid_image_q,
                    main_category__startswith=gender_prefix,
                    discount_price__gte=min_p * 0.7,
                    discount_price__lte=max_p * 1.1,
                    available_quantity__gt=0
                ).exclude(exclude_q).order_by('discount_price')[:limit_each * 2])

            return combined

        # Tops and Bottoms candidate sets (strictly separate from standalones!)
        if is_dresses:
            tops = []
            bottoms = []
            standalone_candidates = fetch_tiered_candidates(
                cls.STANDALONE_KEYWORDS, top_min, top_max, exclude_standalones=False, limit_each=20
            )
        else:
            if is_ethnic:
                t_kws = cls.ETHNIC_TOP_KEYWORDS
                b_kws = cls.ETHNIC_BOT_KEYWORDS
            elif is_indo_western:
                t_kws = cls.ETHNIC_TOP_KEYWORDS
                b_kws = ['jean', 'jeans', 'denim', 'trouser', 'trousers', 'pant', 'pants']
            elif is_western:
                t_kws = cls.WESTERN_TOP_KEYWORDS
                b_kws = cls.WESTERN_BOT_KEYWORDS
            else:
                # 'all' / 'surprise me'
                t_kws = cls.WESTERN_TOP_KEYWORDS + cls.ETHNIC_TOP_KEYWORDS
                b_kws = cls.WESTERN_BOT_KEYWORDS + cls.ETHNIC_BOT_KEYWORDS

            tops = fetch_tiered_candidates(t_kws, top_min, top_max, exclude_standalones=True, limit_each=20)
            bottoms = fetch_tiered_candidates(b_kws, bot_min, bot_max, exclude_standalones=True, limit_each=20)
            
            # For 'all' or 'western', also fetch standalone jumpsuits/dresses as candidate outfits
            if direction_clean in ['all', 'western'] and gender_clean == 'women':
                standalone_candidates = fetch_tiered_candidates(
                    cls.STANDALONE_KEYWORDS, max(40.0, budget_float * 0.40), budget_float * 0.85, exclude_standalones=False, limit_each=15
                )
            else:
                standalone_candidates = []

        valid_img_filter = Q(is_image_valid=True) & ~Q(image__isnull=True) & ~Q(image='')

        # Fetch shoes
        shoes = []
        if can_include_shoes or is_dresses:
            shoe_cat = "women's shoes" if gender_clean == 'women' else "men's shoes"
            shoe_mid = (shoe_min + shoe_max) / 2.0
            s_high = list(Product.objects.filter(
                valid_img_filter,
                main_category=shoe_cat,
                discount_price__gte=shoe_mid,
                discount_price__lte=shoe_max,
                available_quantity__gt=0
            ).order_by('-discount_price')[:12])

            s_low = list(Product.objects.filter(
                valid_img_filter,
                main_category=shoe_cat,
                discount_price__gte=shoe_min,
                discount_price__lt=shoe_mid,
                available_quantity__gt=0
            ).order_by('discount_price')[:12])
            shoes = s_high + s_low

        # Fetch candidate Bags / Accessories
        accessories = []
        if budget_float >= 900:
            acc_max = budget_float * 0.28
            acc_items = list(Product.objects.filter(
                valid_img_filter,
                Q(product_name__icontains='handbag') | Q(product_name__icontains='sling bag') | Q(main_category__icontains='accessories'),
                discount_price__gte=70,
                discount_price__lte=acc_max,
                available_quantity__gt=0
            ).order_by('discount_price')[:15])
            accessories = acc_items

        if not tops and not standalone_candidates:
            return {
                'success': False,
                'message': f"No matching products found for {gender_clean} under budget ₹{budget_float:.0f}. Try increasing your budget.",
                'outfits': []
            }

        # Batch load co-purchase rules for top and bottom candidates
        top_names = [t.product_name for t in tops[:20] if t.product_name]
        bot_names = [b.product_name for b in bottoms[:20] if b.product_name]
        rules_map = {}
        if top_names and bot_names:
            rules_qs = ProductRecommendation.objects.filter(
                product__in=top_names,
                frequently_bought_with__in=bot_names
            ).values('product', 'frequently_bought_with', 'lift')
            for r in rules_qs:
                rules_map[(r['product'], r['frequently_bought_with'])] = r['lift']

        candidate_outfits = []

        # 1. GENERATE STANDALONE LOOKS (Jumpsuits, Dresses, Gowns, Sarees)
        # Rule: NEVER paired with bottomwear!
        for d in standalone_candidates:
            dp = get_effective_product_price(d)
            if not dp or dp > budget_float:
                continue

            name_lower = (d.product_name or '').lower()
            is_jumpsuit = 'jumpsuit' in name_lower or 'romper' in name_lower
            garment_label = "Jumpsuit" if is_jumpsuit else ("Saree" if 'saree' in name_lower else "Dress")

            # Try Standalone + Footwear (+ Accessory/Bag)
            if shoes:
                for s in shoes:
                    sp = get_effective_product_price(s)
                    if not sp or (dp + sp) > budget_float:
                        continue

                    # Try adding accessory/bag if budget permits
                    acc_pick = None
                    tot = dp + sp
                    if accessories:
                        for acc in accessories:
                            ap = get_effective_product_price(acc)
                            if ap and (tot + ap) <= budget_float:
                                acc_pick = acc
                                tot += ap
                                break

                    util = tot / budget_float
                    score, verdict, top_col, _ = cls._calculate_harmony_score(
                        top=d,
                        bottom=None,
                        shoe=s,
                        accessory=acc_pick,
                        requested_occasion=occasion,
                        requested_style=style,
                        preferred_color=pref_color_clean,
                        budget_utilization=util
                    )

                    candidate_outfits.append({
                        'styling_score': score,
                        'total_price': int(round(tot)),
                        'savings': max(0, int(round(budget_float - tot))),
                        'coins_remaining': max(0, int(round(budget_float - tot))),
                        'budget': int(budget_float),
                        'style_verdict': verdict,
                        'top_color': top_col,
                        'bot_color': 'neutral',
                        'category_direction': garment_label if not is_dresses else 'Dresses & Jumpsuits',
                        'is_dress': True,
                        'garment_type': garment_label,
                        'topwear': serialize_catalog_product(d),
                        'bottomwear': None,  # NEVER pair jumpsuit with bottoms!
                        'footwear': serialize_catalog_product(s),
                        'accessory': serialize_catalog_product(acc_pick) if acc_pick else None,
                    })
            else:
                util = dp / budget_float
                score, verdict, top_col, _ = cls._calculate_harmony_score(
                    top=d,
                    bottom=None,
                    shoe=None,
                    accessory=None,
                    requested_occasion=occasion,
                    requested_style=style,
                    preferred_color=pref_color_clean,
                    budget_utilization=util
                )
                candidate_outfits.append({
                    'styling_score': score,
                    'total_price': int(round(dp)),
                    'savings': max(0, int(round(budget_float - dp))),
                    'coins_remaining': max(0, int(round(budget_float - dp))),
                    'budget': int(budget_float),
                    'style_verdict': verdict,
                    'top_color': top_col,
                    'bot_color': 'neutral',
                    'category_direction': garment_label if not is_dresses else 'Dresses & Jumpsuits',
                    'is_dress': True,
                    'garment_type': garment_label,
                    'topwear': serialize_catalog_product(d),
                    'bottomwear': None,
                    'footwear': None,
                    'accessory': None,
                })

        # 2. GENERATE TWO-PIECE LOOKS (Top + Bottom + Shoes/Accessories)
        if tops and bottoms:
            for top_idx, top in enumerate(tops):
                tp = get_effective_product_price(top)
                if not tp or tp > budget_float:
                    continue

                for bot_idx, bottom in enumerate(bottoms):
                    bp = get_effective_product_price(bottom)
                    if not bp or (tp + bp) > budget_float:
                        continue

                    base_price = tp + bp
                    lift = rules_map.get((top.product_name, bottom.product_name))

                    direction_label = (
                        "Ethnic" if is_ethnic else
                        "Indo-Western" if is_indo_western else
                        "Western"
                    )

                    if can_include_shoes and shoes:
                        for s_idx, shoe in enumerate(shoes):
                            sp = get_effective_product_price(shoe)
                            if not sp or (base_price + sp) > budget_float:
                                continue

                            tot = base_price + sp
                            acc_pick = None
                            if accessories:
                                for acc in accessories:
                                    ap = get_effective_product_price(acc)
                                    if ap and (tot + ap) <= budget_float:
                                        acc_pick = acc
                                        tot += ap
                                        break

                            util = tot / budget_float
                            score, verdict, top_col, bot_col = cls._calculate_harmony_score(
                                top=top,
                                bottom=bottom,
                                shoe=shoe,
                                accessory=acc_pick,
                                requested_occasion=occasion,
                                requested_style=style,
                                preferred_color=pref_color_clean,
                                budget_utilization=util,
                                lift=lift
                            )

                            candidate_outfits.append({
                                'styling_score': score,
                                'total_price': int(round(tot)),
                                'savings': max(0, int(round(budget_float - tot))),
                                'coins_remaining': max(0, int(round(budget_float - tot))),
                                'budget': int(budget_float),
                                'style_verdict': verdict,
                                'top_color': top_col,
                                'bot_color': bot_col,
                                'category_direction': direction_label,
                                'is_dress': False,
                                'garment_type': 'Top',
                                'topwear': serialize_catalog_product(top),
                                'bottomwear': serialize_catalog_product(bottom),
                                'footwear': serialize_catalog_product(shoe),
                                'accessory': serialize_catalog_product(acc_pick) if acc_pick else None,
                            })
                    else:
                        util = base_price / budget_float
                        score, verdict, top_col, bot_col = cls._calculate_harmony_score(
                            top=top,
                            bottom=bottom,
                            shoe=None,
                            accessory=None,
                            requested_occasion=occasion,
                            requested_style=style,
                            preferred_color=pref_color_clean,
                            budget_utilization=util,
                            lift=lift
                        )

                        candidate_outfits.append({
                            'styling_score': score,
                            'total_price': int(round(base_price)),
                            'savings': max(0, int(round(budget_float - base_price))),
                            'coins_remaining': max(0, int(round(budget_float - base_price))),
                            'budget': int(budget_float),
                            'style_verdict': verdict,
                            'top_color': top_col,
                            'bot_color': bot_col,
                            'category_direction': direction_label,
                            'is_dress': False,
                            'garment_type': 'Top',
                            'topwear': serialize_catalog_product(top),
                            'bottomwear': serialize_catalog_product(bottom),
                            'footwear': None,
                            'accessory': None,
                        })

        if not candidate_outfits:
            return {
                'success': False,
                'message': f"No matching outfit combinations found under ₹{budget_float:.0f}. Try increasing your budget or selecting 'Surprise Me'.",
                'outfits': []
            }

        # Deduplicate candidate outfits by product IDs
        unique_candidates = []
        seen_keys = set()
        for o in candidate_outfits:
            t_id = o['topwear']['product_id'] if o['topwear'] else ''
            b_id = o['bottomwear']['product_id'] if o['bottomwear'] else ''
            s_id = o['footwear']['product_id'] if o['footwear'] else ''
            a_id = o['accessory']['product_id'] if o.get('accessory') else ''
            key = (t_id, b_id, s_id, a_id)
            if key not in seen_keys:
                seen_keys.add(key)
                unique_candidates.append(o)

        # Sort candidate outfits by styling_score descending, then total_price descending
        unique_candidates.sort(key=lambda o: (o['styling_score'], o['total_price']), reverse=True)

        # SELECT UP TO 6 HIGH-VARIETY, NON-OVERLAPPING OUTFITS
        TIER_METADATA = [
            ('Most Popular', 'Most Popular Look', 'Highest aesthetic harmony score & runway-ready coordination.'),
            ('Best Match', 'Best Match Look', 'Maximum budget efficiency with effortless daily elegance.'),
            ('Atelier Pick', 'Atelier Curated Look', 'Contrasting color palette for versatile wardrobe rotation.'),
            ('Weekend Chic', 'Weekend Chic Look', 'Relaxed, contemporary silhouette ideal for brunches and casual meetups.'),
            ('Signature Luxe', 'Signature Luxe Look', 'Elevated statement aesthetic designed for evening occasions.'),
            ('Modern Minimal', 'Modern Minimal Look', 'Clean tonal balance with timeless wardrobe staples.')
        ]

        curated_outfits = []
        used_top_ids = set()
        used_bot_ids = set()

        # Pass 1: Select distinct looks where BOTH top and bottom are unique
        for o in unique_candidates:
            if len(curated_outfits) >= 6:
                break
            t_id = o['topwear']['product_id'] if o['topwear'] else None
            b_id = o['bottomwear']['product_id'] if o['bottomwear'] else None

            if t_id and t_id in used_top_ids:
                continue
            if b_id and b_id in used_bot_ids:
                continue

            # Assign tier info
            tier_idx = len(curated_outfits)
            badge, tier_name, tier_desc = TIER_METADATA[tier_idx]
            o['badge'] = badge
            o['tier'] = tier_name
            o['tier_desc'] = tier_desc

            curated_outfits.append(o)
            if t_id: used_top_ids.add(t_id)
            if b_id: used_bot_ids.add(b_id)

        # Pass 2: If catalogue was constrained and we have fewer than 6, relax bottom uniqueness
        if len(curated_outfits) < 6:
            for o in unique_candidates:
                if len(curated_outfits) >= 6:
                    break
                if o in curated_outfits:
                    continue
                t_id = o['topwear']['product_id'] if o['topwear'] else None
                if t_id and t_id in used_top_ids:
                    continue

                tier_idx = len(curated_outfits)
                badge, tier_name, tier_desc = TIER_METADATA[tier_idx]
                o['badge'] = badge
                o['tier'] = tier_name
                o['tier_desc'] = tier_desc

                curated_outfits.append(o)
                if t_id: used_top_ids.add(t_id)

        # Pass 3: Fill any remaining slots with best remaining unique candidates
        if len(curated_outfits) < 3:
            for o in unique_candidates:
                if len(curated_outfits) >= 3:
                    break
                if o not in curated_outfits:
                    tier_idx = min(len(curated_outfits), 5)
                    badge, tier_name, tier_desc = TIER_METADATA[tier_idx]
                    o['badge'] = badge
                    o['tier'] = tier_name
                    o['tier_desc'] = tier_desc
                    curated_outfits.append(o)

        # Apply sort_by order to the curated outfits
        if sort_by == 'price_low':
            curated_outfits.sort(key=lambda o: o['total_price'])
        elif sort_by == 'price_high':
            curated_outfits.sort(key=lambda o: o['total_price'], reverse=True)
        elif sort_by == 'score':
            curated_outfits.sort(key=lambda o: o['styling_score'], reverse=True)

        return {
            'success': True,
            'budget': int(budget_float),
            'gender': gender_clean,
            'occasion': occasion,
            'style': style,
            'preferred_color': pref_color_clean,
            'category_direction': direction_clean,
            'total_candidates_analyzed': len(unique_candidates),
            'outfits': curated_outfits
        }

