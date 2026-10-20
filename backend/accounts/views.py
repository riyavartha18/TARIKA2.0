from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

from accounts.permissions import IsAuthenticatedUser, IsAdmin
from accounts.serializers import (
    CustomerRegisterSerializer,
    LoginSerializer,
    AdminStaffCreateSerializer
)
from accounts.models import Employee, Customer, Role


class CustomerRegisterView(APIView):
    """
    Public registration endpoint strictly for Customers.
    Never accepts or assigns any role other than CUSTOMER.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = CustomerRegisterSerializer(data=request.data)
        if serializer.is_valid():
            result = serializer.save()
            return Response({
                "message": "Customer account registered successfully.",
                "user": result['user'],
                "tokens": result['tokens']
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LoginView(APIView):
    """
    Universal login endpoint for all roles:
    CUSTOMER, ADMIN, WAREHOUSE_MANAGER, DELIVERY_PARTNER.
    Validates credentials against auth.users and queries trusted profile/role.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            auth_result = serializer.validated_data['auth_result']
            return Response({
                "message": "Login successful.",
                "user": auth_result['user'],
                "tokens": auth_result['tokens']
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LogoutView(APIView):
    """
    Logout endpoint for authenticated users.
    Invalidates client session.
    """
    permission_classes = [IsAuthenticatedUser]

    def post(self, request):
        return Response({
            "message": "Logged out successfully."
        }, status=status.HTTP_200_OK)


class MeView(APIView):
    """
    Returns authenticated user's profile, trusted role, and warehouse context.
    """
    permission_classes = [IsAuthenticatedUser]

    def get(self, request):
        user = request.user
        profile_data = {
            "id": user.auth_user_id,
            "email": user.email,
            "role": user.role,
            "warehouse_id": user.warehouse_id,
            "is_active": user.is_active,
        }

        if user.role == Role.CUSTOMER:
            customer = user.profile
            if not customer:
                try:
                    customer = Customer.objects.filter(auth_user_id=user.auth_user_id).first()
                except Exception:
                    customer = None
            if customer:
                profile_data.update({
                    "customer_id": getattr(customer, 'customer_id', None),
                    "full_name": getattr(customer, 'full_name', None),
                    "phone": getattr(customer, 'phone', None),
                    "city": getattr(customer, 'city', None),
                    "state": getattr(customer, 'state', None),
                    "country": getattr(customer, 'country', None),
                })
        else:
            employee = user.profile
            if not employee:
                try:
                    employee = Employee.objects.filter(auth_user_id=user.auth_user_id).first()
                except Exception:
                    employee = None
            if employee:
                profile_data.update({
                    "employee_id": getattr(employee, 'employee_id', None),
                    "full_name": getattr(employee, 'full_name', None),
                    "phone": getattr(employee, 'phone', None),
                    "created_at": getattr(employee, 'created_at', None),
                })

        return Response({
            "user": profile_data
        }, status=status.HTTP_200_OK)


class AdminCreateStaffView(APIView):
    """
    Admin-only endpoint for provisioning staff members:
    - WAREHOUSE_MANAGER (requires valid warehouse_id)
    - DELIVERY_PARTNER (warehouse_id = NULL)
    
    Customers, Warehouse Managers, and Delivery Partners cannot access this endpoint (403 Forbidden).
    """
    permission_classes = [IsAuthenticatedUser, IsAdmin]

    def post(self, request):
        serializer = AdminStaffCreateSerializer(
            data=request.data,
            context={'request': request}
        )
        if serializer.is_valid():
            created_employee = serializer.save()
            return Response({
                "message": f"Staff account ({created_employee['role']}) created successfully.",
                "employee": created_employee
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
