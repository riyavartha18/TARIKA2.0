from unittest.mock import MagicMock, patch
from django.test import SimpleTestCase
from django.urls import reverse, resolve
from rest_framework import serializers
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import Role, EmployeeRole
from accounts.serializers import (
    CustomerRegisterSerializer,
    AdminStaffCreateSerializer,
    LoginSerializer,
    UserProfileSerializer
)
from accounts.permissions import (
    IsAdmin,
    IsWarehouseManager,
    IsDeliveryPartner,
    IsCustomer,
    IsEmployee,
    IsAssignedWarehouseManager
)
from accounts.authentication import AuthenticatedUser
from accounts.services.supabase_auth import SupabaseAuthService
from accounts.views import (
    CustomerRegisterView,
    LoginView,
    LogoutView,
    MeView,
    AdminCreateStaffView
)


class AccountsURLTests(SimpleTestCase):
    """Test URL routing for Part 1 authentication endpoints."""

    def test_register_url_resolves(self):
        url = reverse('accounts:register')
        self.assertEqual(url, '/api/auth/register/')
        self.assertEqual(resolve(url).func.view_class, CustomerRegisterView)

    def test_login_url_resolves(self):
        url = reverse('accounts:login')
        self.assertEqual(url, '/api/auth/login/')
        self.assertEqual(resolve(url).func.view_class, LoginView)

    def test_logout_url_resolves(self):
        url = reverse('accounts:logout')
        self.assertEqual(url, '/api/auth/logout/')
        self.assertEqual(resolve(url).func.view_class, LogoutView)

    def test_me_url_resolves(self):
        url = reverse('accounts:me')
        self.assertEqual(url, '/api/auth/me/')
        self.assertEqual(resolve(url).func.view_class, MeView)

    def test_staff_create_url_resolves(self):
        url = reverse('accounts:staff-create')
        self.assertEqual(url, '/api/auth/staff/create/')
        self.assertEqual(resolve(url).func.view_class, AdminCreateStaffView)


class AccountsSerializerTests(SimpleTestCase):
    """Test serializer validation rules and role security."""

    def test_customer_registration_serializer_valid(self):
        data = {
            "email": "customer@test.com",
            "password": "Password123!",
            "full_name": "Test Customer",
            "phone": 9876543210,
            "city": "Mumbai"
        }
        serializer = CustomerRegisterSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_customer_registration_ignores_role_injection(self):
        # Even if a malicious request passes role='ADMIN', customer serializer does not process it
        data = {
            "email": "hacker@test.com",
            "password": "Password123!",
            "full_name": "Test Customer",
            "role": "ADMIN"
        }
        serializer = CustomerRegisterSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertNotIn('role', serializer.validated_data)

    def test_customer_registration_password_min_length(self):
        data = {
            "email": "customer@test.com",
            "password": "123",  # Too short
            "full_name": "Test Customer"
        }
        serializer = CustomerRegisterSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('password', serializer.errors)

    def test_admin_staff_create_disallows_invalid_roles(self):
        data = {
            "email": "staff@iras.com",
            "password": "Password123!",
            "full_name": "Staff User",
            "role": "CUSTOMER"  # Invalid for staff create
        }
        serializer = AdminStaffCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('role', serializer.errors)

    def test_warehouse_manager_requires_warehouse_id(self):
        data = {
            "email": "manager@iras.com",
            "password": "Password123!",
            "full_name": "Manager User",
            "role": EmployeeRole.WAREHOUSE_MANAGER
            # warehouse_id missing
        }
        serializer = AdminStaffCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('warehouse_id', serializer.errors)

    def test_delivery_partner_forces_warehouse_id_null(self):
        data = {
            "email": "delivery@iras.com",
            "password": "Password123!",
            "full_name": "Delivery User",
            "role": EmployeeRole.DELIVERY_PARTNER,
            "warehouse_id": "wh-123"  # Should be cleared to None
        }
        serializer = AdminStaffCreateSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertIsNone(serializer.validated_data['warehouse_id'])


class AccountsPermissionTests(SimpleTestCase):
    """Test DRF permission classes and role authorization boundaries."""

    def setUp(self):
        self.factory = APIRequestFactory()

    def test_is_admin_permission(self):
        perm = IsAdmin()
        req = self.factory.get('/')

        # Admin user
        req.user = AuthenticatedUser('uid1', 'admin@iras.com', Role.ADMIN)
        self.assertTrue(perm.has_permission(req, None))

        # Manager user
        req.user = AuthenticatedUser('uid2', 'mgr@iras.com', Role.WAREHOUSE_MANAGER)
        self.assertFalse(perm.has_permission(req, None))

        # Customer user
        req.user = AuthenticatedUser('uid3', 'cust@test.com', Role.CUSTOMER)
        self.assertFalse(perm.has_permission(req, None))

    def test_is_warehouse_manager_permission(self):
        perm = IsWarehouseManager()
        req = self.factory.get('/')

        req.user = AuthenticatedUser('uid2', 'mgr@iras.com', Role.WAREHOUSE_MANAGER, warehouse_id='wh-1')
        self.assertTrue(perm.has_permission(req, None))

        req.user = AuthenticatedUser('uid3', 'cust@test.com', Role.CUSTOMER)
        self.assertFalse(perm.has_permission(req, None))

    def test_is_delivery_partner_permission(self):
        perm = IsDeliveryPartner()
        req = self.factory.get('/')

        req.user = AuthenticatedUser('uid4', 'del@iras.com', Role.DELIVERY_PARTNER)
        self.assertTrue(perm.has_permission(req, None))

        req.user = AuthenticatedUser('uid1', 'admin@iras.com', Role.ADMIN)
        self.assertFalse(perm.has_permission(req, None))

    def test_is_customer_permission(self):
        perm = IsCustomer()
        req = self.factory.get('/')

        req.user = AuthenticatedUser('uid3', 'cust@test.com', Role.CUSTOMER)
        self.assertTrue(perm.has_permission(req, None))

        req.user = AuthenticatedUser('uid1', 'admin@iras.com', Role.ADMIN)
        self.assertFalse(perm.has_permission(req, None))

    def test_is_employee_permission(self):
        perm = IsEmployee()
        req = self.factory.get('/')

        req.user = AuthenticatedUser('uid1', 'admin@iras.com', Role.ADMIN)
        self.assertTrue(perm.has_permission(req, None))

        req.user = AuthenticatedUser('uid2', 'mgr@iras.com', Role.WAREHOUSE_MANAGER)
        self.assertTrue(perm.has_permission(req, None))

        req.user = AuthenticatedUser('uid4', 'del@iras.com', Role.DELIVERY_PARTNER)
        self.assertTrue(perm.has_permission(req, None))

        req.user = AuthenticatedUser('uid3', 'cust@test.com', Role.CUSTOMER)
        self.assertFalse(perm.has_permission(req, None))

    def test_multi_warehouse_isolation(self):
        perm = IsAssignedWarehouseManager()
        req = self.factory.get('/?warehouse_id=WH-NORTH')

        # Manager assigned to WH-NORTH -> Allowed
        req.user = AuthenticatedUser('uid2', 'mgr@iras.com', Role.WAREHOUSE_MANAGER, warehouse_id='WH-NORTH')
        self.assertTrue(perm.has_permission(req, None))

        # Manager assigned to WH-SOUTH -> Denied access to WH-NORTH
        req.user = AuthenticatedUser('uid5', 'mgr2@iras.com', Role.WAREHOUSE_MANAGER, warehouse_id='WH-SOUTH')
        self.assertFalse(perm.has_permission(req, None))

        # Admin -> Allowed access to any warehouse
        req.user = AuthenticatedUser('uid1', 'admin@iras.com', Role.ADMIN)
        self.assertTrue(perm.has_permission(req, None))


class AccountsJWTTests(SimpleTestCase):
    """Test JWT token generation and validation."""

    def test_token_generation_and_verification(self):
        auth_user_id = '12345678-1234-5678-1234-567812345678'
        email = 'manager@iras.com'
        role = Role.WAREHOUSE_MANAGER
        warehouse_id = '9ac8b56f-fc26-44a5-b3cb-42b843844d6a'

        tokens = SupabaseAuthService.generate_token_pair(
            auth_user_id=auth_user_id,
            email=email,
            role=role,
            warehouse_id=warehouse_id
        )

        self.assertIn('access_token', tokens)
        self.assertIn('refresh_token', tokens)

        payload = SupabaseAuthService.verify_token(tokens['access_token'])
        self.assertEqual(payload['sub'], auth_user_id)
        self.assertEqual(payload['email'], email)
        self.assertEqual(payload['role'], role)
        self.assertEqual(payload['warehouse_id'], warehouse_id)


class AccountsViewAPITests(SimpleTestCase):
    """Test API views using APIRequestFactory and authentication contexts."""

    def setUp(self):
        self.factory = APIRequestFactory()

    @patch('accounts.views.CustomerRegisterSerializer.save')
    def test_customer_register_view_success(self, mock_save):
        mock_save.return_value = {
            'user': {'id': 'uid-1', 'email': 'cust@test.com', 'role': Role.CUSTOMER},
            'tokens': {'access_token': 'fake_access', 'refresh_token': 'fake_refresh'}
        }
        view = CustomerRegisterView.as_view()
        request = self.factory.post('/api/auth/register/', {
            "email": "cust@test.com",
            "password": "Password123!",
            "full_name": "Test Customer"
        }, format='json')
        response = view(request)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['user']['role'], Role.CUSTOMER)

    def test_customer_register_view_invalid(self):
        view = CustomerRegisterView.as_view()
        request = self.factory.post('/api/auth/register/', {
            "email": "cust@test.com"
            # Missing password and full_name
        }, format='json')
        response = view(request)
        self.assertEqual(response.status_code, 400)

    @patch('accounts.views.LoginSerializer.is_valid')
    def test_login_view_success(self, mock_is_valid):
        mock_is_valid.return_value = True
        view = LoginView.as_view()
        request = self.factory.post('/api/auth/login/', {
            "email": "cust@test.com",
            "password": "Password123!"
        }, format='json')
        with patch.object(LoginSerializer, 'validated_data', {
            'auth_result': {
                'user': {'id': 'uid-1', 'email': 'cust@test.com', 'role': Role.CUSTOMER},
                'tokens': {'access_token': 'fake_access', 'refresh_token': 'fake_refresh'}
            }
        }):
            response = view(request)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data['message'], "Login successful.")

    def test_me_view_unauthenticated(self):
        view = MeView.as_view()
        request = self.factory.get('/api/auth/me/')
        # No request.user set -> triggers permission failure
        response = view(request)
        self.assertEqual(response.status_code, 401)

    def test_me_view_authenticated(self):
        view = MeView.as_view()
        request = self.factory.get('/api/auth/me/')
        user = AuthenticatedUser(
            '11111111-2222-3333-4444-555555555555',
            'mgr@iras.com',
            Role.WAREHOUSE_MANAGER,
            warehouse_id='wh-1'
        )
        force_authenticate(request, user=user)
        response = view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['user']['role'], Role.WAREHOUSE_MANAGER)
        self.assertEqual(response.data['user']['warehouse_id'], 'wh-1')

    def test_admin_create_staff_forbidden_for_customer(self):
        view = AdminCreateStaffView.as_view()
        request = self.factory.post('/api/auth/staff/create/', {
            "email": "newmgr@iras.com",
            "password": "Password123!",
            "full_name": "New Manager",
            "role": EmployeeRole.WAREHOUSE_MANAGER,
            "warehouse_id": "wh-1"
        }, format='json')
        user = AuthenticatedUser('uid-cust', 'cust@test.com', Role.CUSTOMER)
        force_authenticate(request, user=user)
        response = view(request)
        self.assertEqual(response.status_code, 403)

    def test_admin_create_staff_forbidden_for_warehouse_manager(self):
        view = AdminCreateStaffView.as_view()
        request = self.factory.post('/api/auth/staff/create/', {
            "email": "newmgr@iras.com",
            "password": "Password123!",
            "full_name": "New Manager",
            "role": EmployeeRole.WAREHOUSE_MANAGER,
            "warehouse_id": "wh-1"
        }, format='json')
        user = AuthenticatedUser('uid-mgr', 'mgr@iras.com', Role.WAREHOUSE_MANAGER, warehouse_id='wh-1')
        force_authenticate(request, user=user)
        response = view(request)
        self.assertEqual(response.status_code, 403)

    @patch('accounts.views.AdminStaffCreateSerializer.save')
    def test_admin_create_staff_allowed_for_admin(self, mock_save):
        mock_save.return_value = {
            'employee_id': 10,
            'auth_user_id': 'uid-new',
            'full_name': 'New Manager',
            'email': 'newmgr@iras.com',
            'role': EmployeeRole.WAREHOUSE_MANAGER,
            'warehouse_id': 'wh-1',
            'is_active': True
        }
        view = AdminCreateStaffView.as_view()
        request = self.factory.post('/api/auth/staff/create/', {
            "email": "newmgr@iras.com",
            "password": "Password123!",
            "full_name": "New Manager",
            "role": EmployeeRole.WAREHOUSE_MANAGER,
            "warehouse_id": "wh-1"
        }, format='json')
        user = AuthenticatedUser('uid-admin', 'admin@iras.com', Role.ADMIN)
        force_authenticate(request, user=user)
        with patch('accounts.serializers.Warehouse.objects.filter') as mock_wh_filter:
            mock_wh_filter.return_value.exists.return_value = True
            response = view(request)
            self.assertEqual(response.status_code, 201)
            self.assertEqual(response.data['employee']['role'], EmployeeRole.WAREHOUSE_MANAGER)
