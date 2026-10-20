from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination

from accounts.permissions import IsAuthenticatedUser, IsDeliveryPartner, IsEmployee
from accounts.models import Employee, EmployeeRole
from warehouse.models import Delivery, Return
from delivery.services import DeliveryPartnerService
from delivery.serializers import (
    DeliveryPartnerListSerializer,
    DeliveryPartnerDetailSerializer,
    DeliveryStatusUpdateSerializer,
    DeliveryEmployeeSerializer,
    DeliveryReturnPickupSerializer,
    ReturnPickupStatusUpdateSerializer,
)


class StandardDeliveryPagination(PageNumberPagination):
    page_size = 15
    page_size_query_param = 'page_size'
    max_page_size = 100


class DeliveryPartnerMyDeliveriesView(APIView):
    """
    GET /api/delivery/my-deliveries/
    Returns ONLY deliveries assigned to the authenticated delivery employee.
    Enforces strict ownership check.
    """
    permission_classes = [IsAuthenticatedUser, IsDeliveryPartner]

    def get(self, request):
        employee = getattr(request.user, 'profile', None)
        if not employee or not getattr(employee, 'employee_id', None):
            return Response(
                {"detail": "No delivery employee profile associated with this account."},
                status=status.HTTP_403_FORBIDDEN
            )

        status_param = request.query_params.get('status')
        search_param = request.query_params.get('search')

        queryset = DeliveryPartnerService.get_assigned_deliveries(
            employee_id=employee.employee_id,
            status=status_param,
            search=search_param
        )

        paginator = StandardDeliveryPagination()
        page = paginator.paginate_queryset(queryset, request)
        if page is not None:
            serializer = DeliveryPartnerListSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        serializer = DeliveryPartnerListSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class DeliveryPartnerDetailView(APIView):
    """
    GET /api/delivery/deliveries/<delivery_id>/
    Fetch complete details of an assigned delivery.
    Enforces strict ownership check.
    """
    permission_classes = [IsAuthenticatedUser, IsDeliveryPartner]

    def get(self, request, delivery_id):
        employee = getattr(request.user, 'profile', None)
        if not employee or not getattr(employee, 'employee_id', None):
            return Response(
                {"detail": "No delivery employee profile associated with this account."},
                status=status.HTTP_403_FORBIDDEN
            )

        try:
            delivery = DeliveryPartnerService.get_delivery_detail(
                delivery_id=delivery_id,
                employee_id=employee.employee_id
            )
        except Delivery.DoesNotExist:
            return Response(
                {"detail": f"Delivery '{delivery_id}' not found or not assigned to you."},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = DeliveryPartnerDetailSerializer(delivery)
        return Response(serializer.data, status=status.HTTP_200_OK)


class DeliveryPartnerStatusUpdateView(APIView):
    """
    PATCH /api/delivery/deliveries/<delivery_id>/status/
    Actions:
    - Confirm Pickup -> status = "Picked Up"
    - Start Delivery -> status = "In Transit"
    - Mark as Delivered -> status = "Delivered", actual_delivery_date = TODAY, order_status = "delivered"
    - Delayed/Failed -> status = "Delayed" / "Failed", reason = failure_reason
    Enforces strict ownership check.
    """
    permission_classes = [IsAuthenticatedUser, IsDeliveryPartner]

    def patch(self, request, delivery_id):
        employee = getattr(request.user, 'profile', None)
        if not employee or not getattr(employee, 'employee_id', None):
            return Response(
                {"detail": "No delivery employee profile associated with this account."},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = DeliveryStatusUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        new_status = serializer.validated_data['status']
        reason = serializer.validated_data.get('reason', '')

        try:
            updated_delivery = DeliveryPartnerService.update_delivery_status(
                delivery_id=delivery_id,
                employee_id=employee.employee_id,
                new_status=new_status,
                reason=reason
            )
        except Delivery.DoesNotExist:
            return Response(
                {"detail": f"Delivery '{delivery_id}' not found or not assigned to you."},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as exc:
            return Response(
                {"detail": f"Error updating delivery status: {str(exc)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        detail_serializer = DeliveryPartnerDetailSerializer(updated_delivery)
        return Response({
            "message": f"Delivery status updated to '{new_status}' successfully.",
            "delivery": detail_serializer.data
        }, status=status.HTTP_200_OK)


class DeliveryPartnerDashboardView(APIView):
    """
    GET /api/delivery/dashboard/
    Returns dashboard summary metrics for the logged in delivery partner.
    """
    permission_classes = [IsAuthenticatedUser, IsDeliveryPartner]

    def get(self, request):
        employee = getattr(request.user, 'profile', None)
        if not employee or not getattr(employee, 'employee_id', None):
            return Response(
                {"detail": "No delivery employee profile associated with this account."},
                status=status.HTTP_403_FORBIDDEN
            )

        metrics = DeliveryPartnerService.get_dashboard_metrics(employee.employee_id)
        return Response({
            "employee": {
                "employee_id": employee.employee_id,
                "full_name": employee.full_name,
                "email": employee.email,
                "courier_company": getattr(employee, 'courier_company', None),
            },
            "metrics": metrics
        }, status=status.HTTP_200_OK)


class DeliveryPartnersListView(APIView):
    """
    GET /api/delivery/partners/
    Returns list of active delivery partner employees (accessible by staff/admin).
    """
    permission_classes = [IsAuthenticatedUser, IsEmployee]

    def get(self, request):
        partners = Employee.objects.filter(
            role=EmployeeRole.DELIVERY_PARTNER,
            is_active=True
        ).order_by('full_name')
        serializer = DeliveryEmployeeSerializer(partners, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class DeliveryPartnerReturnPickupsView(APIView):
    """
    GET /api/delivery/return-pickups/
    Returns ONLY return pickups assigned to the authenticated delivery employee.
    Enforces strict employee data isolation.
    """
    permission_classes = [IsAuthenticatedUser, IsDeliveryPartner]

    def get(self, request):
        employee = getattr(request.user, 'profile', None)
        if not employee or not getattr(employee, 'employee_id', None):
            return Response(
                {"detail": "No delivery employee profile associated with this account."},
                status=status.HTTP_403_FORBIDDEN
            )

        status_param = request.query_params.get('status')
        search_param = request.query_params.get('search')

        queryset = DeliveryPartnerService.get_assigned_return_pickups(
            employee_id=employee.employee_id,
            status=status_param,
            search=search_param
        )

        paginator = StandardDeliveryPagination()
        page = paginator.paginate_queryset(queryset, request)
        if page is not None:
            serializer = DeliveryReturnPickupSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        serializer = DeliveryReturnPickupSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class DeliveryPartnerReturnPickupDetailView(APIView):
    """
    GET /api/delivery/return-pickups/<return_id>/
    Returns full details of an assigned return pickup.
    Enforces assigned employee authorization.
    """
    permission_classes = [IsAuthenticatedUser, IsDeliveryPartner]

    def get(self, request, return_id):
        employee = getattr(request.user, 'profile', None)
        if not employee or not getattr(employee, 'employee_id', None):
            return Response(
                {"detail": "No delivery employee profile associated with this account."},
                status=status.HTTP_403_FORBIDDEN
            )

        try:
            ret = DeliveryPartnerService.get_return_pickup_detail(return_id, employee.employee_id)
        except Return.DoesNotExist:
            return Response(
                {"detail": f"Return pickup '{return_id}' not found or not assigned to you."},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = DeliveryReturnPickupSerializer(ret)
        return Response(serializer.data, status=status.HTTP_200_OK)


class DeliveryPartnerReturnPickupStatusView(APIView):
    """
    PATCH /api/delivery/return-pickups/<return_id>/status/
    Updates status of assigned return pickup.
    Allowed transitions:
      Pickup Assigned -> Pickup Accepted, Failed
      Pickup Accepted -> Picked Up, Failed
      Picked Up -> Received at Warehouse, Failed
    """
    permission_classes = [IsAuthenticatedUser, IsDeliveryPartner]

    def patch(self, request, return_id):
        employee = getattr(request.user, 'profile', None)
        if not employee or not getattr(employee, 'employee_id', None):
            return Response(
                {"detail": "No delivery employee profile associated with this account."},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = ReturnPickupStatusUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        new_status = serializer.validated_data['status']
        reason = serializer.validated_data.get('reason', '')

        try:
            updated_return = DeliveryPartnerService.update_return_pickup_status(
                return_id=return_id,
                employee_id=employee.employee_id,
                new_status=new_status,
                reason=reason
            )
        except Return.DoesNotExist:
            return Response(
                {"detail": f"Return pickup '{return_id}' not found or not assigned to you."},
                status=status.HTTP_404_NOT_FOUND
            )
        except ValueError as v_err:
            return Response({"detail": str(v_err)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            return Response({"detail": f"Error updating return status: {str(exc)}"}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            "message": f"Return pickup status updated to '{new_status}' successfully.",
            "return": DeliveryReturnPickupSerializer(updated_return).data
        }, status=status.HTTP_200_OK)
