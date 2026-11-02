from unittest.mock import MagicMock, patch
from django.test import SimpleTestCase
from django.urls import reverse, resolve
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework import status

from accounts.models import Customer
from wardrobe.models import WardrobeItem
from wardrobe.views import WardrobeListCreateView, WardrobeDetailView
from wardrobe.serializers import WardrobeItemSerializer

class WardrobeURLRoutingTests(SimpleTestCase):
    def test_wardrobe_list_create_url_resolves(self):
        url = reverse('wardrobe:wardrobe-list-create')
        self.assertEqual(url, '/api/wardrobe/')
        self.assertEqual(resolve(url).func.view_class, WardrobeListCreateView)

    def test_wardrobe_detail_url_resolves(self):
        url = reverse('wardrobe:wardrobe-detail', kwargs={'pk': 1})
        self.assertEqual(url, '/api/wardrobe/1/')
        self.assertEqual(resolve(url).func.view_class, WardrobeDetailView)

class WardrobeOwnershipAndAccessTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.customer1 = Customer(customer_id='cust-uuid-1', full_name='Customer One', email='c1@test.com')
        self.customer2 = Customer(customer_id='cust-uuid-2', full_name='Customer Two', email='c2@test.com')
        self.user1 = MagicMock()
        self.user1.is_authenticated = True
        self.user1.role = 'CUSTOMER'
        self.user1.profile = self.customer1

    @patch('cart.services.CustomerResolver.get_customer_for_user')
    @patch('wardrobe.models.WardrobeItem.objects.filter')
    def test_customer_only_sees_own_items(self, mock_filter, mock_resolver):
        mock_resolver.return_value = self.customer1
        item1 = WardrobeItem(id=1, customer_id='cust-uuid-1', item_name='Silk Blue Kurti', category='Kurtis', primary_color='Royal Blue', occasion='Festive')
        mock_qs = MagicMock()
        mock_qs.__iter__.return_value = [item1]
        mock_qs.__len__.return_value = 1
        mock_filter.return_value = mock_qs

        request = self.factory.get('/api/wardrobe/')
        force_authenticate(request, user=self.user1)
        view = WardrobeListCreateView.as_view()
        response = view(request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_filter.assert_called_with(customer_id='cust-uuid-1')

    @patch('cart.services.CustomerResolver.get_customer_for_user')
    @patch('wardrobe.models.WardrobeItem.objects.get')
    def test_customer_cannot_access_other_users_item(self, mock_get, mock_resolver):
        mock_resolver.return_value = self.customer1
        # When querying for customer1, object belonging to customer2 raises DoesNotExist
        mock_get.side_effect = WardrobeItem.DoesNotExist

        request = self.factory.get('/api/wardrobe/99/')
        force_authenticate(request, user=self.user1)
        view = WardrobeDetailView.as_view()
        response = view(request, pk=99)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        mock_get.assert_called_with(pk=99, customer_id='cust-uuid-1')

