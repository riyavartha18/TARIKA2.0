from unittest.mock import MagicMock, patch
from django.test import SimpleTestCase
from django.urls import reverse, resolve
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework.exceptions import ValidationError, NotFound, PermissionDenied
from rest_framework import status

from accounts.models import Role, Customer, Warehouse
from accounts.authentication import AuthenticatedUser
from catalog.models import Product, Inventory, OrderItem
from cart.models import CartItem
from orders.models import Order, Payment
from orders.serializers import CheckoutRequestSerializer, OrderDetailSerializer
from orders.services import (
    WarehouseAllocationService,
    StockVerificationService,
    OrderCreationService,
    OrderQueryService
)
from orders.views import CheckoutView, OrderDetailView, CustomerOrdersListView


class OrdersURLTests(SimpleTestCase):
    """Test URL routing for Orders & Checkout endpoints."""

    def test_checkout_url_resolves(self):
        url = reverse('orders:checkout')
        self.assertEqual(url, '/api/orders/checkout/')
        self.assertEqual(resolve(url).func.view_class, CheckoutView)

    def test_order_detail_url_resolves(self):
        url = reverse('orders:order-detail', kwargs={'order_id': 'ord-123'})
        self.assertEqual(url, '/api/orders/ord-123/')
        self.assertEqual(resolve(url).func.view_class, OrderDetailView)

    def test_order_list_url_resolves(self):
        url = reverse('orders:order-list')
        self.assertEqual(url, '/api/orders/')
        self.assertEqual(resolve(url).func.view_class, CustomerOrdersListView)


class CheckoutSerializerTests(SimpleTestCase):
    """Test CheckoutRequestSerializer validation rules and payment method normalization."""

    def test_valid_checkout_payload_cod(self):
        data = {
            'shipping_address': 'Flat 402, Royale Palms, MG Road',
            'city': 'Mumbai',
            'state': 'Maharashtra',
            'postal_code': '400001',
            'payment_method': 'COD'
        }
        serializer = CheckoutRequestSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data['payment_method'], 'COD')

    def test_online_payment_rejected_with_notice(self):
        data = {
            'shipping_address': 'Flat 402, Royale Palms, MG Road',
            'city': 'Mumbai',
            'state': 'Maharashtra',
            'postal_code': '400001',
            'payment_method': 'Online Payment'
        }
        serializer = CheckoutRequestSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('payment_method', serializer.errors)
        self.assertIn("Online payment is launching soon", str(serializer.errors['payment_method']))

    def test_empty_address_fails(self):
        data = {
            'shipping_address': '   ',
            'payment_method': 'COD'
        }
        serializer = CheckoutRequestSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('shipping_address', serializer.errors)

    def test_invalid_payment_method_fails(self):
        data = {
            'shipping_address': 'Valid Address, Road 12',
            'payment_method': 'Crypto'
        }
        serializer = CheckoutRequestSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('payment_method', serializer.errors)


class OrdersServiceTests(SimpleTestCase):
    """Test OrderCreationService, StockVerificationService, and WarehouseAllocationService."""

    def setUp(self):
        self.customer = Customer(
            customer_id='cust-001',
            full_name='Riya Vartha',
            email='riya@tarika.com'
        )
        self.warehouse_a = Warehouse(
            warehouse_id='wh-west',
            warehouse_name='West Zone Fulfillment Center'
        )
        self.warehouse_b = Warehouse(
            warehouse_id='wh-north',
            warehouse_name='North Zone Fulfillment Center'
        )
        self.product_1 = Product(
            product_id='prod-101',
            product_name='Silk Embroidered Kurti',
            selling_price=4500,
            is_active=True
        )
        self.product_2 = Product(
            product_id='prod-102',
            product_name='Tailored Linen Trousers',
            selling_price=3200,
            is_active=True
        )

    @patch('orders.services.CartItem.objects.filter')
    def test_empty_cart_raises_validation_error(self, mock_cart_filter):
        mock_cart_filter.return_value.select_related.return_value = []
        with self.assertRaises(ValidationError) as ctx:
            OrderCreationService.create_order_from_cart(
                customer=self.customer,
                checkout_data={'shipping_address': '123 Fashion Street', 'payment_method': 'COD'}
            )
        self.assertIn("empty", str(ctx.exception).lower())

    @patch('orders.services.CartService.get_available_stock')
    def test_insufficient_stock_raises_validation_error(self, mock_stock):
        cart_item = CartItem(
            id=1,
            customer=self.customer,
            product=self.product_1,
            quantity=5
        )
        mock_stock.return_value = 2  # Only 2 available in total

        with self.assertRaises(ValidationError) as ctx:
            StockVerificationService.verify_stock([cart_item])
        self.assertIn("insufficient stock", str(ctx.exception).lower())

    @patch('orders.services.Warehouse.objects.all')
    @patch('orders.services.Inventory.objects.filter')
    def test_warehouse_allocation_fails_if_no_single_warehouse_can_fulfill_all_items(
        self,
        mock_inv_filter,
        mock_wh_all
    ):
        mock_wh_all.return_value = [self.warehouse_a, self.warehouse_b]
        cart_items = [
            CartItem(id=1, customer=self.customer, product=self.product_1, quantity=3),
            CartItem(id=2, customer=self.customer, product=self.product_2, quantity=2),
        ]

        def inventory_side_effect(warehouse, product):
            mock_obj = MagicMock()
            if warehouse == self.warehouse_a and product == self.product_1:
                mock_obj.first.return_value = Inventory(stock_quantity=5)
            elif warehouse == self.warehouse_b and product == self.product_2:
                mock_obj.first.return_value = Inventory(stock_quantity=5)
            else:
                mock_obj.first.return_value = Inventory(stock_quantity=0)
            return mock_obj

        mock_inv_filter.side_effect = inventory_side_effect

        with self.assertRaises(ValidationError) as ctx:
            WarehouseAllocationService.allocate_warehouse(cart_items)
        self.assertIn("fulfillment centers currently has sufficient stock", str(ctx.exception))

    @patch('orders.services.transaction.atomic')
    @patch('orders.services.CartService.clear_cart')
    @patch('orders.services.Payment.objects.create')
    @patch('orders.services.OrderItem.objects.create')
    @patch('orders.services.Order.objects.create')
    @patch('orders.services.WarehouseAllocationService.allocate_warehouse')
    @patch('orders.services.StockVerificationService.verify_stock')
    @patch('orders.services.CartItem.objects.filter')
    @patch('orders.services.get_dim_product_selling_price_map', return_value={'prod-101': 4700})
    def test_successful_order_creation_and_cart_clearing(
        self,
        mock_price_map,
        mock_cart_filter,
        mock_verify_stock,
        mock_allocate_wh,
        mock_order_create,
        mock_item_create,
        mock_payment_create,
        mock_clear_cart,
        mock_atomic
    ):
        mock_atomic.return_value.__enter__.return_value = None
        mock_atomic.return_value.__exit__.return_value = None

        cart_item = CartItem(
            id=1,
            customer=self.customer,
            product=self.product_1,
            quantity=2
        )
        mock_cart_filter.return_value.select_related.return_value = [cart_item]
        mock_allocate_wh.return_value = self.warehouse_a

        fake_order = Order(
            order_id='ord-test-uuid',
            customer=self.customer,
            warehouse=self.warehouse_a,
            total_amount=9400.0,
            order_status='confirmed',
            payment_status='unpaid'
        )
        mock_order_create.return_value = fake_order

        order = OrderCreationService.create_order_from_cart(
            customer=self.customer,
            checkout_data={
                'shipping_address': '221B Baker Street',
                'city': 'Mumbai',
                'state': 'Maharashtra',
                'postal_code': '400001',
                'payment_method': 'COD'
            }
        )

        self.assertEqual(order.order_id, 'ord-test-uuid')
        self.assertEqual(order.total_amount, 9400.0)
        mock_item_create.assert_called_once()
        self.assertEqual(mock_item_create.call_args.kwargs['unit_price'], 4700)
        mock_price_map.assert_called_once()
        self.assertEqual(list(mock_price_map.call_args.args[0]), ['prod-101'])
        mock_payment_create.assert_called_once()
        mock_clear_cart.assert_called_once_with(self.customer)

    @patch('orders.services.Order.objects.select_related')
    def test_cross_customer_order_access_denied(self, mock_select_related):
        other_customer = Customer(customer_id='cust-other')
        fake_order = Order(
            order_id='ord-secret',
            customer=other_customer
        )
        mock_select_related.return_value.prefetch_related.return_value.get.return_value = fake_order

        with self.assertRaises(PermissionDenied):
            OrderQueryService.get_customer_order(self.customer, 'ord-secret')


class OrdersViewTests(SimpleTestCase):
    """Test API views with authentication and permissions."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.customer = Customer(
            customer_id='cust-view-1',
            full_name='Test Customer',
            email='test@tarika.com'
        )
        self.user = AuthenticatedUser(
            auth_user_id='auth-view-1',
            email='test@tarika.com',
            role=Role.CUSTOMER,
            profile=self.customer
        )

    @patch('orders.views.OrderDetailSerializer')
    @patch('orders.views.OrderCreationService.create_order_from_cart')
    @patch('orders.views.CustomerResolver.get_customer_for_user')
    def test_checkout_view_success(self, mock_resolver, mock_create, mock_serializer):
        mock_resolver.return_value = self.customer
        mock_create.return_value = MagicMock(order_id='ord-new-123')
        mock_serializer.return_value.data = {'order_id': 'ord-new-123', 'total_amount': 5000}

        payload = {
            'shipping_address': 'Flat 101, Lotus Enclave, Link Road',
            'city': 'Delhi',
            'state': 'Delhi',
            'postal_code': '110001',
            'payment_method': 'COD'
        }
        request = self.factory.post('/api/orders/checkout/', payload, format='json')
        force_authenticate(request, user=self.user)

        view = CheckoutView.as_view()
        response = view(request)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['order']['order_id'], 'ord-new-123')

    @patch('orders.views.OrderDetailSerializer')
    @patch('orders.views.OrderQueryService.get_customer_order')
    @patch('orders.views.CustomerResolver.get_customer_for_user')
    def test_order_detail_view_success(self, mock_resolver, mock_get_order, mock_serializer):
        mock_resolver.return_value = self.customer
        fake_order = MagicMock(order_id='ord-new-123')
        mock_get_order.return_value = fake_order
        mock_serializer.return_value.data = {'order_id': 'ord-new-123', 'order_status': 'confirmed'}

        request = self.factory.get('/api/orders/ord-new-123/')
        force_authenticate(request, user=self.user)

        view = OrderDetailView.as_view()
        response = view(request, order_id='ord-new-123')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['order_id'], 'ord-new-123')
