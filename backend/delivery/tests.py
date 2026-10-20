from unittest.mock import MagicMock, patch
from django.test import SimpleTestCase
from django.urls import reverse, resolve
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework import status

from accounts.models import Role, EmployeeRole
from accounts.authentication import AuthenticatedUser
from delivery.serializers import (
    DeliveryStatusUpdateSerializer,
    DeliveryPartnerListSerializer,
    DeliveryEmployeeSerializer,
    ReturnPickupStatusUpdateSerializer,
)
from delivery.views import (
    DeliveryPartnerMyDeliveriesView,
    DeliveryPartnerDetailView,
    DeliveryPartnerStatusUpdateView,
    DeliveryPartnerDashboardView,
    DeliveryPartnersListView,
    DeliveryPartnerReturnPickupsView,
    DeliveryPartnerReturnPickupDetailView,
    DeliveryPartnerReturnPickupStatusView,
)
from delivery.services import DeliveryPartnerService


class DeliveryURLTests(SimpleTestCase):
    """Test URL routing for Delivery Partner endpoints."""

    def test_my_deliveries_url_resolves(self):
        url = reverse('delivery:my-deliveries')
        self.assertEqual(url, '/api/delivery/my-deliveries/')
        self.assertEqual(resolve(url).func.view_class, DeliveryPartnerMyDeliveriesView)

    def test_delivery_detail_url_resolves(self):
        url = reverse('delivery:delivery-detail', kwargs={'delivery_id': 'DEL-101'})
        self.assertEqual(url, '/api/delivery/deliveries/DEL-101/')
        self.assertEqual(resolve(url).func.view_class, DeliveryPartnerDetailView)

    def test_delivery_status_update_url_resolves(self):
        url = reverse('delivery:delivery-status-update', kwargs={'delivery_id': 'DEL-101'})
        self.assertEqual(url, '/api/delivery/deliveries/DEL-101/status/')
        self.assertEqual(resolve(url).func.view_class, DeliveryPartnerStatusUpdateView)

    def test_dashboard_url_resolves(self):
        url = reverse('delivery:dashboard')
        self.assertEqual(url, '/api/delivery/dashboard/')
        self.assertEqual(resolve(url).func.view_class, DeliveryPartnerDashboardView)

    def test_partners_list_url_resolves(self):
        url = reverse('delivery:partners-list')
        self.assertEqual(url, '/api/delivery/partners/')
        self.assertEqual(resolve(url).func.view_class, DeliveryPartnersListView)

    def test_return_pickups_url_resolves(self):
        url = reverse('delivery:return-pickups')
        self.assertEqual(url, '/api/delivery/return-pickups/')
        self.assertEqual(resolve(url).func.view_class, DeliveryPartnerReturnPickupsView)

    def test_return_pickup_status_url_resolves(self):
        url = reverse('delivery:return-pickup-status', kwargs={'return_id': 'RET-101'})
        self.assertEqual(url, '/api/delivery/return-pickups/RET-101/status/')
        self.assertEqual(resolve(url).func.view_class, DeliveryPartnerReturnPickupStatusView)


class DeliveryStatusSerializerTests(SimpleTestCase):
    """Test status serializer validation for delivery lifecycle."""

    def test_allowed_status_assigned(self):
        serializer = DeliveryStatusUpdateSerializer(data={'status': 'Assigned'})
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data['status'], 'Assigned')

    def test_allowed_status_case_insensitive(self):
        serializer = DeliveryStatusUpdateSerializer(data={'status': 'in transit'})
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data['status'], 'In Transit')

    def test_allowed_status_delivered(self):
        serializer = DeliveryStatusUpdateSerializer(data={'status': 'delivered'})
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data['status'], 'Delivered')

    def test_allowed_status_delayed_with_reason(self):
        serializer = DeliveryStatusUpdateSerializer(data={'status': 'Delayed', 'reason': 'Heavy traffic'})
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data['status'], 'Delayed')
        self.assertEqual(serializer.validated_data['reason'], 'Heavy traffic')

    def test_invalid_status_rejected(self):
        serializer = DeliveryStatusUpdateSerializer(data={'status': 'Cancelled'})
        self.assertFalse(serializer.is_valid())
        self.assertIn('status', serializer.errors)

    def test_return_pickup_allowed_status(self):
        serializer = ReturnPickupStatusUpdateSerializer(data={'status': 'Picked Up'})
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data['status'], 'Picked Up')

    def test_return_pickup_invalid_status(self):
        serializer = ReturnPickupStatusUpdateSerializer(data={'status': 'In Transit'})
        self.assertFalse(serializer.is_valid())
        self.assertIn('status', serializer.errors)


class DeliveryViewPermissionTests(SimpleTestCase):
    """Test RBAC enforcement on Delivery Partner views."""

    def setUp(self):
        self.factory = APIRequestFactory()

    def test_my_deliveries_forbidden_for_customer(self):
        view = DeliveryPartnerMyDeliveriesView.as_view()
        request = self.factory.get('/api/delivery/my-deliveries/')
        user = AuthenticatedUser('uid-cust', 'cust@tarika.com', Role.CUSTOMER)
        force_authenticate(request, user=user)
        response = view(request)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_return_pickups_forbidden_for_customer(self):
        view = DeliveryPartnerReturnPickupsView.as_view()
        request = self.factory.get('/api/delivery/return-pickups/')
        user = AuthenticatedUser('uid-cust', 'cust@tarika.com', Role.CUSTOMER)
        force_authenticate(request, user=user)
        response = view(request)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_my_deliveries_forbidden_for_warehouse_manager(self):
        view = DeliveryPartnerMyDeliveriesView.as_view()
        request = self.factory.get('/api/delivery/my-deliveries/')
        user = AuthenticatedUser('uid-wh', 'wh@tarika.com', Role.WAREHOUSE_MANAGER)
        force_authenticate(request, user=user)
        response = view(request)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_my_deliveries_unauthenticated_rejected(self):
        view = DeliveryPartnerMyDeliveriesView.as_view()
        request = self.factory.get('/api/delivery/my-deliveries/')
        response = view(request)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
