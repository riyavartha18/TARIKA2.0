from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase
from django.db import DatabaseError
from django.urls import reverse, resolve
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import Customer, Role
from orders.models import Order
from orders.serializers import (
    CheckoutRequestSerializer,
    OrderDetailSerializer,
    build_order_item,
    _iso_date,
)
from orders.services import OrderCreationService, OrderQueryService, CustomerReturnService
from orders.views import (
    CheckoutView,
    OrderDetailView,
    CustomerOrdersListView,
    CustomerOrderReturnView,
)


def make_order(order_id='ORD0000042', quantity=2, final_price=1479.86,
               initial_price=1500.0, discount=20.14, purchase_date='27-03-2026',
               delivery_status='Delivered', rating=4.0, customer_id='U100010'):
    """An unsaved Order row over the real public.orders columns."""
    from catalog.models import Product
    order = Order(
        order_id=order_id,
        quantity=quantity,
        initial_price=initial_price,
        additional_discount=discount,
        final_price=final_price,
        purchase_date=purchase_date,
        delivery_status=delivery_status,
        shipping_time_days=4,
        payment_method='UPI',
        rating=rating,
    )
    order.product = Product(
        product_id='P67929',
        product_name="Pepe Jeans Men's Slim Fit Jeans",
        main_category="men's clothing",
        sub_category='jeans',
        image='https://example.test/jeans.jpg',
        link='https://example.test/link',
        discount_price=739.93,
        actual_price_text='1,500',
        available_quantity=12,
    )
    order.customer = Customer(customer_id=customer_id, customer_name='Asha',
                              email='asha@example.com')
    return order


class OrdersURLTests(SimpleTestCase):
    """The existing order routes keep their addresses."""

    def test_order_list_url_resolves(self):
        url = reverse('orders:order-list')
        self.assertEqual(url, '/api/orders/')
        self.assertEqual(resolve(url).func.view_class, CustomerOrdersListView)

    def test_checkout_url_resolves(self):
        url = reverse('orders:checkout')
        self.assertEqual(url, '/api/orders/checkout/')
        self.assertEqual(resolve(url).func.view_class, CheckoutView)

    def test_order_detail_url_resolves(self):
        url = reverse('orders:order-detail', kwargs={'order_id': 'ORD1'})
        self.assertEqual(url, '/api/orders/ORD1/')
        self.assertEqual(resolve(url).func.view_class, OrderDetailView)


class OrderDateMappingTests(SimpleTestCase):
    """purchase_date TEXT is converted without inventing a value."""

    def test_day_month_year_becomes_iso(self):
        self.assertEqual(_iso_date('27-03-2026'), '2026-03-27')

    def test_unparsable_date_returns_none(self):
        self.assertIsNone(_iso_date('not-a-date'))
        self.assertIsNone(_iso_date(''))
        self.assertIsNone(_iso_date(None))


class OrderStatusMappingTests(SimpleTestCase):
    """Only the delivery_status column signals progress in this schema."""

    def test_statuses_map_to_the_frontend_vocabulary(self):
        expected = {
            'Delivered': 'delivered',
            'In Transit': 'shipped',
            'Delayed': 'processing',
            'Returned': 'returned',
        }
        for raw, mapped in expected.items():
            self.assertEqual(Order(delivery_status=raw).order_status, mapped)

    def test_a_fresh_order_has_no_invented_status(self):
        # A just-placed order stores no status yet, so it reads as processing.
        self.assertEqual(Order(delivery_status=None).order_status, 'processing')


class OrderItemPayloadTests(SimpleTestCase):
    """Line pricing stays self-consistent: unit x quantity == order total."""

    def test_unit_price_and_subtotal(self):
        item = build_order_item(make_order(quantity=2, final_price=1479.86))
        self.assertEqual(item['subtotal'], 1479.86)
        self.assertEqual(item['unit_price'], 739.93)
        self.assertAlmostEqual(item['unit_price'] * item['quantity'], item['subtotal'], places=2)

    def test_product_details_are_joined_from_products(self):
        item = build_order_item(make_order())
        self.assertEqual(item['product_id'], 'P67929')
        self.assertEqual(item['product_name'], "Pepe Jeans Men's Slim Fit Jeans")
        self.assertEqual(item['image'], 'https://example.test/jeans.jpg')
        self.assertEqual(item['category_name'], "men's clothing")

    def test_rating_becomes_the_customer_review(self):
        self.assertEqual(build_order_item(make_order(rating=4.0))['customer_review']['rating'], 4.0)
        self.assertIsNone(build_order_item(make_order(rating=None))['customer_review'])

    def test_no_returns_table_means_no_return_info(self):
        self.assertIsNone(build_order_item(make_order())['return_info'])


class OrderDetailSerializerTests(SimpleTestCase):
    """The My Orders payload exposes only columns the table actually has."""

    def test_payload_shape(self):
        payload = OrderDetailSerializer(make_order()).data
        self.assertEqual(payload['order_id'], 'ORD0000042')
        self.assertEqual(payload['order_date'], '2026-03-27')
        self.assertEqual(payload['order_date_display'], '27-03-2026')
        self.assertEqual(payload['order_status'], 'delivered')
        self.assertEqual(payload['delivery_status'], 'Delivered')
        self.assertEqual(payload['payment_method'], 'UPI')
        self.assertEqual(payload['total_amount'], 1479.86)
        self.assertEqual(payload['discount_amount'], 20.14)
        self.assertEqual(payload['delivery']['shipping_time_days'], 4)
        self.assertEqual(len(payload['items']), 1)

    def test_fields_absent_from_the_schema_are_null_not_fake(self):
        payload = OrderDetailSerializer(make_order()).data
        self.assertIsNone(payload['payment_status'])
        self.assertIsNone(payload['shipping_address'])
        self.assertIsNone(payload['warehouse_name'])
        self.assertIsNone(payload['transaction_reference'])

    def test_customer_details_are_the_requesters_own(self):
        payload = OrderDetailSerializer(make_order()).data
        self.assertEqual(payload['customer_name'], 'Asha')
        self.assertEqual(payload['customer_email'], 'asha@example.com')


class CheckoutSerializerTests(SimpleTestCase):
    """Only Cash on Delivery is accepted, and the address must be usable."""

    def _payload(self, **overrides):
        data = {'shipping_address': '12 Marine Drive, Mumbai 400001',
                'city': 'Mumbai', 'state': 'MH', 'postal_code': '400001',
                'payment_method': 'COD'}
        data.update(overrides)
        return data

    def test_valid_cod_payload(self):
        serializer = CheckoutRequestSerializer(data=self._payload())
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data['payment_method'], 'COD')

    def test_cash_on_delivery_spelling_is_accepted(self):
        serializer = CheckoutRequestSerializer(
            data=self._payload(payment_method='CASH ON DELIVERY'))
        self.assertTrue(serializer.is_valid())

    def test_online_payment_is_rejected_with_notice(self):
        serializer = CheckoutRequestSerializer(data=self._payload(payment_method='UPI'))
        self.assertFalse(serializer.is_valid())
        self.assertIn('payment_method', serializer.errors)

    def test_short_address_is_rejected(self):
        serializer = CheckoutRequestSerializer(data=self._payload(shipping_address='abc'))
        self.assertFalse(serializer.is_valid())

    def test_blank_address_is_rejected(self):
        serializer = CheckoutRequestSerializer(data=self._payload(shipping_address=''))
        self.assertFalse(serializer.is_valid())


class CheckoutPaymentMappingTests(SimpleTestCase):
    """The stored value matches the vocabulary the table already uses."""

    def test_cod_maps_to_the_stored_label(self):
        self.assertEqual(
            OrderCreationService._resolve_payment_method({'payment_method': 'COD'}),
            'Cash on Delivery',
        )

    def test_any_other_method_is_refused(self):
        with self.assertRaises(ValidationError):
            OrderCreationService._resolve_payment_method({'payment_method': 'UPI'})


class OrderQueryServiceTests(SimpleTestCase):
    """Reads are scoped to the requesting customer inside the query."""

    def test_get_customer_order_filters_on_customer_and_id(self):
        customer = Customer(customer_id='U100010')
        order = make_order()
        queryset = MagicMockQuerySet(first_value=order)
        with patch('orders.services.OrderQueryService._base_queryset',
                   return_value=queryset):
            found = OrderQueryService.get_customer_order(customer, 'ORD0000042')
        self.assertIs(found, order)
        self.assertEqual(queryset.last_kwargs,
                         {'customer': customer, 'order_id': 'ORD0000042'})

    def test_foreign_order_id_is_simply_not_found(self):
        queryset = MagicMockQuerySet(first_value=None)
        with patch('orders.services.OrderQueryService._base_queryset',
                   return_value=queryset):
            with self.assertRaises(NotFound):
                OrderQueryService.get_customer_order(
                    Customer(customer_id='U1'), 'ORD9999999')

    def test_blank_order_id_is_rejected_before_the_query(self):
        with self.assertRaises(NotFound):
            OrderQueryService.get_customer_order(Customer(customer_id='U1'), '  ')

    def test_return_request_needs_a_returns_table(self):
        queryset = MagicMockQuerySet(first_value=make_order())
        with patch('orders.services.OrderQueryService._base_queryset',
                   return_value=queryset):
            with self.assertRaises(ValidationError):
                CustomerReturnService.request_return(
                    Customer(customer_id='U100010'), 'ORD0000042',
                    'ORD0000042', 'Wrong size')


class MagicMockQuerySet:
    """Tiny stand-in that records the filter used by the service."""

    def __init__(self, first_value=None):
        self.first_value = first_value
        self.last_kwargs = None

    def filter(self, **kwargs):
        self.last_kwargs = kwargs
        return self

    def first(self):
        return self.first_value

    def order_by(self, *args):
        return self

    def __iter__(self):
        return iter([])


class OrdersViewTests(SimpleTestCase):
    """View contracts: list, detail, checkout, and failure handling."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.customer = Customer(customer_id='U100010', email='a@example.com')
        self.user = SimpleNamespace(
            role=Role.CUSTOMER, profile=self.customer, auth_user_id='U100010',
            is_authenticated=True, is_active=True,
        )

    def _get(self, request, user=None):
        force_authenticate(request, user=user or self.user)
        return request

    def test_orders_list_requires_authentication(self):
        request = self.factory.get('/api/orders/')
        response = CustomerOrdersListView.as_view()(request)
        self.assertEqual(response.status_code, 401)

    def test_orders_list_returns_only_the_customers_orders(self):
        request = self._get(self.factory.get('/api/orders/'))
        with patch('orders.views.OrderQueryService.get_customer_orders',
                   return_value=[make_order()]) as mock_list:
            response = CustomerOrdersListView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(mock_list.call_args[0][0], self.customer)
        self.assertEqual(response.data['results'][0]['order_id'], 'ORD0000042')

    def test_order_detail_is_customer_scoped(self):
        request = self._get(self.factory.get('/api/orders/ORD0000042/'))
        with patch('orders.views.OrderQueryService.get_customer_order',
                   return_value=make_order()) as mock_get:
            response = OrderDetailView.as_view()(request, order_id='ORD0000042')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock_get.call_args[0][0], self.customer)

    def test_someone_elses_order_is_404(self):
        request = self._get(self.factory.get('/api/orders/ORD9999999/'))
        with patch('orders.views.OrderQueryService.get_customer_order',
                   side_effect=NotFound('Order not found.')):
            response = OrderDetailView.as_view()(request, order_id='ORD9999999')
        self.assertEqual(response.status_code, 404)

    def test_checkout_returns_the_placed_order(self):
        request = self._get(self.factory.post(
            '/api/orders/checkout/',
            {'shipping_address': '12 Marine Drive, Mumbai 400001', 'payment_method': 'COD'},
            format='json'))
        with patch('orders.views.OrderCreationService.create_orders_from_cart',
                   return_value=[make_order()]):
            response = CheckoutView.as_view()(request)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['order']['order_id'], 'ORD0000042')
        self.assertEqual(response.data['order_count'], 1)

    def test_checkout_rejects_an_invalid_payment_method(self):
        request = self._get(self.factory.post(
            '/api/orders/checkout/',
            {'shipping_address': '12 Marine Drive, Mumbai 400001', 'payment_method': 'UPI'},
            format='json'))
        response = CheckoutView.as_view()(request)
        self.assertEqual(response.status_code, 400)

    def test_database_failure_is_reported_generically(self):
        request = self._get(self.factory.get('/api/orders/'))
        with patch('orders.views.OrderQueryService.get_customer_orders',
                   side_effect=DatabaseError('secret connection string')):
            response = CustomerOrdersListView.as_view()(request)
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('secret', str(response.data))

    def test_return_route_answers_a_clear_validation_error(self):
        request = self._get(self.factory.post(
            '/api/orders/ORD0000042/return/',
            {'order_item_id': 'ORD0000042', 'return_reason': 'Wrong size'},
            format='json'))
        with patch('orders.views.CustomerReturnService.request_return',
                   side_effect=ValidationError('not available')):
            response = CustomerOrderReturnView.as_view()(request, order_id='ORD0000042')
        self.assertEqual(response.status_code, 400)
