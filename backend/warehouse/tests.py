from django.test import TestCase, override_settings
from rest_framework.test import APIClient, APIRequestFactory, force_authenticate
from rest_framework import status
from warehouse.serializers import WarehouseProductUpdateSerializer
from warehouse.views import WarehouseProductDetailView
from accounts.authentication import AuthenticatedUser
from accounts.models import Role


class WarehouseProductAPITests(TestCase):
    """
    Authorization and validation tests for the warehouse product edit
    endpoint.  These avoid touching the live `public.products` data:
    permission checks run before any database read in the view.
    """
    def setUp(self):
        self.client = APIClient()
        self.factory = APIRequestFactory()

    def test_anonymous_put_is_rejected(self):
        """Product updates require authentication (enforced server-side)."""
        response = self.client.put(
            '/api/warehouse/products/SOME_ID/',
            {'product_name': 'New Name'},
            format='json'
        )
        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)
        )

    def test_customer_put_is_forbidden(self):
        """A CUSTOMER role cannot modify product records."""
        request = self.factory.put(
            '/api/warehouse/products/SOME_ID/',
            {'product_name': 'Hacked Name'},
            format='json'
        )
        force_authenticate(request, user=AuthenticatedUser('1', 'c@x.y', Role.CUSTOMER))
        response = WarehouseProductDetailView.as_view()(request, product_id='SOME_ID')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_delivery_partner_put_is_forbidden(self):
        """Only warehouse managers (per established rules) may edit products."""
        request = self.factory.put(
            '/api/warehouse/products/SOME_ID/',
            {'product_name': 'Hacked Name'},
            format='json'
        )
        force_authenticate(request, user=AuthenticatedUser('2', 'd@x.y', Role.DELIVERY_PARTNER))
        response = WarehouseProductDetailView.as_view()(request, product_id='SOME_ID')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class WarehouseProductUpdateMappingTests(TestCase):
    """
    update_product passes model FIELD names to save(update_fields=...) —
    passing db_column names (e.g. 'name') raises ValueError at runtime.
    Verified statically so no live products table is required.
    """
    def test_field_map_targets_real_model_fields(self):
        from warehouse.services import WarehouseService
        from catalog.models import Product
        product_field_names = {f.name for f in Product._meta.fields}
        # Every update target must be a real Product FIELD name — Django's
        # save(update_fields=[...]) raises ValueError for db_column names.
        self.assertEqual(
            sorted(WarehouseService.UPDATE_FIELD_MAP.keys()),
            ['actual_price', 'available_quantity', 'discount_price', 'image',
             'link', 'main_category', 'product_name', 'sub_category'],
        )
        for model_attr in WarehouseService.UPDATE_FIELD_MAP.values():
            self.assertIn(model_attr, product_field_names,
                          f"update_fields value '{model_attr}' is not a Product field name")


class WarehouseProductUpdateSerializerTests(TestCase):
    """Validation rules run without database access."""

    def test_valid_real_schema_payload(self):
        serializer = WarehouseProductUpdateSerializer(data={
            'product_name': 'Silk Maxi Dress',
            'main_category': "women's clothing",
            'sub_category': 'Western Wear',
            'image': 'https://example.com/img.jpg',
            'link': 'https://example.com/product',
            'discount_price': 1499.5,
            'actual_price': '1,999',
            'available_quantity': 25,
        })
        self.assertTrue(serializer.is_valid(), serializer.errors)
        # actual_price stays text; numeric columns stay numeric
        self.assertEqual(serializer.validated_data['actual_price'], '1,999')
        self.assertEqual(serializer.validated_data['available_quantity'], 25.0)

    def test_empty_product_name_rejected(self):
        serializer = WarehouseProductUpdateSerializer(data={'product_name': '   '})
        self.assertFalse(serializer.is_valid())

    def test_negative_stock_rejected(self):
        serializer = WarehouseProductUpdateSerializer(data={
            'product_name': 'Valid Name',
            'available_quantity': -3,
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn('available_quantity', serializer.errors)

    def test_non_finite_prices_rejected(self):
        for bad_value in (float('inf'), float('nan'), float('-inf')):
            serializer = WarehouseProductUpdateSerializer(data={
                'product_name': 'Valid Name',
                'discount_price': bad_value,
            })
            self.assertFalse(serializer.is_valid(), f'{bad_value} must be rejected')
            self.assertIn('discount_price', serializer.errors)

    def test_non_numeric_price_string_rejected(self):
        serializer = WarehouseProductUpdateSerializer(data={
            'product_name': 'Valid Name',
            'discount_price': 'free',
        })
        self.assertFalse(serializer.is_valid())
