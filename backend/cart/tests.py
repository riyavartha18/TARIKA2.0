from unittest.mock import MagicMock, patch
from types import SimpleNamespace

from django.test import SimpleTestCase
from django.db import DatabaseError
from django.urls import reverse, resolve
from rest_framework.exceptions import PermissionDenied, ValidationError, NotFound
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import Customer, Role
from cart.models import WishlistItem, CartItem
from cart.serializers import (
    WishlistItemSerializer,
    CartItemSerializer,
    AddToWishlistSerializer,
    AddToCartSerializer,
    UpdateCartQuantitySerializer,
    build_product_payload,
)
from cart.services import (
    CartService,
    CustomerResolver,
    ServiceUnavailable,
    allocate_key,
)
from cart.views import (
    WishlistListView,
    WishlistRemoveView,
    CartView,
    CartItemDetailView,
    CartClearView,
)


def make_product(product_id='P10000', name='TARIKA Silk Kurti', stock=7,
                 discount=1099.0, actual='1,499'):
    """An unsaved Product row - enough for the pure mapping code under test."""
    from catalog.models import Product
    return Product(
        product_id=product_id,
        product_name=name,
        main_category="women's clothing",
        sub_category='kurtas',
        image='https://example.test/p.jpg',
        link='https://example.test/link',
        discount_price=discount,
        actual_price_text=actual,
        available_quantity=stock,
    )


class CartURLTests(SimpleTestCase):
    """The wishlist and cart keep their existing routes."""

    def test_wishlist_list_url_resolves(self):
        url = reverse('wishlist:wishlist-list')
        self.assertEqual(url, '/api/wishlist/')
        self.assertEqual(resolve(url).func.view_class, WishlistListView)

    def test_wishlist_remove_url_resolves(self):
        url = reverse('wishlist:wishlist-remove', kwargs={'product_id': 'P1'})
        self.assertEqual(url, '/api/wishlist/P1/')
        self.assertEqual(resolve(url).func.view_class, WishlistRemoveView)

    def test_cart_summary_url_resolves(self):
        url = reverse('cart:cart-summary')
        self.assertEqual(url, '/api/cart/')
        self.assertEqual(resolve(url).func.view_class, CartView)

    def test_cart_item_detail_url_resolves(self):
        url = reverse('cart:cart-item-detail', kwargs={'product_id': 'P1'})
        self.assertEqual(url, '/api/cart/P1/')
        self.assertEqual(resolve(url).func.view_class, CartItemDetailView)

    def test_cart_clear_url_resolves(self):
        url = reverse('cart:cart-clear')
        self.assertEqual(url, '/api/cart/clear/')
        self.assertEqual(resolve(url).func.view_class, CartClearView)


class ProductPayloadTests(SimpleTestCase):
    """The flat product summary the customer cards render."""

    def test_payload_maps_the_real_product_columns(self):
        payload = build_product_payload(make_product())
        self.assertEqual(payload['product_id'], 'P10000')
        self.assertEqual(payload['product_name'], 'TARIKA Silk Kurti')
        self.assertEqual(payload['category_name'], "women's clothing")
        self.assertEqual(payload['category_id'], "women's-clothing")
        self.assertEqual(payload['primary_image'], 'https://example.test/p.jpg')
        # selling_price is discount_price, base_price is the parsed TEXT column.
        self.assertEqual(payload['selling_price'], 1099.0)
        self.assertEqual(payload['base_price'], 1499.0)
        self.assertEqual(payload['total_stock'], 7)
        self.assertTrue(payload['in_stock'])

    def test_missing_product_yields_blanks_instead_of_raising(self):
        payload = build_product_payload(None)
        self.assertIsNone(payload['product_id'])
        self.assertEqual(payload['selling_price'], 0)
        self.assertFalse(payload['in_stock'])

    def test_unrecorded_stock_is_not_reported_as_sold_out(self):
        payload = build_product_payload(make_product(stock=None))
        self.assertIsNone(payload['available_stock'])
        self.assertEqual(payload['total_stock'], 0)
        self.assertTrue(payload['in_stock'])


class CartSerializerTests(SimpleTestCase):
    """Line items expose id, prices and totals derived from the row."""

    def test_cart_line_totals(self):
        item = CartItem(cartkey='CART0000001', quantity=3)
        item.product = make_product(stock=10)
        data = CartItemSerializer(item).data

        self.assertEqual(data['id'], 'CART0000001')
        self.assertEqual(data['cartkey'], 'CART0000001')
        self.assertEqual(data['product_id'], 'P10000')
        self.assertEqual(data['unit_price'], 1099.0)
        self.assertEqual(data['line_total'], 3297.0)
        self.assertTrue(data['is_stock_available'])
        # Nested copy kept for the bag page grouping.
        self.assertEqual(data['product']['category_name'], "women's clothing")

    def test_cart_line_flags_quantity_above_stock(self):
        item = CartItem(cartkey='CART0000002', quantity=9)
        item.product = make_product(stock=4)
        data = CartItemSerializer(item).data
        self.assertFalse(data['is_stock_available'])

    def test_wishlist_line_carries_wishkey_as_id(self):
        entry = WishlistItem(wishkey='WISH0000007')
        entry.product = make_product()
        data = WishlistItemSerializer(entry).data
        self.assertEqual(data['id'], 'WISH0000007')
        self.assertEqual(data['product_id'], 'P10000')
        self.assertEqual(data['product_name'], 'TARIKA Silk Kurti')

    def test_quantity_input_rejects_non_positive_values(self):
        for value in (0, -1, 'abc', 10 ** 6):
            serializer = UpdateCartQuantitySerializer(data={'quantity': value})
            self.assertFalse(serializer.is_valid(), f'{value} should be rejected')

    def test_quantity_input_accepts_a_whole_number(self):
        serializer = UpdateCartQuantitySerializer(data={'quantity': 4})
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data['quantity'], 4)

    def test_product_id_must_exist(self):
        with patch('cart.serializers.Product.objects.filter') as mock_filter:
            mock_filter.return_value.exists.return_value = False
            self.assertFalse(AddToWishlistSerializer(data={'product_id': 'P404'}).is_valid())
            self.assertFalse(
                AddToCartSerializer(data={'product_id': 'P404', 'quantity': 1}).is_valid()
            )

    def test_blank_product_id_is_rejected(self):
        serializer = AddToWishlistSerializer(data={'product_id': '   '})
        self.assertFalse(serializer.is_valid())


class CustomerResolverTests(SimpleTestCase):
    """The customer is taken from the verified session, never from the request."""

    def test_profile_instance_is_used_directly(self):
        customer = Customer(customer_id='U100010', email='a@example.com')
        user = SimpleNamespace(role=Role.CUSTOMER, profile=customer, auth_user_id='ignored')
        self.assertIs(CustomerResolver.get_customer_for_user(user), customer)

    def test_non_customer_role_is_refused(self):
        user = SimpleNamespace(role=Role.ADMIN, profile=None, auth_user_id='7')
        with self.assertRaises(PermissionDenied):
            CustomerResolver.get_customer_for_user(user)

    def test_identity_without_a_customer_row_is_refused(self):
        user = SimpleNamespace(role=Role.CUSTOMER, profile=None, auth_user_id='U999999')
        with patch('cart.services.Customer.objects.filter') as mock_filter:
            mock_filter.return_value.first.return_value = None
            with self.assertRaises(PermissionDenied):
                CustomerResolver.get_customer_for_user(user)

    def test_missing_identity_is_refused(self):
        user = SimpleNamespace(role=Role.CUSTOMER, profile=None, auth_user_id=None)
        with self.assertRaises(PermissionDenied):
            CustomerResolver.get_customer_for_user(user)

    def test_database_error_is_reported_without_details(self):
        user = SimpleNamespace(role=Role.CUSTOMER, profile=None, auth_user_id='U1')
        with patch('cart.services.Customer.objects.filter',
                   side_effect=DatabaseError('secret sql text')):
            with self.assertRaises(ServiceUnavailable):
                CustomerResolver.get_customer_for_user(user)


class KeyAllocationTests(SimpleTestCase):
    """wishkey / cartkey / orderid continue the existing sequential format."""

    def test_next_key_is_padded_and_prefixed(self):
        cases = [('wishlist', 306213, 'WISH0306214'),
                 ('cart', 165557, 'CART0165558'),
                 ('orders', 1000000, 'ORD1000001')]
        for table, current_max, expected in cases:
            cursor = MagicMock()
            # One fetchone per allocation: the advisory lock only executes.
            cursor.fetchone.return_value = (current_max + 1,)
            conn = MagicMock()
            conn.cursor.return_value.__enter__.return_value = cursor
            with patch('cart.services.connection', conn):
                self.assertEqual(allocate_key(table), expected)

    def test_empty_table_starts_at_one(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = (1,)
        conn = MagicMock()
        conn.cursor.return_value.__enter__.return_value = cursor
        with patch('cart.services.connection', conn):
            self.assertEqual(allocate_key('wishlist'), 'WISH0000001')


class CartStockGuardTests(SimpleTestCase):
    """Quantities are validated against the product row's own stock."""

    def test_available_stock_reads_the_real_column(self):
        self.assertEqual(CartService.get_available_stock(make_product(stock=4.0)), 4)
        self.assertIsNone(CartService.get_available_stock(make_product(stock=None)))

    def test_quantity_above_stock_is_rejected(self):
        with self.assertRaises(ValidationError):
            CartService._guard_quantity(make_product(stock=2), 5, current_in_cart=2)

    def test_unrecorded_stock_is_not_blocked(self):
        CartService._guard_quantity(make_product(stock=None), 40, current_in_cart=0)

    def test_absolute_line_cap_is_enforced(self):
        with self.assertRaises(ValidationError):
            CartService._guard_quantity(make_product(stock=10000), 100, 0)

    def test_missing_product_is_a_404_not_a_500(self):
        with patch('cart.services.Product.objects.filter') as mock_filter:
            mock_filter.return_value.first.return_value = None
            with self.assertRaises(NotFound):
                CartService.add_to_cart(
                    Customer(customer_id='U1'), 'P404', 1
                )

    def test_out_of_stock_product_cannot_be_added(self):
        with patch('cart.services.Product.objects.filter') as mock_filter:
            mock_filter.return_value.first.return_value = make_product(stock=0)
            with self.assertRaises(ValidationError):
                CartService.add_to_cart(Customer(customer_id='U1'), 'P10000', 1)


class CartSummaryTests(SimpleTestCase):
    """Subtotal and totals are recalculated from the stored rows."""

    def _item(self, cartkey, quantity, price):
        item = CartItem(cartkey=cartkey, quantity=quantity)
        item.product = make_product(product_id=cartkey, discount=price, stock=50)
        return item

    def test_summary_totals(self):
        items = [self._item('CART0000001', 2, 500.0), self._item('CART0000002', 1, 250.0)]
        with patch.object(CartService, 'get_customer_cart_items', return_value=items):
            summary = CartService.get_cart_summary(Customer(customer_id='U1'))

        self.assertEqual(summary['total_items'], 3)
        self.assertEqual(summary['subtotal'], 1250.0)
        self.assertEqual(summary['total'], 1250.0)
        self.assertEqual(len(summary['items']), 2)
        self.assertEqual(summary['items'][0]['line_total'], 1000.0)


class CartViewTests(SimpleTestCase):
    """Response shapes the frontend consumes, plus permission behaviour."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.customer = Customer(customer_id='U100010', email='a@example.com')
        self.user = SimpleNamespace(
            role=Role.CUSTOMER, profile=self.customer, auth_user_id='U100010',
            is_authenticated=True, is_active=True,
        )

    def _item_payload(self):
        item = CartItem(cartkey='CART0000001', quantity=1)
        item.product = make_product()
        return CartItemSerializer(item).data

    def test_unauthenticated_request_denied(self):
        request = self.factory.get('/api/cart/')
        response = CartView.as_view()(request)
        self.assertEqual(response.status_code, 401)

    def test_non_customer_role_denied(self):
        request = self.factory.get('/api/cart/')
        force_authenticate(request, user=SimpleNamespace(
            role=Role.ADMIN, profile=None, auth_user_id='7',
            is_authenticated=True, is_active=True,
        ))
        response = CartView.as_view()(request)
        self.assertEqual(response.status_code, 403)

    def test_cart_get_returns_items_and_totals(self):
        summary = {'items': [self._item_payload()], 'total_items': 1,
                   'subtotal': 1099.0, 'total': 1099.0}
        request = self.factory.get('/api/cart/')
        force_authenticate(request, user=self.user)
        with patch('cart.views.CartService.get_cart_summary', return_value=summary):
            response = CartView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['total_items'], 1)

    def test_cart_post_returns_cart_summary(self):
        item = CartItem(cartkey='CART0000009', quantity=1)
        item.product = make_product()
        summary = {'items': [], 'total_items': 1, 'subtotal': 1099.0, 'total': 1099.0}
        request = self.factory.post('/api/cart/', {'product_id': 'P10000', 'quantity': 1},
                                    format='json')
        force_authenticate(request, user=self.user)
        with patch('cart.serializers.Product.objects.filter') as mock_filter, \
             patch('cart.views.CartService.add_to_cart', return_value=(item, True)), \
             patch('cart.views.CartService.get_cart_summary', return_value=summary):
            mock_filter.return_value.exists.return_value = True
            response = CartView.as_view()(request)

        self.assertEqual(response.status_code, 201)
        # The context reads `cart`, not only `summary`.
        self.assertEqual(response.data['cart'], summary)
        self.assertTrue(response.data['created'])

    def test_cart_post_increment_reports_not_created(self):
        item = CartItem(cartkey='CART0000009', quantity=2)
        item.product = make_product()
        request = self.factory.post('/api/cart/', {'product_id': 'P10000'}, format='json')
        force_authenticate(request, user=self.user)
        with patch('cart.serializers.Product.objects.filter') as mock_filter, \
             patch('cart.views.CartService.add_to_cart', return_value=(item, False)), \
             patch('cart.views.CartService.get_cart_summary',
                   return_value={'items': [], 'total_items': 2, 'subtotal': 0, 'total': 0}):
            mock_filter.return_value.exists.return_value = True
            response = CartView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['created'])

    def test_invalid_product_id_returns_400(self):
        request = self.factory.post('/api/cart/', {'product_id': 'P404'}, format='json')
        force_authenticate(request, user=self.user)
        with patch('cart.serializers.Product.objects.filter') as mock_filter:
            mock_filter.return_value.exists.return_value = False
            response = CartView.as_view()(request)
        self.assertEqual(response.status_code, 400)

    def test_database_failure_returns_generic_503(self):
        request = self.factory.get('/api/cart/')
        force_authenticate(request, user=self.user)
        with patch('cart.views.CartService.get_cart_summary',
                   side_effect=DatabaseError('connection refused; secret')):
            response = CartView.as_view()(request)
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('secret', str(response.data))

    def test_wishlist_post_reports_duplicate_flag(self):
        entry = WishlistItem(wishkey='WISH0000001')
        entry.product = make_product()
        request = self.factory.post('/api/wishlist/', {'product_id': 'P10000'}, format='json')
        force_authenticate(request, user=self.user)
        with patch('cart.serializers.Product.objects.filter') as mock_filter, \
             patch('cart.views.WishlistService.add_to_wishlist', return_value=(entry, False)):
            mock_filter.return_value.exists.return_value = True
            response = WishlistListView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['already_in_wishlist'])
        self.assertEqual(response.data['item']['id'], 'WISH0000001')

    def test_wishlist_remove_missing_row_is_404(self):
        request = self.factory.delete('/api/wishlist/P10000/')
        force_authenticate(request, user=self.user)
        with patch('cart.views.WishlistService.remove_from_wishlist', return_value=False):
            response = WishlistRemoveView.as_view()(request, product_id='P10000')
        self.assertEqual(response.status_code, 404)

    def test_wishlist_list_is_scoped_to_the_session_customer(self):
        request = self.factory.get('/api/wishlist/')
        force_authenticate(request, user=self.user)
        with patch('cart.views.WishlistService.get_customer_wishlist',
                   return_value=[]) as mock_get:
            response = WishlistListView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        # The service received the customer from the token, not from the request.
        self.assertEqual(mock_get.call_args[0][0], self.customer)

    def test_quantity_update_returns_fresh_cart(self):
        item = CartItem(cartkey='CART0000001', quantity=4)
        item.product = make_product(stock=50)
        summary = {'items': [], 'total_items': 4, 'subtotal': 4396.0, 'total': 4396.0}
        request = self.factory.patch('/api/cart/P10000/', {'quantity': 4}, format='json')
        force_authenticate(request, user=self.user)
        with patch('cart.views.CartService.update_cart_quantity', return_value=item), \
             patch('cart.views.CartService.get_cart_summary', return_value=summary):
            response = CartItemDetailView.as_view()(request, product_id='P10000')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['cart'], summary)

    def test_remove_line_returns_fresh_cart(self):
        summary = {'items': [], 'total_items': 0, 'subtotal': 0, 'total': 0}
        request = self.factory.delete('/api/cart/P10000/')
        force_authenticate(request, user=self.user)
        with patch('cart.views.CartService.remove_from_cart', return_value=True), \
             patch('cart.views.CartService.get_cart_summary', return_value=summary):
            response = CartItemDetailView.as_view()(request, product_id='P10000')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['cart']['total_items'], 0)

    def test_clear_cart_resets_totals(self):
        request = self.factory.delete('/api/cart/clear/')
        force_authenticate(request, user=self.user)
        with patch('cart.views.CartService.clear_cart', return_value=None):
            response = CartClearView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['total_items'], 0)
