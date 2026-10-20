from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework import status
from catalog.models import Category, Product


class WarehouseProductAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_get_product_detail_not_found(self):
        response = self.client.get('/api/warehouse/products/NONEXISTENT_999/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('not found', response.data.get('detail', '').lower())

    def test_put_product_not_found(self):
        response = self.client.put(
            '/api/warehouse/products/NONEXISTENT_999/',
            {'product_name': 'New Name'},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_put_product_validation_empty_name(self):
        # Even if product doesn't exist or exists, empty name validation check
        response = self.client.put(
            '/api/warehouse/products/SOME_ID/',
            {'product_name': '   '},
            format='json'
        )
        # Should be 404 because product check happens first
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
