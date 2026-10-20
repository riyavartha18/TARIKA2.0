from rest_framework.permissions import BasePermission
from accounts.models import Role


class IsAuthenticatedUser(BasePermission):
    """
    Allows access only to authenticated and active users.
    """
    message = "Authentication credentials were not provided or are invalid."

    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and 
            getattr(request.user, 'is_active', True)
        )


class IsAdmin(BasePermission):
    """
    Allows access only to users with the ADMIN role.
    """
    message = "Admin access required. You do not have permission to perform this action."

    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and 
            getattr(request.user, 'role', None) == Role.ADMIN
        )


class IsWarehouseManager(BasePermission):
    """
    Allows access only to users with the WAREHOUSE_MANAGER role.
    """
    message = "Warehouse Manager access required."

    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and 
            getattr(request.user, 'role', None) == Role.WAREHOUSE_MANAGER
        )


class IsDeliveryPartner(BasePermission):
    """
    Allows access only to users with the DELIVERY_PARTNER role.
    """
    message = "Delivery Partner access required."

    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and 
            getattr(request.user, 'role', None) == Role.DELIVERY_PARTNER
        )


class IsCustomer(BasePermission):
    """
    Allows access only to users with the CUSTOMER role.
    """
    message = "Customer access required."

    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and 
            getattr(request.user, 'role', None) == Role.CUSTOMER
        )


class IsEmployee(BasePermission):
    """
    Allows access only to IRAS staff (Admin, Warehouse Manager, Delivery Partner).
    """
    message = "Employee access required."

    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and 
            getattr(request.user, 'role', None) in [
                Role.ADMIN, 
                Role.WAREHOUSE_MANAGER, 
                Role.DELIVERY_PARTNER
            ]
        )


class IsAssignedWarehouseManager(BasePermission):
    """
    Ensures that Warehouse Managers can only manage their assigned warehouse.
    Admins bypass this restriction (system-wide access).
    """
    message = "You are not authorized to access or manage this warehouse's resources."

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.user.role == Role.ADMIN:
            return True
        if request.user.role == Role.WAREHOUSE_MANAGER:
            target_warehouse = None
            if view and hasattr(view, 'kwargs') and view.kwargs:
                target_warehouse = view.kwargs.get('warehouse_id')
            if not target_warehouse:
                query_dict = getattr(request, 'query_params', getattr(request, 'GET', None))
                if query_dict:
                    target_warehouse = query_dict.get('warehouse_id')

            if target_warehouse:
                return str(request.user.warehouse_id) == str(target_warehouse)
            return True
        return False

    def has_object_permission(self, request, view, obj):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.user.role == Role.ADMIN:
            return True
        if request.user.role == Role.WAREHOUSE_MANAGER:
            obj_warehouse_id = getattr(obj, 'warehouse_id', None)
            if obj_warehouse_id:
                return str(request.user.warehouse_id) == str(obj_warehouse_id)
        return False
