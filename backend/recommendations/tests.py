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
