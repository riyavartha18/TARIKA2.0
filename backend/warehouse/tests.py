from django.test import TestCase, override_settings
from rest_framework.test import APIClient, APIRequestFactory, force_authenticate
from rest_framework import status
from warehouse.serializers import WarehouseProductUpdateSerializer
from warehouse.views import WarehouseProductDetailView, WarehouseProductListView
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

    def test_anonymous_product_list_is_rejected(self):
        response = self.client.get('/api/warehouse/products/')
        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)
        )

    def test_customer_product_list_is_forbidden(self):
        request = self.factory.get('/api/warehouse/products/')
        force_authenticate(request, user=AuthenticatedUser('1', 'c@x.y', Role.CUSTOMER))
        response = WarehouseProductListView.as_view()(request)
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
            ['actual_price', 'available_quantity', 'confidence', 'discount_price','discounted_price',
             'hidden', 'image','initial_price',  'is_active', 'link', 'main_category',
             'product_name', 'sub_category'],
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
            'initial_price': 3499.5,
            'discount_price': 1499.5,
            'actual_price': '2,000',
            'available_quantity': 25,
            'is_active': False,
            'hidden': True,
            'confidence': 0.85,
        })
        self.assertTrue(serializer.is_valid(), serializer.errors)
        # The final price is normalised into the TEXT column format and the
        # mirror column value is resolved by Django, not trusted from React.
        self.assertEqual(serializer.validated_data['actual_price'], '2000.00')
        self.assertEqual(serializer.validated_data['discounted_price'], 2000.0)
        self.assertEqual(serializer.validated_data['available_quantity'], 25.0)
        self.assertFalse(serializer.validated_data['is_active'])
        self.assertTrue(serializer.validated_data['hidden'])
        self.assertEqual(serializer.validated_data['confidence'], 0.85)

    def test_empty_product_name_rejected(self):
        serializer = WarehouseProductUpdateSerializer(data={'product_name': '   '})
        self.assertFalse(serializer.is_valid())

    def test_status_fields_can_be_updated_without_other_product_fields(self):
        for field in ('is_active', 'hidden'):
            serializer = WarehouseProductUpdateSerializer(data={field: False})
            self.assertTrue(serializer.is_valid(), serializer.errors)
            self.assertIs(serializer.validated_data[field], False)

    def test_confidence_requires_a_value_between_zero_and_one(self):
        for value in (0, 0.6, 1):
            serializer = WarehouseProductUpdateSerializer(data={'confidence': value})
            self.assertTrue(serializer.is_valid(), serializer.errors)

        for value in (-0.01, 1.01):
            serializer = WarehouseProductUpdateSerializer(data={'confidence': value})
            self.assertFalse(serializer.is_valid())
            self.assertIn('confidence', serializer.errors)

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

    def test_unparsable_discounted_price_rejected(self):
        """actual_price is the FINAL selling price: must be numeric text."""
        serializer = WarehouseProductUpdateSerializer(data={
            'product_name': 'Valid Name',
            'initial_price': 1000,
            'actual_price': 'eight hundred',
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn('actual_price', serializer.errors)


def stored_product(initial=1000.0, discount_amount=200.0, final='800.00'):
    """Unsaved Product row carrying the migrated three-field price layout."""
    from catalog.models import Product
    return Product(
        product_id='P-PRICE-1',
        product_name='Price Test Product',
        initial_price=initial,
        discount_price=discount_amount,
        actual_price_text=final,
        discounted_price=float(final) if final not in (None, '') else None,
    )


class WarehouseDiscountAmountInputTests(TestCase):
    """Input method 1: warehouse enters the discount AMOUNT.

    Django calculates the final price and percentage; the amount stays a
    currency value in `discount_price` (never a percentage).
    """

    def test_amount_calculates_final_price_and_percentage(self):
        # Spec example: ₹1,000 original, ₹200 amount -> ₹800 final, 20% OFF.
        serializer = WarehouseProductUpdateSerializer(
            data={
                'product_name': 'Price Test Product',
                'initial_price': 1000.0,
                'discount_price': 200.0,
            },
            context={'product': stored_product()},
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        resolved = serializer.validated_data
        self.assertEqual(resolved['discount_price'], 200.0)
        self.assertEqual(resolved['actual_price'], '800.00')
        self.assertEqual(resolved['discounted_price'], 800.0)

    def test_percentage_is_derived_not_stored(self):
        product = stored_product(initial=1000.0, discount_amount=200.0, final='800.00')
        self.assertEqual(product.discount_percentage, 20.0)
        self.assertEqual(product.discount_price, 200.0)  # amount, not 20

    def test_percentage_two_decimal_precision(self):
        product = stored_product(initial=999.0, discount_amount=43.22222222,
                                 final='955.78')
        self.assertEqual(product.discount_percentage, 4.33)

    def test_amount_exceeding_initial_rejected(self):
        serializer = WarehouseProductUpdateSerializer(
            data={
                'product_name': 'Price Test Product',
                'initial_price': 500.0,
                'discount_price': 600.0,
            },
            context={'product': stored_product(initial=500.0)},
        )
        self.assertFalse(serializer.is_valid())

    def test_negative_amount_rejected(self):
        serializer = WarehouseProductUpdateSerializer(
            data={'product_name': 'Price Test Product', 'discount_price': -10.0},
            context={'product': stored_product()},
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn('discount_price', serializer.errors)


class WarehouseDiscountedPriceInputTests(TestCase):
    """Input method 2: warehouse enters the final DISCOUNTED PRICE.

    Django calculates the discount amount from initial - final and stores it
    in `discount_price`; the entered value is stored in `actual_price`.
    """

    def test_final_price_calculates_amount(self):
        serializer = WarehouseProductUpdateSerializer(
            data={
                'product_name': 'Price Test Product',
                'initial_price': 1000.0,
                'actual_price': '750',
            },
            context={'product': stored_product()},
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        resolved = serializer.validated_data
        self.assertEqual(resolved['discount_price'], 250.0)
        self.assertEqual(resolved['actual_price'], '750.00')
        self.assertEqual(resolved['discounted_price'], 750.0)

    def test_final_price_exceeding_initial_rejected(self):
        serializer = WarehouseProductUpdateSerializer(
            data={
                'product_name': 'Price Test Product',
                'initial_price': 500.0,
                'actual_price': '501',
            },
            context={'product': stored_product(initial=500.0)},
        )
        self.assertFalse(serializer.is_valid())

    def test_negative_final_price_rejected(self):
        serializer = WarehouseProductUpdateSerializer(
            data={
                'product_name': 'Price Test Product',
                'initial_price': 500.0,
                'actual_price': '-1',
            },
            context={'product': stored_product(initial=500.0)},
        )
        self.assertFalse(serializer.is_valid())

    def test_synchronised_inputs_must_agree(self):
        """Both input methods submitted: Django rejects disagreement."""
        serializer = WarehouseProductUpdateSerializer(
            data={
                'product_name': 'Price Test Product',
                'initial_price': 1000.0,
                'discount_price': 200.0,
                'actual_price': '900',
            },
            context={'product': stored_product()},
        )
        self.assertFalse(serializer.is_valid())

    def test_original_price_only_keeps_stored_amount_and_recopies_final(self):
        serializer = WarehouseProductUpdateSerializer(
            data={
                'product_name': 'Price Test Product',
                'initial_price': 2000.0,
            },
            context={'product': stored_product(initial=1000.0, discount_amount=200.0)},
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data['discount_price'], 200.0)
        self.assertEqual(serializer.validated_data['actual_price'], '1800.00')

    def test_zero_initial_price_is_safe(self):
        """Zero original price must never divide by zero."""
        product = stored_product(initial=0.0, discount_amount=0.0, final='0.00')
        self.assertEqual(product.discount_percentage, 0.0)
        serializer = WarehouseProductUpdateSerializer(
            data={'product_name': 'Price Test Product', 'discount_price': 10.0},
            context={'product': product},
        )
        # A discount above a zero-priced product is invalid, not a crash.
        self.assertFalse(serializer.is_valid())
