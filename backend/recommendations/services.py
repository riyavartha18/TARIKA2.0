import logging
from decimal import Decimal
from django.db import connection, transaction
import pandas as pd
from mlxtend.preprocessing import TransactionEncoder
from mlxtend.frequent_patterns import apriori, association_rules

from catalog.models import Product
from .models import ProductRecommendation

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

    DEFAULT_MIN_SUPPORT = 0.002
    DEFAULT_MIN_CONFIDENCE = 0.0

    @classmethod
    def fetch_delivered_order_items(cls):
        """
        Executes a SQL query joining orders, order_items, and products
        for orders with status 'delivered'.
        Returns a pandas DataFrame with columns: order_id, product_id, product_name.
        """
        query = """
        SELECT
            o.order_id,
            oi.product_id,
            p.product_name
        FROM orders o
        JOIN order_items oi
            ON o.order_id = oi.order_id
        JOIN products p
            ON oi.product_id = p.product_id
        WHERE o.order_status = 'delivered'
          AND p.product_name IS NOT NULL
          AND TRIM(p.product_name) != ''
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

                    # Insert newly mined association rules
                    insert_query = """
                    INSERT INTO product_recommendations
                    (product, frequently_bought_with, support, confidence, lift, created_at)
                    VALUES (%s, %s, %s, %s, %s, NOW())
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
                    cursor.executemany(insert_query, records_to_insert)

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
                is_active=True
            ).select_related('category')

            # Build list of matching product representations
            matched_items = []
            for p in matching_products:
                matched_items.append({
                    'product_id': p.product_id,
                    'product_name': p.product_name,
                    'sku': p.sku,
                    'selling_price': p.selling_price,
                    'base_price': p.base_price,
                    'category_id': p.category.category_id if p.category else None,
                    'category_name': p.category.category_name if p.category else None,
                    'gender': p.gender,
                    'color': p.color,
                    'size': p.size,
                    'material': p.material,
                    'is_active': p.is_active
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
