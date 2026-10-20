from unittest.mock import MagicMock, patch
from django.test import SimpleTestCase
from django.urls import reverse, resolve
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework.exceptions import ValidationError, NotFound

from accounts.models import Role, Customer
from accounts.authentication import AuthenticatedUser
from catalog.models import Category, Product
from cart.models import WishlistItem, CartItem
from cart.serializers import (
    WishlistItemSerializer,
    AddToWishlistSerializer,
    CartItemSerializer,
    AddToCartSerializer,
    UpdateCartQuantitySerializer
)
from cart.services import WishlistService, CartService, CustomerResolver
from cart.views import (
    WishlistListView,
    WishlistRemoveView,
    CartView,
    CartItemDetailView,
    CartClearView
)


class CartURLTests(SimpleTestCase):
    """Test URL routing for Wishlist and Cart/Bag endpoints."""

    def test_wishlist_list_url_resolves(self):
        url = reverse('wishlist:wishlist-list')
        self.assertEqual(url, '/api/wishlist/')
        self.assertEqual(resolve(url).func.view_class, WishlistListView)

    def test_wishlist_remove_url_resolves(self):
        url = reverse('wishlist:wishlist-remove', kwargs={'product_id': 'prod-1'})
        self.assertEqual(url, '/api/wishlist/prod-1/')
        self.assertEqual(resolve(url).func.view_class, WishlistRemoveView)

    def test_cart_summary_url_resolves(self):
        url = reverse('cart:cart-summary')
        self.assertEqual(url, '/api/cart/')
        self.assertEqual(resolve(url).func.view_class, CartView)

    def test_cart_item_detail_url_resolves(self):
        url = reverse('cart:cart-item-detail', kwargs={'product_id': 'prod-1'})
        self.assertEqual(url, '/api/cart/prod-1/')
        self.assertEqual(resolve(url).func.view_class, CartItemDetailView)

    def test_cart_clear_url_resolves(self):
        url = reverse('cart:cart-clear')
        self.assertEqual(url, '/api/cart/clear/')
        self.assertEqual(resolve(url).func.view_class, CartClearView)


class WishlistAndCartSerializerTests(SimpleTestCase):
    """Test serializer validation, line totals, and stock calculations."""

    @patch('cart.serializers.get_dim_product_selling_price_map', return_value={'p-1': 2700})
    def test_cart_item_line_total_uses_dimension_price(self, mock_price_map):
        product = Product(
            product_id='p-1',
            product_name='Designer Gown',
            selling_price=2500,
            is_active=True
        )
        product._available_stock_cached = 10
        item = CartItem(id=1, product=product, quantity=3)

        serializer = CartItemSerializer(item)
        data = serializer.data

        self.assertEqual(data['product']['selling_price'], 2700)
        self.assertEqual(data['unit_price'], 2700)
        self.assertEqual(data['line_total'], 8100)
        self.assertEqual(data['quantity'], 3)
        self.assertTrue(data['is_stock_available'])
        mock_price_map.assert_called_once_with(['p-1'])

    @patch('cart.serializers.Product.objects.get')
    def test_add_to_wishlist_serializer_validation(self, mock_get):
        mock_get.return_value = Product(product_id='p-1', is_active=True)
        serializer = AddToWishlistSerializer(data={'product_id': 'p-1'})
        self.assertTrue(serializer.is_valid())

    @patch('cart.serializers.Product.objects.get')
    def test_add_to_wishlist_serializer_invalid_product(self, mock_get):
        mock_get.side_effect = Product.DoesNotExist()
        serializer = AddToWishlistSerializer(data={'product_id': 'non-existent'})
        self.assertFalse(serializer.is_valid())
        self.assertIn('product_id', serializer.errors)

    def test_update_cart_quantity_serializer_positive_only(self):
        serializer = UpdateCartQuantitySerializer(data={'quantity': 0})
        self.assertFalse(serializer.is_valid())
        self.assertIn('quantity', serializer.errors)

        serializer_neg = UpdateCartQuantitySerializer(data={'quantity': -5})
        self.assertFalse(serializer_neg.is_valid())

        serializer_valid = UpdateCartQuantitySerializer(data={'quantity': 4})
        self.assertTrue(serializer_valid.is_valid())


class WishlistAndCartViewTests(SimpleTestCase):
    """Test views, customer isolation, role permissions, and service integrations."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.customer_a = Customer(
            customer_id='cust-a',
            full_name='Riya Customer A',
            email='customer_a@tarika.com',
            is_active=True
        )
        self.customer_b = Customer(
            customer_id='cust-b',
            full_name='Customer B',
            email='customer_b@tarika.com',
            is_active=True
        )
        self.user_a = AuthenticatedUser(
            auth_user_id='auth-a',
            email='customer_a@tarika.com',
            role=Role.CUSTOMER,
            profile=self.customer_a
        )
        self.user_b = AuthenticatedUser(
            auth_user_id='auth-b',
            email='customer_b@tarika.com',
            role=Role.CUSTOMER,
            profile=self.customer_b
        )
        self.admin_user = AuthenticatedUser(
            auth_user_id='auth-admin',
            email='admin@tarika.com',
            role=Role.ADMIN
        )

    # ---------------- Wishlist Tests ---------------- #

    @patch('cart.services.WishlistService.get_customer_wishlist')
    def test_wishlist_list_view_authenticated(self, mock_get_wl):
        prod = Product(product_id='p-1', product_name='Silk Dress', selling_price=1999)
        prod._total_stock_cached = 5
        mock_item = WishlistItem(id=1, customer=self.customer_a, product=prod)
        mock_get_wl.return_value = [mock_item]

        request = self.factory.get('/api/wishlist/')
        force_authenticate(request, user=self.user_a)

        view = WishlistListView.as_view()
        response = view(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['product_id'], 'p-1')
        mock_get_wl.assert_called_once_with(self.customer_a)

    @patch('cart.services.WishlistService.add_to_wishlist')
    @patch('cart.serializers.Product.objects.get')
    def test_wishlist_add_new_product(self, mock_prod_get, mock_add):
        mock_prod_get.return_value = Product(product_id='p-1', is_active=True)
        prod = Product(product_id='p-1', product_name='Silk Dress', selling_price=1999)
        prod._total_stock_cached = 5
        mock_item = WishlistItem(id=1, customer=self.customer_a, product=prod)
        mock_add.return_value = (mock_item, True)

        request = self.factory.post('/api/wishlist/', {'product_id': 'p-1'}, format='json')
        force_authenticate(request, user=self.user_a)

        view = WishlistListView.as_view()
        response = view(request)

        self.assertEqual(response.status_code, 201)
        self.assertFalse(response.data['already_in_wishlist'])
        self.assertEqual(response.data['item']['product_id'], 'p-1')

    @patch('cart.services.WishlistService.add_to_wishlist')
    @patch('cart.serializers.Product.objects.get')
    def test_wishlist_prevent_duplicate_items(self, mock_prod_get, mock_add):
        mock_prod_get.return_value = Product(product_id='p-1', is_active=True)
        prod = Product(product_id='p-1', product_name='Silk Dress', selling_price=1999)
        prod._total_stock_cached = 5
        mock_item = WishlistItem(id=1, customer=self.customer_a, product=prod)
        mock_add.return_value = (mock_item, False)

        request = self.factory.post('/api/wishlist/', {'product_id': 'p-1'}, format='json')
        force_authenticate(request, user=self.user_a)

        view = WishlistListView.as_view()
        response = view(request)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['already_in_wishlist'])
        self.assertIn('already in your wishlist', response.data['message'].lower())

    @patch('cart.services.WishlistService.remove_from_wishlist')
    def test_wishlist_remove_item_success(self, mock_remove):
        mock_remove.return_value = True

        request = self.factory.delete('/api/wishlist/p-1/')
        force_authenticate(request, user=self.user_a)

        view = WishlistRemoveView.as_view()
        response = view(request, product_id='p-1')

        self.assertEqual(response.status_code, 200)
        mock_remove.assert_called_once_with(self.customer_a, 'p-1')

    @patch('cart.services.WishlistService.remove_from_wishlist')
    def test_wishlist_remove_item_not_found(self, mock_remove):
        mock_remove.return_value = False

        request = self.factory.delete('/api/wishlist/p-non-existent/')
        force_authenticate(request, user=self.user_a)

        view = WishlistRemoveView.as_view()
        response = view(request, product_id='p-non-existent')

        self.assertEqual(response.status_code, 404)

    # ---------------- Bag / Cart Tests ---------------- #

    @patch('cart.services.CartService.get_cart_summary')
    def test_cart_view_summary(self, mock_summary):
        mock_summary.return_value = {
            'items': [
                {'product_id': 'p-1', 'quantity': 2, 'unit_price': 1500, 'line_total': 3000}
            ],
            'total_items': 2,
            'subtotal': 3000,
            'total': 3000
        }

        request = self.factory.get('/api/cart/')
        force_authenticate(request, user=self.user_a)

        view = CartView.as_view()
        response = view(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['total_items'], 2)
        self.assertEqual(response.data['subtotal'], 3000)
        self.assertEqual(response.data['total'], 3000)
        mock_summary.assert_called_once_with(self.customer_a)

    @patch('cart.services.CartService.get_cart_summary')
    @patch('cart.services.CartService.add_to_cart')
    @patch('cart.serializers.Product.objects.get')
    def test_cart_add_product_success(self, mock_prod_get, mock_add, mock_summary):
        mock_prod_get.return_value = Product(product_id='p-1', is_active=True)
        prod = Product(product_id='p-1', product_name='Cotton Shirt', selling_price=1200)
        prod._available_stock_cached = 15
        mock_item = CartItem(id=1, customer=self.customer_a, product=prod, quantity=2)
        mock_add.return_value = (mock_item, True)
        mock_summary.return_value = {
            'items': [],
            'total_items': 2,
            'subtotal': 2400,
            'total': 2400
        }

        request = self.factory.post('/api/cart/', {'product_id': 'p-1', 'quantity': 2}, format='json')
        force_authenticate(request, user=self.user_a)

        view = CartView.as_view()
        response = view(request)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['item']['product_id'], 'p-1')
        self.assertEqual(response.data['item']['quantity'], 2)
        mock_add.assert_called_once_with(self.customer_a, 'p-1', 2)

    @patch('cart.services.CartService.get_cart_summary')
    @patch('cart.services.CartService.update_cart_quantity')
    def test_cart_update_quantity_success(self, mock_update, mock_summary):
        prod = Product(product_id='p-1', product_name='Cotton Shirt', selling_price=1200)
        prod._available_stock_cached = 20
        mock_item = CartItem(id=1, customer=self.customer_a, product=prod, quantity=5)
        mock_update.return_value = mock_item
        mock_summary.return_value = {
            'items': [],
            'total_items': 5,
            'subtotal': 6000,
            'total': 6000
        }

        request = self.factory.patch('/api/cart/p-1/', {'quantity': 5}, format='json')
        force_authenticate(request, user=self.user_a)

        view = CartItemDetailView.as_view()
        response = view(request, product_id='p-1')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['item']['quantity'], 5)
        mock_update.assert_called_once_with(self.customer_a, 'p-1', 5)

    @patch('cart.services.CartService.get_cart_summary')
    @patch('cart.services.CartService.remove_from_cart')
    def test_cart_remove_item_success(self, mock_remove, mock_summary):
        mock_remove.return_value = True
        mock_summary.return_value = {'items': [], 'total_items': 0, 'subtotal': 0, 'total': 0}

        request = self.factory.delete('/api/cart/p-1/')
        force_authenticate(request, user=self.user_a)

        view = CartItemDetailView.as_view()
        response = view(request, product_id='p-1')

        self.assertEqual(response.status_code, 200)
        mock_remove.assert_called_once_with(self.customer_a, 'p-1')

    @patch('cart.services.CartService.clear_cart')
    def test_cart_clear_view(self, mock_clear):
        request = self.factory.delete('/api/cart/clear/')
        force_authenticate(request, user=self.user_a)

        view = CartClearView.as_view()
        response = view(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['total_items'], 0)
        self.assertEqual(response.data['subtotal'], 0)
        mock_clear.assert_called_once_with(self.customer_a)

    # ---------------- Permissions & Customer Isolation ---------------- #

    def test_unauthenticated_request_denied(self):
        request = self.factory.get('/api/wishlist/')
        view = WishlistListView.as_view()
        response = view(request)

        # Unauthenticated request returns 401
        self.assertEqual(response.status_code, 401)

    def test_non_customer_role_denied(self):
        request = self.factory.get('/api/cart/')
        force_authenticate(request, user=self.admin_user)

        view = CartView.as_view()
        response = view(request)

        self.assertEqual(response.status_code, 403)
        self.assertIn('Customer access required', response.data['detail'])

    @patch('cart.services.CartService.get_customer_cart_items')
    def test_customer_data_isolation(self, mock_get_items):
        mock_get_items.return_value = []

        # Customer B requests their cart
        request = self.factory.get('/api/cart/')
        force_authenticate(request, user=self.user_b)

        view = CartView.as_view()
        response = view(request)

        self.assertEqual(response.status_code, 200)
        # Verify query was strictly scoped to customer_b and NOT customer_a
        mock_get_items.assert_called_once_with(self.customer_b)
        self.assertNotEqual(mock_get_items.call_args[0][0].customer_id, self.customer_a.customer_id)

    # ---------------- Stock Validation Tests ---------------- #

    @patch('cart.services.CartItem.objects.filter')
    @patch('cart.services.CartService.get_available_stock')
    @patch('cart.services.Product.objects.prefetch_related')
    def test_cart_add_exceeding_stock_rejected(self, mock_prefetch, mock_stock, mock_filter):
        prod = Product(product_id='p-limited', product_name='Limited Top')
        mock_prefetch.return_value.get.return_value = prod
        mock_stock.return_value = 2  # Only 2 units in stock
        mock_filter.return_value.first.return_value = None

        # Attempt to add 3 units
        with self.assertRaises(ValidationError) as ctx:
            CartService.add_to_cart(self.customer_a, 'p-limited', quantity=3)

        self.assertIn('Only 2 available in stock', str(ctx.exception))

    @patch('cart.services.CartService.get_available_stock')
    @patch('cart.services.Product.objects.prefetch_related')
    def test_cart_add_out_of_stock_rejected(self, mock_prefetch, mock_stock):
        prod = Product(product_id='p-oos', product_name='Sold Out Coat')
        mock_prefetch.return_value.get.return_value = prod
        mock_stock.return_value = 0

        with self.assertRaises(ValidationError) as ctx:
            CartService.add_to_cart(self.customer_a, 'p-oos', quantity=1)

        self.assertIn('out of stock', str(ctx.exception).lower())

    @patch('cart.services.CartService.get_available_stock')
    @patch('cart.models.CartItem.objects.select_related')
    def test_cart_update_exceeding_stock_rejected(self, mock_select, mock_stock):
        prod = Product(product_id='p-ltd', product_name='Limited Silk Scarf')
        cart_item = CartItem(id=1, customer=self.customer_a, product=prod, quantity=1)
        mock_select.return_value.prefetch_related.return_value.get.return_value = cart_item
        mock_stock.return_value = 3

        with self.assertRaises(ValidationError) as ctx:
            CartService.update_cart_quantity(self.customer_a, 'p-ltd', quantity=5)

        self.assertIn('Only 3 available in stock', str(ctx.exception))

