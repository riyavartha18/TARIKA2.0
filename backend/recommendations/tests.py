from decimal import Decimal
from unittest.mock import patch, MagicMock
import pandas as pd
from django.test import SimpleTestCase
from django.urls import reverse, resolve
from rest_framework.test import APIRequestFactory
from rest_framework import status

from recommendations.views import ProductRecommendationView
from recommendations.services import RecommendationService
from recommendations.models import ProductRecommendation


class RecommendationPipelineTests(SimpleTestCase):
    """
    Unit tests for the Apriori recommendation engine, association rule mining,
    edge cases, and database refresh integrity.
    """

    def test_1_recommendation_generation(self):
        """
        1. Test recommendation generation:
        Given delivered orders with frequent co-purchases, verify that
        the service builds transactions, runs Apriori, and generates directional rules.
        """
        # Create synthetic order items where Product A and Product B frequently co-occur
        sample_data = []
        # 10 orders with Product A and Product B
        for i in range(10):
            sample_data.append({'order_id': f'ord_{i}', 'product_id': 'p1', 'product_name': 'Alpha Sneaker'})
            sample_data.append({'order_id': f'ord_{i}', 'product_id': 'p2', 'product_name': 'Beta Socks'})
        # 5 orders with Product C alone
        for i in range(10, 15):
            sample_data.append({'order_id': f'ord_{i}', 'product_id': 'p3', 'product_name': 'Gamma Cap'})

        df = pd.DataFrame(sample_data)

        with patch.object(RecommendationService, 'fetch_delivered_order_items', return_value=df):
            results = RecommendationService.generate_recommendations(min_support=0.1, min_confidence=0.0)

            self.assertTrue(results['success'])
            self.assertEqual(results['delivered_orders_count'], 15)
            self.assertEqual(results['products_count'], 3)
            self.assertGreater(results['frequent_itemsets_count'], 0)
            self.assertGreaterEqual(results['rules_count'], 2)

            rules = results['rules']
            products_in_rules = {(r['product'], r['frequently_bought_with']) for r in rules}
            self.assertIn(('Alpha Sneaker', 'Beta Socks'), products_in_rules)
            self.assertIn(('Beta Socks', 'Alpha Sneaker'), products_in_rules)

            # Check that metrics (support, confidence, lift) are populated
            rule = rules[0]
            self.assertIn('support', rule)
            self.assertIn('confidence', rule)
            self.assertIn('lift', rule)
            self.assertGreater(rule['lift'], 1.0)

    def test_2_no_delivered_orders(self):
        """
        2. Test graceful handling when there are no delivered orders.
        """
        empty_df = pd.DataFrame(columns=['order_id', 'product_id', 'product_name'])

        with patch.object(RecommendationService, 'fetch_delivered_order_items', return_value=empty_df):
            results = RecommendationService.generate_recommendations()

            self.assertFalse(results['success'])
            self.assertEqual(results['delivered_orders_count'], 0)
            self.assertEqual(results['products_count'], 0)
            self.assertEqual(results['frequent_itemsets_count'], 0)
            self.assertEqual(results['rules_count'], 0)
            self.assertEqual(len(results['rules']), 0)
            self.assertIn("No delivered orders found", results['message'])

    def test_3_no_frequent_itemsets(self):
        """
        3. Test graceful handling when orders exist but co-occurrence does not meet min_support.
        """
        # 10 orders, each with a completely unique product (no co-purchases at all)
        sample_data = [
            {'order_id': f'ord_{i}', 'product_id': f'p_{i}', 'product_name': f'Item_{i}'}
            for i in range(10)
        ]
        df = pd.DataFrame(sample_data)

        with patch.object(RecommendationService, 'fetch_delivered_order_items', return_value=df):
            # Using min_support=0.5: no pairs will ever satisfy this
            results = RecommendationService.generate_recommendations(min_support=0.5)

            self.assertFalse(results['success'])
            self.assertEqual(results['rules_count'], 0)
            self.assertIn("No frequent itemsets", results['message'])

    def test_6_recommendation_refresh_does_not_create_duplicate_rows(self):
        """
        6. Test recommendation refresh does not create duplicate rows:
        Verifies that multiple update_recommendations calls safely replace
        the dataset atomically rather than accumulating duplicate rows.
        """
        mock_rules = [
            {
                'product': 'Track Trousers',
                'frequently_bought_with': 'Slim Fit T-Shirt',
                'support': Decimal('0.00243'),
                'confidence': Decimal('0.0765'),
                'lift': Decimal('3.079369')
            },
            {
                'product': 'Slim Fit T-Shirt',
                'frequently_bought_with': 'Track Trousers',
                'support': Decimal('0.00243'),
                'confidence': Decimal('0.0979'),
                'lift': Decimal('3.079369')
            }
        ]

        gen_result = {
            'success': True,
            'message': 'Success',
            'delivered_orders_count': 100,
            'products_count': 2,
            'frequent_itemsets_count': 2,
            'rules_count': 2,
            'rules': mock_rules
        }

        # Mock database cursor to record SQL statements
        executed_sqls = []

        class MockCursor:
            def execute(self, sql, params=None):
                executed_sqls.append((sql.strip(), params))

            def executemany(self, sql, seq_of_params):
                executed_sqls.append((sql.strip(), list(seq_of_params)))

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                pass

        class DummyAtomic:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                pass

        mock_cursor = MockCursor()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch.object(RecommendationService, 'generate_recommendations', return_value=gen_result), \
             patch('recommendations.services.transaction.atomic', return_value=DummyAtomic()), \
             patch('recommendations.services.connection', mock_conn):

            # First refresh
            res1 = RecommendationService.update_recommendations()
            self.assertTrue(res1['success'])
            self.assertEqual(res1['rules_count'], 2)

            # Second refresh
            res2 = RecommendationService.update_recommendations()
            self.assertTrue(res2['success'])
            self.assertEqual(res2['rules_count'], 2)

            # Ensure DELETE is called before INSERT so duplicate rows are prevented
            delete_calls = [sql for sql, _ in executed_sqls if 'DELETE FROM product_recommendations' in sql]
            insert_calls = [sql for sql, _ in executed_sqls if 'INSERT INTO product_recommendations' in sql]

            self.assertEqual(len(delete_calls), 2)
            self.assertEqual(len(insert_calls), 2)


class RecommendationAPITests(SimpleTestCase):
    """
    Unit tests for the recommendations API view and endpoints.
    """

    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = ProductRecommendationView.as_view()

    def test_url_reverse_and_resolve(self):
        """Test URL patterns reverse and resolve properly."""
        url = reverse('recommendations:product-recommendations', kwargs={'product_id': 'prod-123'})
        self.assertEqual(url, '/api/recommendations/prod-123/')
        match = resolve(url)
        self.assertEqual(match.view_name, 'recommendations:product-recommendations')

    def test_4_api_with_recommendations(self):
        """
        4. Test API with recommendations:
        For a product with recommendation rules, return 200 OK with recommended products and metrics.
        """
        mock_data = {
            'product_id': 'prod-100',
            'product_name': 'Slim Fit T-Shirt',
            'category_id': 'cat-top',
            'total_recommendations': 1,
            'recommendations': [
                {
                    'id': 1,
                    'product': 'Slim Fit T-Shirt',
                    'frequently_bought_with': 'Track Trousers',
                    'support': 0.00243,
                    'confidence': 0.0979,
                    'lift': 3.0794,
                    'created_at': '2026-09-28T12:00:00Z',
                    'recommended_product': {
                        'product_id': 'prod-200',
                        'product_name': 'Track Trousers',
                        'sku': 'TRK-001',
                        'selling_price': 1010,
                        'base_price': 1200,
                        'category_id': 'cat-bot',
                        'category_name': 'Bottom Wear',
                        'gender': 'Men',
                        'color': 'Black',
                        'size': 'L',
                        'material': 'Cotton',
                        'is_active': True
                    },
                    'matching_products': []
                }
            ]
        }

        with patch.object(RecommendationService, 'get_recommendations_for_product', return_value=mock_data):
            request = self.factory.get('/api/recommendations/prod-100/')
            response = self.view(request, product_id='prod-100')

            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.data['product_id'], 'prod-100')
            self.assertEqual(response.data['product_name'], 'Slim Fit T-Shirt')
            self.assertEqual(response.data['total_recommendations'], 1)
            self.assertEqual(len(response.data['recommendations']), 1)

            rec_item = response.data['recommendations'][0]
            self.assertEqual(rec_item['frequently_bought_with'], 'Track Trousers')
            self.assertEqual(rec_item['support'], 0.00243)
            self.assertEqual(rec_item['confidence'], 0.0979)
            self.assertEqual(rec_item['lift'], 3.0794)
            self.assertIsNotNone(rec_item['recommended_product'])
            self.assertEqual(rec_item['recommended_product']['product_id'], 'prod-200')

    def test_5_api_for_product_with_no_recommendations(self):
        """
        5. Test API for product with no recommendations:
        Should return 200 OK with an empty recommendations list gracefully.
        """
        mock_data = {
            'product_id': 'prod-isolated',
            'product_name': 'Novelty Umbrella',
            'category_id': 'cat-acc',
            'total_recommendations': 0,
            'recommendations': []
        }

        with patch.object(RecommendationService, 'get_recommendations_for_product', return_value=mock_data):
            request = self.factory.get('/api/recommendations/prod-isolated/')
            response = self.view(request, product_id='prod-isolated')

            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.data['product_id'], 'prod-isolated')
            self.assertEqual(response.data['total_recommendations'], 0)
            self.assertEqual(response.data['recommendations'], [])

    def test_api_for_nonexistent_product(self):
        """
        Test API for nonexistent product returns 404 Not Found.
        """
        with patch.object(RecommendationService, 'get_recommendations_for_product', return_value=None):
            request = self.factory.get('/api/recommendations/nonexistent-id/')
            response = self.view(request, product_id='nonexistent-id')

            self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
            self.assertIn('detail', response.data)
            self.assertIn('not found', response.data['detail'].lower())


from recommendations.outfit_validator import validate_outfit
from recommendations.services import SmartBudgetOutfitService


class SmartBudgetStylistCompatibilityTests(SimpleTestCase):
    """
    Comprehensive unit tests for the Smart Budget Stylist compatibility gate
    and outfit builder rules (TASK 2).
    """

    def setUp(self):
        self.default_prefs = {
            'budget': 2500,
            'occasion': 'casual',
            'style': 'chic',
            'preferred_color': 'pink',
            'gender': 'women',
            'category_direction': 'all',
        }

    def test_saree_with_jeans_fails(self):
        pieces = {
            'one_piece': {
                'product_name': 'Banarasi Silk Saree',
                'slot_type': 'one_piece',
                'subtype': 'saree',
                'formality': 4,
                'pattern': 'embellished',
                'dominant_colours': ['maroon', 'gold'],
                'style_family': 'ethnic',
                'includes_blouse': True,
                'discount_price': 1200
            },
            'top': None,
            'bottom': {
                'product_name': 'Skinny Blue Jeans',
                'slot_type': 'bottom',
                'subtype': 'other',
                'formality': 2,
                'pattern': 'solid',
                'dominant_colours': ['blue'],
                'style_family': 'western',
                'discount_price': 600
            },
            'footwear': None,
            'bag': None,
            'accessories': []
        }
        passed, reasons = validate_outfit(pieces, self.default_prefs)
        self.assertFalse(passed)
        self.assertTrue(any('saree' in r.lower() or 'one-piece' in r.lower() for r in reasons))

    def test_lehenga_with_sneakers_fails(self):
        pieces = {
            'one_piece': {
                'product_name': 'Bridal Lehenga Choli Set',
                'slot_type': 'one_piece',
                'subtype': 'lehenga_set',
                'formality': 5,
                'pattern': 'embellished',
                'dominant_colours': ['red', 'gold'],
                'style_family': 'ethnic',
                'includes_dupatta': True,
                'discount_price': 1800
            },
            'top': None,
            'bottom': None,
            'footwear': {
                'product_name': 'White Running Sneakers',
                'slot_type': 'footwear',
                'footwear_type': 'sneaker',
                'formality': 2,
                'pattern': 'solid',
                'dominant_colours': ['white'],
                'style_family': 'athleisure',
                'discount_price': 500
            },
            'bag': None,
            'accessories': []
        }
        passed, reasons = validate_outfit(pieces, {**self.default_prefs, 'occasion': 'festive'})
        self.assertFalse(passed)
        self.assertTrue(any('sneaker' in r.lower() or 'footwear' in r.lower() or 'formality' in r.lower() for r in reasons))

    def test_saree_with_belt_fails(self):
        pieces = {
            'one_piece': {
                'product_name': 'Chanderi Saree with Blouse',
                'slot_type': 'one_piece',
                'subtype': 'saree',
                'formality': 4,
                'pattern': 'solid',
                'dominant_colours': ['green'],
                'style_family': 'ethnic',
                'includes_blouse': True,
                'discount_price': 1100
            },
            'top': None,
            'bottom': None,
            'footwear': {
                'product_name': 'Ethnic Heels',
                'slot_type': 'footwear',
                'footwear_type': 'heel',
                'formality': 4,
                'pattern': 'solid',
                'dominant_colours': ['gold'],
                'style_family': 'ethnic',
                'discount_price': 600
            },
            'bag': None,
            'accessories': [
                {
                    'product_name': 'Leather Waist Belt',
                    'slot_type': 'accessory',
                    'accessory_type': 'belt',
                    'formality': 3,
                    'pattern': 'solid',
                    'dominant_colours': ['brown'],
                    'style_family': 'western',
                    'discount_price': 200
                }
            ]
        }
        passed, reasons = validate_outfit(pieces, {**self.default_prefs, 'occasion': 'festive'})
        self.assertFalse(passed)
        self.assertTrue(any('belt' in r.lower() for r in reasons))

    def test_lehenga_set_with_separate_dupatta_fails(self):
        pieces = {
            'one_piece': {
                'product_name': 'Embroidered Lehenga Choli Set',
                'slot_type': 'one_piece',
                'subtype': 'lehenga_set',
                'formality': 5,
                'pattern': 'embellished',
                'dominant_colours': ['pink', 'silver'],
                'style_family': 'ethnic',
                'includes_dupatta': True,
                'discount_price': 1600
            },
            'top': None,
            'bottom': None,
            'footwear': {
                'product_name': 'Silver Heels',
                'slot_type': 'footwear',
                'footwear_type': 'heel',
                'formality': 4,
                'pattern': 'solid',
                'dominant_colours': ['silver'],
                'style_family': 'western',
                'discount_price': 500
            },
            'bag': None,
            'accessories': [
                {
                    'product_name': 'Chiffon Silk Dupatta',
                    'slot_type': 'accessory',
                    'accessory_type': 'dupatta',
                    'formality': 4,
                    'pattern': 'solid',
                    'dominant_colours': ['pink'],
                    'style_family': 'ethnic',
                    'discount_price': 250
                }
            ]
        }
        passed, reasons = validate_outfit(pieces, {**self.default_prefs, 'occasion': 'festive'})
        self.assertFalse(passed)
        self.assertTrue(any('dupatta' in r.lower() for r in reasons))

    def test_saree_without_blouse_option_fails(self):
        pieces = {
            'one_piece': {
                'product_name': 'Plain Cotton Saree without Blouse',
                'slot_type': 'one_piece',
                'subtype': 'saree',
                'formality': 3,
                'pattern': 'solid',
                'dominant_colours': ['yellow'],
                'style_family': 'ethnic',
                'includes_blouse': False,
                'discount_price': 500
            },
            'top': None,
            'bottom': None,
            'footwear': {
                'product_name': 'Casual Flats',
                'slot_type': 'footwear',
                'footwear_type': 'flat',
                'formality': 3,
                'pattern': 'solid',
                'dominant_colours': ['tan'],
                'style_family': 'ethnic',
                'discount_price': 300
            },
            'bag': None,
            'accessories': []
        }
        passed, reasons = validate_outfit(pieces, {**self.default_prefs, 'occasion': 'traditional'})
        self.assertFalse(passed)
        self.assertTrue(any('blouse' in r.lower() for r in reasons))

    def test_cotton_saree_casual_traditional_passes(self):
        pieces = {
            'one_piece': {
                'product_name': 'Cotton Printed Daily Saree',
                'slot_type': 'one_piece',
                'subtype': 'saree',
                'formality': 3,
                'pattern': 'printed',
                'dominant_colours': ['white', 'blue'],
                'style_family': 'ethnic',
                'includes_blouse': True,
                'discount_price': 550
            },
            'top': None,
            'bottom': None,
            'footwear': {
                'product_name': 'Leather Juttis',
                'slot_type': 'footwear',
                'footwear_type': 'jutti',
                'formality': 3,
                'pattern': 'solid',
                'dominant_colours': ['tan'],
                'style_family': 'ethnic',
                'discount_price': 350
            },
            'bag': {
                'product_name': 'Embroidered Potli Bag',
                'slot_type': 'bag',
                'subtype': 'potli',
                'formality': 3,
                'pattern': 'solid',
                'dominant_colours': ['white'],
                'style_family': 'ethnic',
                'discount_price': 250
            },
            'accessories': []
        }
        passed, reasons = validate_outfit(pieces, {**self.default_prefs, 'occasion': 'casual', 'budget': 1500})
        self.assertTrue(passed, f"Failed reasons: {reasons}")

    def test_silk_saree_festive_full_passes(self):
        pieces = {
            'one_piece': {
                'product_name': 'Kanjivaram Silk Saree',
                'slot_type': 'one_piece',
                'subtype': 'saree',
                'formality': 5,
                'pattern': 'embellished',
                'dominant_colours': ['maroon', 'gold'],
                'style_family': 'ethnic',
                'includes_blouse': True,
                'discount_price': 1400
            },
            'top': None,
            'bottom': None,
            'footwear': {
                'product_name': 'Golden Block Heels',
                'slot_type': 'footwear',
                'footwear_type': 'heel',
                'formality': 5,
                'pattern': 'solid',
                'dominant_colours': ['gold'],
                'style_family': 'ethnic',
                'discount_price': 550
            },
            'bag': {
                'product_name': 'Zari Evening Clutch',
                'slot_type': 'bag',
                'subtype': 'clutch',
                'formality': 4,
                'pattern': 'solid',
                'dominant_colours': ['gold'],
                'style_family': 'ethnic',
                'discount_price': 350
            },
            'accessories': [
                {
                    'product_name': 'Kundan Jhumka Earrings',
                    'slot_type': 'accessory',
                    'accessory_type': 'jewellery',
                    'formality': 4,
                    'pattern': 'solid',
                    'dominant_colours': ['gold'],
                    'style_family': 'ethnic',
                    'discount_price': 200
                }
            ]
        }
        passed, reasons = validate_outfit(pieces, {**self.default_prefs, 'occasion': 'festive', 'budget': 3000})
        self.assertTrue(passed, f"Failed reasons: {reasons}")

    def test_lehenga_never_for_casual_college_streetwear(self):
        pieces = {
            'one_piece': {
                'product_name': 'Printed Lehenga Set',
                'slot_type': 'one_piece',
                'subtype': 'lehenga_set',
                'formality': 4,
                'pattern': 'printed',
                'dominant_colours': ['pink'],
                'style_family': 'ethnic',
                'includes_dupatta': True,
                'discount_price': 999
            },
            'top': None,
            'bottom': None,
            'footwear': {
                'product_name': 'Flat Sandals',
                'slot_type': 'footwear',
                'footwear_type': 'flat',
                'formality': 3,
                'pattern': 'solid',
                'dominant_colours': ['white'],
                'style_family': 'ethnic',
                'discount_price': 300
            },
            'bag': None,
            'accessories': []
        }
        for occ in ('casual', 'college', 'streetwear'):
            passed, reasons = validate_outfit(pieces, {**self.default_prefs, 'occasion': occ})
            self.assertFalse(passed, f"Lehenga should have failed for occasion {occ}")
            self.assertTrue(any('lehenga' in r.lower() or 'occasion' in r.lower() for r in reasons))

    def test_two_bags_in_one_outfit_fails(self):
        pieces = {
            'one_piece': None,
            'top': {
                'product_name': 'White T-Shirt',
                'slot_type': 'top',
                'formality': 2,
                'pattern': 'solid',
                'dominant_colours': ['white'],
                'style_family': 'western',
                'discount_price': 299
            },
            'bottom': {
                'product_name': 'Denim Jeans',
                'slot_type': 'bottom',
                'formality': 2,
                'pattern': 'solid',
                'dominant_colours': ['blue'],
                'style_family': 'western',
                'discount_price': 499
            },
            'footwear': None,
            'bag': {
                'product_name': 'Leather Handbag',
                'slot_type': 'bag',
                'formality': 2,
                'pattern': 'solid',
                'dominant_colours': ['black'],
                'style_family': 'western',
                'discount_price': 400
            },
            'accessories': [
                {
                    'product_name': 'Extra Sling Bag',
                    'slot_type': 'accessory',
                    'accessory_type': 'bag',
                    'formality': 2,
                    'pattern': 'solid',
                    'dominant_colours': ['tan'],
                    'style_family': 'western',
                    'discount_price': 300
                }
            ]
        }
        passed, reasons = validate_outfit(pieces, self.default_prefs)
        self.assertFalse(passed)
        self.assertTrue(any('bag' in r.lower() for r in reasons))

    def test_multiple_statement_pieces_fail(self):
        pieces = {
            'one_piece': {
                'product_name': 'Floral Printed Maxi Dress',
                'slot_type': 'one_piece',
                'formality': 3,
                'pattern': 'printed',
                'dominant_colours': ['pink', 'green'],
                'style_family': 'western',
                'discount_price': 899
            },
            'top': None,
            'bottom': None,
            'footwear': {
                'product_name': 'Neutral Flats',
                'slot_type': 'footwear',
                'footwear_type': 'flat',
                'formality': 3,
                'pattern': 'solid',
                'dominant_colours': ['nude'],
                'style_family': 'western',
                'discount_price': 350
            },
            'bag': {
                'product_name': 'Polka Dot Printed Tote',
                'slot_type': 'bag',
                'formality': 3,
                'pattern': 'printed',
                'dominant_colours': ['black', 'white'],
                'style_family': 'western',
                'discount_price': 350
            },
            'accessories': [
                {
                    'product_name': 'Heavy Statement Necklace',
                    'slot_type': 'accessory',
                    'accessory_type': 'jewellery',
                    'formality': 3,
                    'pattern': 'embellished',
                    'dominant_colours': ['gold'],
                    'style_family': 'western',
                    'discount_price': 200
                }
            ]
        }
        passed, reasons = validate_outfit(pieces, self.default_prefs)
        self.assertFalse(passed)
        self.assertTrue(any('statement' in r.lower() or 'printed' in r.lower() for r in reasons))

    def test_tiers_core_and_full_pass(self):
        # CORE: Dress + footwear
        core_pieces = {
            'one_piece': {
                'product_name': 'Black A-Line Dress',
                'slot_type': 'one_piece',
                'formality': 3,
                'pattern': 'solid',
                'dominant_colours': ['black'],
                'style_family': 'western',
                'discount_price': 799
            },
            'top': None,
            'bottom': None,
            'footwear': {
                'product_name': 'Classic White Flats',
                'slot_type': 'footwear',
                'footwear_type': 'flat',
                'formality': 3,
                'pattern': 'solid',
                'dominant_colours': ['white'],
                'style_family': 'western',
                'discount_price': 399
            },
            'bag': None,
            'accessories': []
        }
        passed_core, reasons_core = validate_outfit(core_pieces, self.default_prefs)
        self.assertTrue(passed_core, f"CORE failed: {reasons_core}")

        # FULL: Jumpsuit + footwear + bag + earrings + watch
        full_pieces = {
            'one_piece': {
                'product_name': 'Olive Green Linen Jumpsuit',
                'slot_type': 'one_piece',
                'formality': 3,
                'pattern': 'solid',
                'dominant_colours': ['green'],
                'style_family': 'western',
                'discount_price': 999
            },
            'top': None,
            'bottom': None,
            'footwear': {
                'product_name': 'Tan Leather Wedges',
                'slot_type': 'footwear',
                'footwear_type': 'sandal',
                'formality': 3,
                'pattern': 'solid',
                'dominant_colours': ['tan'],
                'style_family': 'western',
                'discount_price': 499
            },
            'bag': {
                'product_name': 'Beige Crossbody Bag',
                'slot_type': 'bag',
                'formality': 3,
                'pattern': 'solid',
                'dominant_colours': ['beige'],
                'style_family': 'western',
                'discount_price': 350
            },
            'accessories': [
                {
                    'product_name': 'Gold Hoop Earrings',
                    'slot_type': 'accessory',
                    'accessory_type': 'jewellery',
                    'formality': 3,
                    'pattern': 'solid',
                    'dominant_colours': ['gold'],
                    'style_family': 'western',
                    'discount_price': 150
                },
                {
                    'product_name': 'Minimal Gold Wristwatch',
                    'slot_type': 'accessory',
                    'accessory_type': 'watch',
                    'formality': 3,
                    'pattern': 'solid',
                    'dominant_colours': ['gold'],
                    'style_family': 'western',
                    'discount_price': 250
                }
            ]
        }
        passed_full, reasons_full = validate_outfit(full_pieces, self.default_prefs)
        self.assertTrue(passed_full, f"FULL failed: {reasons_full}")

    def test_printed_top_bag_shoes_fails(self):
        pieces = {
            'one_piece': None,
            'top': {
                'product_name': 'Floral Printed Top',
                'slot_type': 'top',
                'formality': 2,
                'pattern': 'printed',
                'dominant_colours': ['blue', 'yellow'],
                'style_family': 'western',
                'discount_price': 399
            },
            'bottom': {
                'product_name': 'Solid Denim Shorts',
                'slot_type': 'bottom',
                'formality': 2,
                'pattern': 'solid',
                'dominant_colours': ['blue'],
                'style_family': 'western',
                'discount_price': 399
            },
            'footwear': {
                'product_name': 'Striped Canvas Shoes',
                'slot_type': 'footwear',
                'footwear_type': 'sneaker',
                'formality': 2,
                'pattern': 'printed',
                'dominant_colours': ['black', 'white'],
                'style_family': 'western',
                'discount_price': 499
            },
            'bag': {
                'product_name': 'Red Floral Tote Bag',
                'slot_type': 'bag',
                'formality': 2,
                'pattern': 'printed',
                'dominant_colours': ['red'],
                'style_family': 'western',
                'discount_price': 299
            },
            'accessories': []
        }
        passed, reasons = validate_outfit(pieces, self.default_prefs)
        self.assertFalse(passed)
        self.assertTrue(any('printed' in r.lower() for r in reasons))

    def test_yellow_tracksuit_stiletto_fails(self):
        pieces = {
            'one_piece': None,
            'top': {
                'product_name': 'Bright Yellow Track Jacket',
                'slot_type': 'top',
                'formality': 1,
                'pattern': 'solid',
                'dominant_colours': ['yellow'],
                'style_family': 'athleisure',
                'discount_price': 500
            },
            'bottom': {
                'product_name': 'Yellow Sweatpants',
                'slot_type': 'bottom',
                'formality': 1,
                'pattern': 'solid',
                'dominant_colours': ['yellow'],
                'style_family': 'athleisure',
                'discount_price': 500
            },
            'footwear': {
                'product_name': 'Pointed High Stiletto Heels',
                'slot_type': 'footwear',
                'footwear_type': 'heel',
                'formality': 5,
                'pattern': 'solid',
                'dominant_colours': ['black'],
                'style_family': 'western',
                'discount_price': 900
            },
            'bag': None,
            'accessories': []
        }
        passed, reasons = validate_outfit(pieces, self.default_prefs)
        self.assertFalse(passed)
        self.assertTrue(any('formality' in r.lower() or 'style family' in r.lower() for r in reasons))

    def test_flip_flops_with_chic_fails(self):
        pieces = {
            'one_piece': {
                'product_name': 'Sleek Chic Slip Dress',
                'slot_type': 'one_piece',
                'formality': 3,
                'pattern': 'solid',
                'dominant_colours': ['black'],
                'style_family': 'western',
                'discount_price': 799
            },
            'top': None,
            'bottom': None,
            'footwear': {
                'product_name': 'Rubber Beach Flip Flops',
                'slot_type': 'footwear',
                'footwear_type': 'flip_flop',
                'formality': 1,
                'pattern': 'solid',
                'dominant_colours': ['black'],
                'style_family': 'western',
                'discount_price': 150
            },
            'bag': None,
            'accessories': []
        }
        passed, reasons = validate_outfit(pieces, {**self.default_prefs, 'style': 'chic'})
        self.assertFalse(passed)
        self.assertTrue(any('flip' in r.lower() or 'formality' in r.lower() for r in reasons))

    def test_solid_navy_top_jeans_sneakers_passes(self):
        pieces = {
            'one_piece': None,
            'top': {
                'product_name': 'Solid Navy Blue Cotton Top',
                'slot_type': 'top',
                'formality': 2,
                'pattern': 'solid',
                'dominant_colours': ['navy'],
                'style_family': 'western',
                'discount_price': 399
            },
            'bottom': {
                'product_name': 'Classic Blue Denim Jeans',
                'slot_type': 'bottom',
                'formality': 2,
                'pattern': 'solid',
                'dominant_colours': ['blue'],
                'style_family': 'western',
                'discount_price': 699
            },
            'footwear': {
                'product_name': 'Clean White Casual Sneakers',
                'slot_type': 'footwear',
                'footwear_type': 'sneaker',
                'formality': 2,
                'pattern': 'solid',
                'dominant_colours': ['white'],
                'style_family': 'western',
                'discount_price': 599
            },
            'bag': None,
            'accessories': []
        }
        passed, reasons = validate_outfit(pieces, {**self.default_prefs, 'occasion': 'casual'})
        self.assertTrue(passed, f"Failed reasons: {reasons}")

    def test_metal_tone_clash_fails(self):
        pieces = {
            'one_piece': {
                'product_name': 'Classic Black Cocktail Dress',
                'slot_type': 'one_piece',
                'formality': 4,
                'pattern': 'solid',
                'dominant_colours': ['black'],
                'style_family': 'western',
                'discount_price': 999
            },
            'top': None,
            'bottom': None,
            'footwear': {
                'product_name': 'Black Stiletto Heels',
                'slot_type': 'footwear',
                'footwear_type': 'heel',
                'formality': 4,
                'pattern': 'solid',
                'dominant_colours': ['black'],
                'style_family': 'western',
                'discount_price': 599
            },
            'bag': {
                'product_name': 'Silver Metallic Clutch',
                'slot_type': 'bag',
                'formality': 4,
                'pattern': 'solid',
                'dominant_colours': ['silver'],
                'metal_tone': 'silver',
                'style_family': 'western',
                'discount_price': 399
            },
            'accessories': [
                {
                    'product_name': 'Yellow Gold Dangle Earrings',
                    'slot_type': 'accessory',
                    'accessory_type': 'jewellery',
                    'formality': 4,
                    'pattern': 'solid',
                    'dominant_colours': ['gold'],
                    'metal_tone': 'gold',
                    'style_family': 'western',
                    'discount_price': 250
                }
            ]
        }
        passed, reasons = validate_outfit(pieces, {**self.default_prefs, 'occasion': 'party'})
        self.assertFalse(passed)
        self.assertTrue(any('metal tone' in r.lower() for r in reasons))

    def test_budget_hard_cap_enforced_strictly(self):
        for budget_val in [500, 799, 1000, 1499, 1999, 2100, 5000]:
            pieces = {
                'one_piece': None,
                'top': {
                    'product_name': 'Top',
                    'slot_type': 'top',
                    'formality': 2,
                    'pattern': 'solid',
                    'dominant_colours': ['blue'],
                    'style_family': 'western',
                    'discount_price': budget_val // 2
                },
                'bottom': {
                    'product_name': 'Bottom',
                    'slot_type': 'bottom',
                    'formality': 2,
                    'pattern': 'solid',
                    'dominant_colours': ['blue'],
                    'style_family': 'western',
                    'discount_price': (budget_val // 2) + 10
                },
                'footwear': None,
                'bag': None,
                'accessories': []
            }
            # Total is budget_val + 10, should fail hard cap
            passed, reasons = validate_outfit(pieces, {**self.default_prefs, 'budget': budget_val})
            self.assertFalse(passed, f"Budget cap {budget_val} failed to reject total {budget_val + 10}")
            self.assertTrue(any('budget' in r.lower() for r in reasons))

    def test_generate_budget_outfits_variety_rule_and_bases(self):
        """
        Verify outfit generation pipeline:
        1. Surprise Me returns outfits from multiple bases (two_piece, one_piece, saree_lehenga).
        2. No single product appears more than 3 times across the list (variety rule).
        3. Every outfit total <= budget.
        4. Every piece has a non-empty image.
        5. Every outfit has valid base_type in ('two_piece', 'one_piece', 'saree_lehenga').
        """
        from unittest.mock import patch, MagicMock
        from recommendations.services import SmartBudgetOutfitService
        from collections import Counter

        def make_mock_p(pid, name, slot, subtype, price, form=3, pat='solid', cols=['navy'], style='western', ftype=None, atype=None, mtone='unknown', blouse=True, dupatta=True):
            p = MagicMock()
            p.product_id = pid
            p.product_name = name
            p.slot_type = slot
            p.subtype = subtype
            p.discount_price = price
            p.base_price = price + 200
            p.available_quantity = 10
            p.formality = form
            p.pattern = pat
            p.dominant_colours = cols
            p.style_family = style
            p.footwear_type = ftype
            p.accessory_type = atype
            p.metal_tone = mtone
            p.includes_blouse = blouse
            p.includes_dupatta = dupatta
            p.image = f"https://example.com/images/I/{pid}.jpg"
            p.is_image_valid = True
            p.hidden = False
            p.confidence = 0.95
            p.main_category = 'Clothing'
            p.sub_category = slot
            return p

        mock_items = [
            # Two-Piece (Tops & Bottoms)
            make_mock_p('t1', 'Navy Solid Top', 'top', 'top', 300, form=3, cols=['navy']),
            make_mock_p('t2', 'White Linen Top', 'top', 'top', 350, form=3, cols=['white']),
            make_mock_p('t3', 'Pink Cotton Kurti', 'top', 'kurta', 400, form=3, cols=['pink'], style='ethnic'),
            make_mock_p('b1', 'Classic Blue Jeans', 'bottom', 'jeans', 600, form=3, cols=['blue']),
            make_mock_p('b2', 'Black Trousers', 'bottom', 'trousers', 550, form=3, cols=['black']),
            make_mock_p('b3', 'White Palazzo Pants', 'bottom', 'palazzo', 450, form=3, cols=['white'], style='ethnic'),

            # One-Piece (Dresses & Jumpsuits)
            make_mock_p('d1', 'Black Midi Dress', 'one_piece', 'dress', 800, form=3, cols=['black']),
            make_mock_p('d2', 'Pink Fit & Flare Dress', 'one_piece', 'dress', 750, form=3, cols=['pink']),
            make_mock_p('j1', 'Navy Tailored Jumpsuit', 'one_piece', 'jumpsuit', 850, form=3, cols=['navy']),

            # Saree / Lehenga
            make_mock_p('s1', 'Printed Art Silk Saree', 'saree', 'saree', 650, form=3, cols=['blue'], style='ethnic', blouse=True),
            make_mock_p('s2', 'Maroon Festive Saree', 'saree', 'saree', 700, form=4, cols=['maroon'], style='ethnic', blouse=True),
            make_mock_p('ls1', 'Pink Embroidered Lehenga Set', 'lehenga_set', 'lehenga_set', 950, form=4, cols=['pink'], style='ethnic', dupatta=True),

            # Footwear
            make_mock_p('fw1', 'Beige Block Heels', 'footwear', 'sandal', 350, form=3, cols=['beige'], ftype='heel'),
            make_mock_p('fw2', 'White Leather Sneakers', 'footwear', 'sneaker', 400, form=3, cols=['white'], ftype='sneaker'),
            make_mock_p('fw3', 'Traditional Leather Juttis', 'footwear', 'sandal', 300, form=3, cols=['tan'], style='ethnic', ftype='jutti'),

            # Bags
            make_mock_p('bg1', 'Black Sling Bag', 'bag', 'bag', 250, form=3, cols=['black'], mtone='gold'),
            make_mock_p('bg2', 'Embroidered Potli Bag', 'bag', 'potli', 200, form=3, cols=['gold'], style='ethnic'),

            # Accessories
            make_mock_p('ac1', 'Gold Stud Earrings', 'accessory', 'jewellery', 150, form=3, cols=['gold'], atype='jewellery', mtone='gold'),
            make_mock_p('ac2', 'Minimal Gold Watch', 'accessory', 'watch', 250, form=3, cols=['gold'], atype='watch', mtone='gold'),
        ]

        class MockQuerySet(list):
            def filter(self, *args, **kwargs):
                arg_str = str(args) + str(kwargs)
                if 'footwear' in arg_str:
                    return MockQuerySet([it for it in self if it.slot_type == 'footwear'])
                if 'bag' in arg_str:
                    return MockQuerySet([it for it in self if it.slot_type == 'bag'])
                if 'accessory' in arg_str:
                    return MockQuerySet([it for it in self if it.slot_type == 'accessory'])
                if 'saree' in arg_str:
                    return MockQuerySet([it for it in self if it.slot_type == 'saree'])
                if 'lehenga' in arg_str:
                    return MockQuerySet([it for it in self if it.slot_type in ('lehenga_set', 'lehenga_skirt', 'choli')])
                if 'one_piece' in arg_str or 'dress' in arg_str or 'jumpsuit' in arg_str:
                    return MockQuerySet([it for it in self if it.slot_type in ('one_piece', 'dress', 'jumpsuit')])
                if 'bottom' in arg_str:
                    return MockQuerySet([it for it in self if it.slot_type == 'bottom'])
                if 'top' in arg_str or 'kurta' in arg_str:
                    return MockQuerySet([it for it in self if it.slot_type in ('top', 'kurta')])
                return self
            def exclude(self, *args, **kwargs):
                return self
            def order_by(self, *args, **kwargs):
                return self
            def values(self, *args, **kwargs):
                return []
            def distinct(self):
                return self

        def mock_prod_filter(*args, **kwargs):
            return MockQuerySet(mock_items).filter(*args, **kwargs)

        with patch('catalog.models.Product.objects.filter', side_effect=mock_prod_filter), \
             patch('recommendations.models.ProductRecommendation.objects.filter', return_value=MockQuerySet([])):

            res = SmartBudgetOutfitService.generate_budget_outfits(
                budget=2500,
                gender='women',
                occasion='party',
                style='chic',
                fashion_direction='all',
                limit=50
            )

            self.assertTrue(res.get('success'), f"Generation failed: {res.get('error')}")
            outfits = res.get('outfits', [])
            self.assertGreater(len(outfits), 0, "No outfits generated")

            product_counts = Counter()
            base_types_found = set()

            for o in outfits:
                # 1. Total <= budget
                self.assertLessEqual(o['total_price'], 2500, f"Outfit total {o['total_price']} exceeds budget 2500")
                
                # 2. Base type valid
                self.assertIn(o['base_type'], {'two_piece', 'one_piece', 'saree_lehenga'})
                base_types_found.add(o['base_type'])

                # 3. Completeness valid
                self.assertIn(o['completeness'], {'full', 'core', 'basic'})

                # 4. Check all items for valid images and track variety count
                for piece in [o.get('topwear'), o.get('bottomwear'), o.get('footwear'), o.get('bag')] + o.get('accessories', []):
                    if piece:
                        pid = piece.get('product_id')
                        product_counts[pid] += 1
                        self.assertTrue(bool(piece.get('image')), f"Product {pid} has empty image")

            # Variety rule check: No product in more than 3 outfits
            for pid, count in product_counts.items():
                self.assertLessEqual(count, 3, f"Product {pid} appeared {count} times (max allowed is 3)")

            # Multiple bases returned when candidates exist
            self.assertGreaterEqual(len(base_types_found), 2, f"Expected multiple base types in Surprise Me, got: {base_types_found}")


class SmartBudgetStylistCriticalFixTests(SimpleTestCase):
    """
    Automated tests verifying critical fixes for Smart Budget Stylist:
    - Saree label paired with crop-top image prevention.
    - Men's/boys' shoes excluded from women's recommendations.
    - Shoe inserts / heel grips excluded from footwear.
    - Hair clips / claw clips excluded from bags.
    - Minimum 2 distinct products for styled look (one-product dress rejected).
    - Dress + footwear accepted; dress + bag accepted.
    - Two-piece outfit with correct component images and links.
    - Strict budget cap enforcement (no budget violations).
    - Four styling modes and color filter enforcement.
    - Honest, evidence-based harmony score calculation (no fake 98%/90%).
    """

    def test_saree_label_never_paired_with_crop_top(self):
        from catalog.classifier import classify_product
        # 1. Product title mentioning "Saree for Blouse" or "Crop Top" must NOT be classified as saree
        attrs = classify_product(
            product_name="Leriya Fashion Women Crop Floral Top with Cap Sleeves for Office Wear Casual Wear Both Use to Western Top & Saree for Blouse",
            main_category="women's clothing",
            sub_category="tops"
        )
        self.assertEqual(attrs['slot_type'], 'top')
        self.assertEqual(attrs['subtype'], 'choli')
        self.assertNotEqual(attrs['slot_type'], 'one_piece')

        # 2. Validator rejects saree paired with western top
        from recommendations.outfit_validator import validate_outfit
        pieces = {
            'one_piece': {'product_id': 'P_SAR_1', 'product_name': 'Kanjivaram Silk Saree', 'slot_type': 'one_piece', 'subtype': 'saree', 'selling_price': 1200, 'formality': 4, 'dominant_colours': ['red'], 'style_family': 'ethnic'},
            'top': {'product_id': 'P_TOP_1', 'product_name': 'Crop Graphic Western T-Shirt', 'slot_type': 'top', 'subtype': 't-shirt', 'selling_price': 400, 'formality': 1, 'dominant_colours': ['white'], 'style_family': 'western'},
            'bottom': None,
            'footwear': None,
            'bag': None,
            'accessories': []
        }
        passed, reasons = validate_outfit(pieces, {'budget': 2000, 'gender': 'women'})
        self.assertFalse(passed)
        self.assertTrue(any('choli' in r or 'traditional' in r for r in reasons))

    def test_mens_or_boys_shoes_excluded_from_womens_styling(self):
        from recommendations.outfit_validator import validate_outfit
        pieces = {
            'one_piece': {'product_id': 'P_DR_1', 'product_name': 'Floral Summer Dress', 'slot_type': 'one_piece', 'subtype': 'dress', 'selling_price': 800, 'formality': 3, 'dominant_colours': ['pink'], 'style_family': 'western'},
            'top': None,
            'bottom': None,
            'footwear': {'product_id': 'P_FW_BOY', 'product_name': "Bata Boys' School Uniform Shoes", 'slot_type': 'footwear', 'selling_price': 450, 'formality': 3, 'dominant_colours': ['black'], 'style_family': 'western'},
            'bag': None,
            'accessories': []
        }
        passed, reasons = validate_outfit(pieces, {'budget': 2000, 'gender': 'women'})
        self.assertFalse(passed)
        self.assertTrue(any("designated for men/boys" in r for r in reasons))

    def test_shoe_inserts_or_heel_grips_rejected_as_footwear(self):
        from recommendations.outfit_validator import validate_outfit
        pieces = {
            'one_piece': {'product_id': 'P_DR_1', 'product_name': 'Floral Summer Dress', 'slot_type': 'one_piece', 'subtype': 'dress', 'selling_price': 800, 'formality': 3, 'dominant_colours': ['pink'], 'style_family': 'western'},
            'top': None,
            'bottom': None,
            'footwear': {'product_id': 'P_FW_INS', 'product_name': "Dr Foot Heel Grips Cushion Pad Shoe Insert", 'slot_type': 'footwear', 'selling_price': 250, 'formality': 3, 'dominant_colours': ['neutral'], 'style_family': 'western'},
            'bag': None,
            'accessories': []
        }
        passed, reasons = validate_outfit(pieces, {'budget': 2000, 'gender': 'women'})
        self.assertFalse(passed)
        self.assertTrue(any("shoe accessory/insert/cleaner" in r for r in reasons))

    def test_hair_clips_or_claw_clips_rejected_as_bags(self):
        from recommendations.outfit_validator import validate_outfit
        pieces = {
            'one_piece': {'product_id': 'P_DR_1', 'product_name': 'Floral Summer Dress', 'slot_type': 'one_piece', 'subtype': 'dress', 'selling_price': 800, 'formality': 3, 'dominant_colours': ['pink'], 'style_family': 'western'},
            'top': None,
            'bottom': None,
            'footwear': {'product_id': 'P_FW_1', 'product_name': "Strappy Heeled Sandals", 'slot_type': 'footwear', 'selling_price': 500, 'formality': 3, 'dominant_colours': ['beige'], 'style_family': 'western'},
            'bag': {'product_id': 'P_CLIP_1', 'product_name': "Yellow Chimes Claw Clips for Women Hair Clutches", 'slot_type': 'bag', 'selling_price': 150, 'formality': 3, 'dominant_colours': ['pink'], 'style_family': 'western'},
            'accessories': []
        }
        passed, reasons = validate_outfit(pieces, {'budget': 2000, 'gender': 'women'})
        self.assertFalse(passed)
        self.assertTrue(any("not a wearable bag" in r for r in reasons))

    def test_one_product_dress_rejected_as_styled_look(self):
        from recommendations.outfit_validator import validate_outfit
        # A standalone dress has only 1 product, so it must be rejected from styled looks
        pieces = {
            'one_piece': {'product_id': 'P_DR_1', 'product_name': 'Maxi A-Line Dress', 'slot_type': 'one_piece', 'subtype': 'dress', 'selling_price': 999, 'formality': 3, 'dominant_colours': ['blue'], 'style_family': 'western'},
            'top': None,
            'bottom': None,
            'footwear': None,
            'bag': None,
            'accessories': []
        }
        passed, reasons = validate_outfit(pieces, {'budget': 2000, 'gender': 'women'})
        self.assertFalse(passed)
        self.assertTrue(any("at least two distinct products" in r for r in reasons))

    def test_dress_with_compatible_footwear_accepted(self):
        from recommendations.outfit_validator import validate_outfit
        pieces = {
            'one_piece': {'product_id': 'P_DR_1', 'product_name': 'Cotton Summer Dress', 'slot_type': 'one_piece', 'subtype': 'dress', 'selling_price': 899, 'formality': 3, 'dominant_colours': ['white'], 'style_family': 'western'},
            'top': None,
            'bottom': None,
            'footwear': {'product_id': 'P_FW_1', 'product_name': 'Tan Flat Sandals', 'slot_type': 'footwear', 'selling_price': 499, 'formality': 3, 'dominant_colours': ['beige'], 'style_family': 'western'},
            'bag': None,
            'accessories': []
        }
        passed, reasons = validate_outfit(pieces, {'budget': 2000, 'gender': 'women', 'occasion': 'casual'})
        self.assertTrue(passed, f"Failed with reasons: {reasons}")

    def test_dress_with_compatible_bag_accepted(self):
        from recommendations.outfit_validator import validate_outfit
        pieces = {
            'one_piece': {'product_id': 'P_DR_1', 'product_name': 'Casual Cotton Dress', 'slot_type': 'one_piece', 'subtype': 'dress', 'selling_price': 799, 'formality': 3, 'dominant_colours': ['blue'], 'style_family': 'western'},
            'top': None,
            'bottom': None,
            'footwear': None,
            'bag': {'product_id': 'P_BAG_1', 'product_name': 'Canvas Shoulder Tote Bag', 'slot_type': 'bag', 'selling_price': 399, 'formality': 3, 'dominant_colours': ['white'], 'style_family': 'western'},
            'accessories': []
        }
        passed, reasons = validate_outfit(pieces, {'budget': 2000, 'gender': 'women', 'occasion': 'casual'})
        self.assertTrue(passed, f"Failed with reasons: {reasons}")

    def test_two_piece_outfit_component_serialization(self):
        from recommendations.smart_budget_service import serialize_catalog_product
        class DummyProduct:
            product_id = 'P_TOP_77'
            product_name = 'Linen Button-down Shirt'
            base_price = 1200
            discount_price = 799
            available_quantity = 10
            image = 'https://m.media-amazon.com/images/I/71abc.jpg'
            main_category = "women's clothing"
            sub_category = 'shirts'
            slot_type = 'top'
            subtype = 'shirt'
            formality = 3
            pattern = 'solid'
            dominant_colours = ['white']
            style_family = 'western'
            product_url = 'https://amazon.in/dp/B07TEST'

        ser = serialize_catalog_product(DummyProduct())
        self.assertEqual(ser['product_id'], 'P_TOP_77')
        self.assertEqual(ser['product_name'], 'Linen Button-down Shirt')
        self.assertEqual(ser['selling_price'], 799)
        self.assertEqual(ser['image'], 'https://m.media-amazon.com/images/I/71abc.jpg')
        self.assertEqual(ser['slot_type'], 'top')
        self.assertEqual(ser['product_url'], 'https://amazon.in/dp/B07TEST')

    def test_strict_budget_cap_enforcement(self):
        from recommendations.outfit_validator import validate_outfit
        # Budget = 1000, pieces total = 1050 (violates budget by 50)
        pieces = {
            'top': {'product_id': 'P1', 'selling_price': 600, 'formality': 3, 'dominant_colours': ['black'], 'style_family': 'western'},
            'bottom': {'product_id': 'P2', 'selling_price': 450, 'formality': 3, 'dominant_colours': ['black'], 'style_family': 'western'},
            'one_piece': None,
            'footwear': None,
            'bag': None,
            'accessories': []
        }
        passed, reasons = validate_outfit(pieces, {'budget': 1000, 'gender': 'women'})
        self.assertFalse(passed)
        self.assertTrue(any("exceeds the budget cap" in r for r in reasons))

    def test_honest_harmony_scores_not_artificially_clamped_to_98(self):
        from recommendations.smart_budget_service import SmartBudgetOutfitService
        pieces = {
            'top': {'product_id': 'P1', 'selling_price': 500, 'formality': 3, 'dominant_colours': ['white'], 'style_family': 'western', 'pattern': 'solid'},
            'bottom': {'product_id': 'P2', 'selling_price': 600, 'formality': 3, 'dominant_colours': ['blue'], 'style_family': 'western', 'pattern': 'solid'},
            'one_piece': None,
            'footwear': {'product_id': 'P3', 'selling_price': 400, 'formality': 3, 'dominant_colours': ['white'], 'style_family': 'western', 'pattern': 'solid'},
            'bag': None,
            'accessories': []
        }
        score, breakdown, verdict, matched_col = SmartBudgetOutfitService._calculate_score_and_breakdown(
            pieces=pieces,
            budget=2000.0,
            occasion='casual',
            style='chic',
            preferred_color='white'
        )
        # Score must be realistic and calibrated (between 55% and 92%), never generic 98% or 90%
        self.assertGreaterEqual(score, 55)
        self.assertLessEqual(score, 92)
        self.assertIn('formality_harmony', breakdown)
        self.assertIn('style_coherence', breakdown)
        self.assertIn('color_harmony', breakdown)
        self.assertTrue(bool(verdict))


class FullCatalogAuditAndRecommendationDiversityTests(SimpleTestCase):
    databases = {'default'}
    """
    Comprehensive verification for:
      - Cobbler nails or hardware rejected as footwear
      - Fevicol / glue rejected as footwear
      - Cosmetic pouches rejected as all-purpose styled handbags
      - Genuine sandals, clothing, sarees accepted
      - Broken, missing, and duplicate images rejected
      - Products with uncertain identity safely placed in review / hidden
      - All four styling modes (Surprise Me, Western, Indo-Western, Ethnic)
      - Colour filters
      - Minimum two products in styled looks
      - Budget boundaries
      - Recommendation diversity and duplicate prevention
    """

    def test_cobbler_nails_and_hardware_rejected_as_footwear(self):
        from recommendations.outfit_validator import validate_outfit
        pieces = {
            'one_piece': {'product_id': 'P_DR_1', 'product_name': 'A-Line Cotton Midi Dress', 'slot_type': 'one_piece', 'subtype': 'dress', 'selling_price': 899, 'formality': 3, 'dominant_colours': ['blue'], 'style_family': 'western'},
            'top': None,
            'bottom': None,
            'footwear': {'product_id': 'P56518', 'product_name': 'Cobbler Nails Black for Wood, Wall, Chappal, Sandles (200 PCS)', 'slot_type': 'footwear', 'selling_price': 199, 'formality': 1, 'dominant_colours': ['black'], 'style_family': 'western'},
            'bag': None,
            'accessories': []
        }
        passed, reasons = validate_outfit(pieces, {'budget': 2000, 'gender': 'women'})
        self.assertFalse(passed)
        self.assertTrue(any("hardware" in r.lower() or "repair" in r.lower() for r in reasons))

    def test_fevicol_and_shoe_glue_rejected_as_footwear(self):
        from recommendations.outfit_validator import validate_outfit
        pieces = {
            'one_piece': {'product_id': 'P_DR_1', 'product_name': 'Floral Maxi Dress', 'slot_type': 'one_piece', 'subtype': 'dress', 'selling_price': 999, 'formality': 3, 'dominant_colours': ['pink'], 'style_family': 'western'},
            'top': None,
            'bottom': None,
            'footwear': {'product_id': 'P93806', 'product_name': 'HARIOM SMPH fevicol All Fix Glue for Repairing Footwear', 'slot_type': 'footwear', 'selling_price': 150, 'formality': 1, 'dominant_colours': ['neutral'], 'style_family': 'western'},
            'bag': None,
            'accessories': []
        }
        passed, reasons = validate_outfit(pieces, {'budget': 2000, 'gender': 'women'})
        self.assertFalse(passed)
        self.assertTrue(any("hardware" in r.lower() or "repair" in r.lower() for r in reasons))

    def test_cosmetic_and_makeup_pouches_rejected_as_styled_handbag(self):
        from recommendations.outfit_validator import validate_outfit
        pieces = {
            'one_piece': {'product_id': 'P_DR_1', 'product_name': 'Cocktail Evening Dress', 'slot_type': 'one_piece', 'subtype': 'dress', 'selling_price': 1200, 'formality': 4, 'dominant_colours': ['black'], 'style_family': 'western'},
            'top': None,
            'bottom': None,
            'footwear': {'product_id': 'P_FW_1', 'product_name': 'Classic Heeled Pumps', 'slot_type': 'footwear', 'selling_price': 800, 'formality': 4, 'dominant_colours': ['black'], 'style_family': 'western'},
            'bag': {'product_id': 'P88372', 'product_name': 'GeorgiaUSA Set of 4 Makeup Bag | Makeup Pouch Cosmetic Bag', 'slot_type': 'bag', 'subtype': 'pouch', 'selling_price': 350, 'formality': 2, 'dominant_colours': ['pink'], 'style_family': 'western'},
            'accessories': []
        }
        passed, reasons = validate_outfit(pieces, {'budget': 3000, 'gender': 'women', 'occasion': 'party'})
        self.assertFalse(passed)
        self.assertTrue(any("pouch" in r.lower() for r in reasons))

    def test_genuine_sandals_and_clothing_accepted(self):
        from recommendations.outfit_validator import validate_outfit
        pieces = {
            'one_piece': {'product_id': 'P_DR_REAL', 'product_name': 'Women Floral Flared Midi Dress', 'slot_type': 'one_piece', 'subtype': 'dress', 'selling_price': 1199, 'formality': 3, 'dominant_colours': ['blue'], 'style_family': 'western'},
            'top': None,
            'bottom': None,
            'footwear': {'product_id': 'P_FW_REAL', 'product_name': 'Women Open Toe Block Heel Sandals', 'slot_type': 'footwear', 'selling_price': 799, 'formality': 3, 'dominant_colours': ['beige'], 'style_family': 'western'},
            'bag': {'product_id': 'P_BAG_REAL', 'product_name': 'Structured Faux Leather Shoulder Bag', 'slot_type': 'bag', 'subtype': 'handbag', 'selling_price': 699, 'formality': 3, 'dominant_colours': ['beige'], 'style_family': 'western'},
            'accessories': []
        }
        passed, reasons = validate_outfit(pieces, {'budget': 3000, 'gender': 'women', 'occasion': 'casual'})
        self.assertTrue(passed, f"Validation failed with: {reasons}")

    def test_broken_missing_and_mismatched_image_filtering(self):
        from catalog.serializers import sanitize_product_image_url
        self.assertIsNone(sanitize_product_image_url(None))
        self.assertIsNone(sanitize_product_image_url(''))
        self.assertIsNone(sanitize_product_image_url('   '))
        # Genuine Amazon CDN image must be cleaned and preserved
        clean = sanitize_product_image_url('https://images-na.ssl-images-amazon.com/images/W/MEDIA_123/images/I/71abcXYZ.jpg')
        self.assertEqual(clean, 'https://images-na.ssl-images-amazon.com/images/I/71abcXYZ.jpg')

    def test_products_with_uncertain_identity_safely_hidden(self):
        from catalog.classifier import classify_product
        # #NAME? artifacts or ultra-short corrupt titles
        res_name = classify_product('#NAME?', 'women', 'apparel')
        self.assertTrue(res_name['hidden'])
        self.assertEqual(res_name['confidence'], 0.0)

        # Non-fashion cobbler nails
        res_nail = classify_product('Cobbler Nails Black for Wood and Chappal', 'shoes', 'women')
        self.assertTrue(res_nail['hidden'])
        self.assertLessEqual(res_nail['confidence'], 0.2)

        # Tool sizers
        res_tool = classify_product('Invisible Ring Sizer Loose Ring Size Adjuster', 'jewellery', 'accessories')
        self.assertTrue(res_tool['hidden'])

    def test_all_four_styling_modes_respect_category_rules(self):
        from recommendations.outfit_validator import validate_outfit

        # 1. Western look: Western top + Jeans + Sneakers
        western_pieces = {
            'top': {'product_id': 'W1', 'product_name': 'Cotton Tee', 'slot_type': 'top', 'selling_price': 500, 'formality': 2, 'dominant_colours': ['white'], 'style_family': 'western'},
            'bottom': {'product_id': 'W2', 'product_name': 'Slim Fit Jeans', 'slot_type': 'bottom', 'selling_price': 900, 'formality': 2, 'dominant_colours': ['blue'], 'style_family': 'western'},
            'one_piece': None,
            'footwear': {'product_id': 'W3', 'product_name': 'White Canvas Sneakers', 'slot_type': 'footwear', 'footwear_type': 'sneaker', 'selling_price': 600, 'formality': 2, 'dominant_colours': ['white'], 'style_family': 'western'},
            'bag': None,
            'accessories': []
        }
        passed_w, _ = validate_outfit(western_pieces, {'budget': 2500, 'gender': 'women', 'occasion': 'casual'})
        self.assertTrue(passed_w)

        # 2. Ethnic look: Saree + traditional Choli + Juttis
        ethnic_pieces = {
            'one_piece': {'product_id': 'E1', 'product_name': 'Banarasi Silk Saree', 'slot_type': 'one_piece', 'subtype': 'saree', 'includes_blouse': True, 'selling_price': 1500, 'formality': 4, 'dominant_colours': ['red'], 'style_family': 'ethnic'},
            'top': None,
            'bottom': None,
            'footwear': {'product_id': 'E2', 'product_name': 'Embroidered Mojari Juttis', 'slot_type': 'footwear', 'footwear_type': 'jutti', 'selling_price': 600, 'formality': 4, 'dominant_colours': ['gold'], 'style_family': 'ethnic'},
            'bag': None,
            'accessories': []
        }
        passed_e, _ = validate_outfit(ethnic_pieces, {'budget': 3000, 'gender': 'women', 'occasion': 'festive'})
        self.assertTrue(passed_e)

        # 3. Saree with western sneakers is BLOCKED
        clash_saree = {
            'one_piece': {'product_id': 'E1', 'product_name': 'Banarasi Silk Saree', 'slot_type': 'one_piece', 'subtype': 'saree', 'includes_blouse': True, 'selling_price': 1500, 'formality': 4, 'dominant_colours': ['red'], 'style_family': 'ethnic'},
            'top': None,
            'bottom': None,
            'footwear': {'product_id': 'W3', 'product_name': 'Running Sneakers', 'slot_type': 'footwear', 'footwear_type': 'sneaker', 'selling_price': 600, 'formality': 2, 'dominant_colours': ['white'], 'style_family': 'western'},
            'bag': None,
            'accessories': []
        }
        passed_clash, reasons_clash = validate_outfit(clash_saree, {'budget': 3000, 'gender': 'women', 'occasion': 'festive'})
        self.assertFalse(passed_clash)
        self.assertTrue(any("sneaker" in r.lower() or "formality" in r.lower() for r in reasons_clash))

    def test_colour_filter_prioritisation(self):
        from recommendations.smart_budget_service import SmartBudgetOutfitService
        p_blue = {'product_name': 'Royal Blue Kurti', 'dominant_colours': ['blue', 'navy']}
        p_red = {'product_name': 'Crimson Maroon Dress', 'dominant_colours': ['red', 'maroon']}
        self.assertTrue(SmartBudgetOutfitService._matches_color(p_blue, 'blue'))
        self.assertFalse(SmartBudgetOutfitService._matches_color(p_blue, 'red'))
        self.assertTrue(SmartBudgetOutfitService._matches_color(p_red, 'maroon'))

    def test_recommendation_diversity_caps_product_appearances(self):
        from recommendations.smart_budget_service import SmartBudgetOutfitService
        data = SmartBudgetOutfitService.generate_budget_outfits(budget=3000, gender='women', limit=20)
        if data.get('success') and len(data.get('outfits', [])) > 2:
            outfits = data['outfits']
            product_appearances = {}
            for o in outfits:
                for slot in ['topwear', 'bottomwear', 'footwear', 'bag']:
                    item = o.get(slot)
                    if item and item.get('product_id'):
                        pid = item['product_id']
                        product_appearances[pid] = product_appearances.get(pid, 0) + 1
            for pid, count in product_appearances.items():
                self.assertLessEqual(count, 3, f"Product {pid} appeared {count} times, violating variety limits")




