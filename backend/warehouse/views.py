import math
from django.core.cache import cache
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework.pagination import PageNumberPagination

from accounts.permissions import IsAuthenticatedUser, IsWarehouseManager
from accounts.authentication import SupabaseAuthentication
from catalog.cache import bump_catalog_version
from .services import WarehouseService, WarehouseFeatureUnavailable
from catalog.services import CatalogService
from .services import WarehouseService
from .serializers import (
    WarehouseCategoryGroupedSerializer,
    WarehouseProductListSerializer,
    WarehouseOrderSerializer,
    WarehouseOrderDetailSerializer,
    WarehouseDeliverySerializer,
    WarehouseReturnSerializer,
    WarehouseReturnAssignSerializer,
    WarehouseProductDetailSerializer,
    WarehouseProductUpdateSerializer,
    WarehouseOrderDispatchSerializer,
)
from catalog.models import Product
from .models import Order



class StandardWarehousePagination(PageNumberPagination):
    page_size = 15
    page_size_query_param = 'page_size'
    max_page_size = 100

    def get_paginated_response(self, data):
        total_pages = math.ceil(self.page.paginator.count / self.get_page_size(self.request))
        return Response({
            'count': self.page.paginator.count,
            'total_pages': total_pages,
            'current_page': self.page.number,
            'page_size': self.get_page_size(self.request),
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'results': data
        })


class WarehouseProductPagination(StandardWarehousePagination):
    page_size = 20


class WarehouseProductListView(APIView):
    """Paginated warehouse catalog including inactive and hidden products."""
    authentication_classes = [SupabaseAuthentication]
    permission_classes = [IsAuthenticatedUser, IsWarehouseManager]

    def get(self, request):
        queryset = CatalogService.filter_and_sort_products(
            queryset=Product.objects.all(),
            category=request.query_params.get('category'),
            sub_category=request.query_params.get('sub_category'),
            search=request.query_params.get('search'),
            min_price=request.query_params.get('min_price'),
            max_price=request.query_params.get('max_price'),
            in_stock=request.query_params.get('in_stock'),
            sort=request.query_params.get('sort') or 'newest',
            on_sale=request.query_params.get('on_sale'),
            size=request.query_params.get('size'),
            color=request.query_params.get('color'),
            subcategory_search=request.query_params.get('subcategory_search'),
            starts_with=request.query_params.get('starts_with'),
        ).only(
            'product_id',
            'product_name',
            'main_category',
            'sub_category',
            'link',
            'discount_price',
            'actual_price_text',
            'available_quantity',
            'image',
            'is_active',
            'hidden',
            'confidence',
        )
        paginator = WarehouseProductPagination()
        page = paginator.paginate_queryset(queryset, request)
        serializer = WarehouseProductListSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class WarehouseGroupedProductsView(APIView):
    """
    GET /api/warehouse/products/grouped/
    Returns products grouped according to database categories.
    Single DB query + Python grouping = fast response.
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        categories = WarehouseService.get_grouped_category_products()
        # categories is already a list of plain dicts — return directly
        return Response({
            'count': len(categories),
            'categories': categories
        }, status=status.HTTP_200_OK)


class WarehouseProductDetailView(APIView):
    """
    GET  /api/warehouse/products/<product_key>/
        Fetch full product details from the live `public.products` row.
        availability_label ('Available' / 'Out of Stock' / 'Stock Data
        Unavailable') is computed by Django — React must display this value
        directly.

    PUT  /api/warehouse/products/<product_key>/
        Requires an authenticated WAREHOUSE_MANAGER account (Enforced by Django
        permission classes, never by hiding the button in React).
        Validate and persist editable product fields.
        Returns the updated product (re-read from the database) on success.
        Returns validation errors on failure.
    """
    # GET stays public (matches the read-only catalogue endpoints);
    # the Bearer token is only authenticated for PUT so the permission
    # check has a trusted request.user without changing GET behaviour.
    permission_classes = [AllowAny]
    authentication_classes = []

    def get_authenticators(self):
        if self.request.method.lower() in ('put', 'delete'):
            return [SupabaseAuthentication()]
        return super().get_authenticators()

    def get_permissions(self):
        if self.request.method.lower() in ('put', 'delete'):
            return [IsAuthenticatedUser(), IsWarehouseManager()]
        return super().get_permissions()

    def get(self, request, product_id):
        try:
            product = WarehouseService.get_product_detail(product_id)
        except Product.DoesNotExist:
            return Response(
                {'detail': f'Product "{product_id}" not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        serializer = WarehouseProductDetailSerializer(product)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, product_id):
        # 1. Verify the product exists before touching anything
        try:
            existing_product = WarehouseService.get_product_detail(product_id)
        except Product.DoesNotExist:
            return Response(
                {'detail': f'Product "{product_id}" not found.'},
                status=status.HTTP_404_NOT_FOUND
            )

        # 2. Validate incoming data via Django serializer. The stored product
        # row is passed in context so a partial price payload (only discount
        # amount OR only discounted price) is completed from persisted values
        # and every final number is calculated server-side, never trusted
        # from React.
        write_serializer = WarehouseProductUpdateSerializer(
            data=request.data, context={'product': existing_product}
        )
        if not write_serializer.is_valid():
            return Response(
                {'errors': write_serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 3. Persist to database via service layer
        try:
            updated_product = WarehouseService.update_product(
                product_id, write_serializer.validated_data
            )
        except Exception as exc:
            return Response(
                {'detail': f'Database error: {str(exc)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # 4. Serialise and return the updated product (with fresh inventory stock)
        # Any edit (price, stock, category) changes customer-facing listings and
        # the derived category / curated caches, so refresh the whole catalog.
        bump_catalog_version()
        read_serializer = WarehouseProductDetailSerializer(updated_product)
        product_data = read_serializer.data
        product_data['is_active'] = updated_product.is_active
        product_data['hidden'] = updated_product.hidden
        product_data['confidence'] = updated_product.confidence
        return Response(
            {
                'message': 'Product updated successfully.',
                'product': product_data,
            },
            status=status.HTTP_200_OK
        )

    def delete(self, request, product_id):
        """DELETE /api/warehouse/products/<product_key>/

        Requires an authenticated Warehouse Manager. The product is removed from
        the real database: hard-deleted when nothing references it, or archived
        (soft-deleted) when orders / cart / wishlist history still points at it,
        so no business history is ever cascade-deleted."""
        try:
            result = WarehouseService.delete_product(product_id)
        except Product.DoesNotExist:
            return Response(
                {'detail': f'Product "{product_id}" not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as exc:  # noqa: BLE001
            return Response(
                {'detail': f'Database error: {str(exc)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # Product gone (deleted or archived): refresh every cached listing.
        bump_catalog_version()

        if result['action'] == 'deleted':
            message = f'Product "{result["product_name"]}" was permanently deleted.'
        else:
            refs = result['reference_count']
            message = (
                f'Product "{result["product_name"]}" was archived. It no longer appears in '
                f'any listing, but {refs} existing order/cart/wishlist/purchase-order '
                'reference(s) were preserved, so no sales history or outstanding '
                'supplier order was deleted.'
            )
        return Response(
            {'message': message, 'action': result['action']},
            status=status.HTTP_200_OK
        )



class WarehouseOrdersView(APIView):
    """
    GET /api/warehouse/orders/
    Returns paginated database orders with support for search, status, and page.

    Orders are read from the real public.orders rows; `status` maps onto the
    `delivery_status` column, so 'delivered' means delivery_status = 'Delivered'.
    """
    permission_classes = [AllowAny]
    authentication_classes = []


    def get(self, request):
        search = request.query_params.get('search')
        order_status = request.query_params.get('status')
        warehouse_id = request.query_params.get('warehouse')

        try:
            queryset = WarehouseService.get_orders(
                search=search,
                status=order_status,
                warehouse_id=warehouse_id
            )
        except WarehouseFeatureUnavailable as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_409_CONFLICT)

        paginator = StandardWarehousePagination()
        page = paginator.paginate_queryset(queryset, request)
        if page is not None:
            serializer = WarehouseOrderSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        serializer = WarehouseOrderSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class WarehouseOrderDetailView(APIView):
    """
    GET /api/warehouse/orders/<order_id>/
    Fetch complete order detail including customer info and all related order items & products.
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, order_id):
        try:
            order = WarehouseService.get_order_detail(order_id)
        except Order.DoesNotExist:
            return Response(
                {'detail': f'Order "{order_id}" not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        serializer = WarehouseOrderDetailSerializer(order)
        return Response(serializer.data, status=status.HTTP_200_OK)



class WarehouseDeliveriesView(APIView):
    """
    GET /api/warehouse/deliveries/
    Delivery rows derived from the real orders `delivery_status` column.

    This schema has no deliveries table, so each row is the order's own delivery
    state and the courier / dispatch / expected-date columns are reported as
    null rather than invented (see WarehouseService.delivery_row).
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        search = request.query_params.get('search')
        delivery_status = request.query_params.get('status')
        partner = request.query_params.get('partner')
        warehouse_id = request.query_params.get('warehouse')

        try:
            queryset = WarehouseService.get_deliveries(
                search=search,
                status=delivery_status,
                partner=partner,
                warehouse_id=warehouse_id
            )
        except WarehouseFeatureUnavailable as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_409_CONFLICT)

        paginator = StandardWarehousePagination()
        page = paginator.paginate_queryset(queryset, request)
        if page is not None:
            rows = [WarehouseService.delivery_row(order) for order in page]
            serializer = WarehouseDeliverySerializer(rows, many=True)
            return paginator.get_paginated_response(serializer.data)

        rows = [WarehouseService.delivery_row(order) for order in queryset]
        serializer = WarehouseDeliverySerializer(rows, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class WarehouseReturnsView(APIView):
    """
    GET /api/warehouse/returns/
    Returns paginated database returns with support for search and reason.

    Every row comes from the real public.returns table (customer, product and
    reason). A status filter is refused with 409 because the table has no status
    column, so the dashboard can say so instead of showing a filtered list that
    silently ignored the choice.
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        search = request.query_params.get('search')
        return_status = request.query_params.get('status')
        reason = request.query_params.get('reason')

        try:
            queryset = WarehouseService.get_returns(
                search=search,
                status=return_status,
                reason=reason
            )
        except WarehouseFeatureUnavailable as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_409_CONFLICT)

        paginator = StandardWarehousePagination()
        page = paginator.paginate_queryset(queryset, request)
        if page is not None:
            serializer = WarehouseReturnSerializer(page, many=True)
            response_data = paginator.get_paginated_response(serializer.data)
            return response_data

        serializer = WarehouseReturnSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class WarehouseProfileView(APIView):
    """
    GET /api/warehouse/profile/
    Returns authenticated Warehouse Manager profile and assigned facility details.
    """
    permission_classes = [IsAuthenticatedUser, IsWarehouseManager]

    def get(self, request):
        user = request.user
        return Response({
            'user': {
                'id': user.auth_user_id,
                'email': user.email,
                'role': user.role,
                'warehouse_id': user.warehouse_id,
                'is_active': user.is_active,
            }
        }, status=status.HTTP_200_OK)


class WarehouseReturnAcceptView(APIView):
    """
    PATCH /api/warehouse/returns/<return_id>/accept/
    Accepts/Approves a return request. Only allowed when current status is 'Requested'.
    Updates return_status to 'Approved' and computes refund_amount.
    All validation and DB update handled by Django service layer with warehouse authorization.
    """
    permission_classes = [AllowAny]

    def patch(self, request, return_id):
        try:
            updated_return = WarehouseService.accept_return(return_id, manager_user=request.user)
        except WarehouseFeatureUnavailable as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_409_CONFLICT)
        except PermissionError as p_err:
            return Response({'detail': str(p_err)}, status=status.HTTP_403_FORBIDDEN)
        except Exception as exc:
            err_msg = str(exc)
            if 'not found' in err_msg.lower():
                return Response({'detail': err_msg}, status=status.HTTP_404_NOT_FOUND)
            return Response({'detail': err_msg}, status=status.HTTP_400_BAD_REQUEST)

        serializer = WarehouseReturnSerializer(updated_return)
        return Response({
            'message': 'Return approved successfully.',
            'return': serializer.data,
        }, status=status.HTTP_200_OK)

    def post(self, request, return_id):
        return self.patch(request, return_id)



class WarehouseReturnRejectView(APIView):
    """
    PATCH /api/warehouse/returns/<return_id>/reject/
    Rejects a return request. Only allowed when current status is 'Requested'.
    Updates return_status to 'Rejected'.
    All validation and DB update handled by Django service layer with warehouse authorization.
    """
    permission_classes = [AllowAny]

    def patch(self, request, return_id):
        try:
            updated_return = WarehouseService.reject_return(return_id, manager_user=request.user)
        except WarehouseFeatureUnavailable as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_409_CONFLICT)
        except PermissionError as p_err:
            return Response({'detail': str(p_err)}, status=status.HTTP_403_FORBIDDEN)
        except Exception as exc:
            err_msg = str(exc)
            if 'not found' in err_msg.lower():
                return Response({'detail': err_msg}, status=status.HTTP_404_NOT_FOUND)
            return Response({'detail': err_msg}, status=status.HTTP_400_BAD_REQUEST)

        serializer = WarehouseReturnSerializer(updated_return)
        return Response({
            'message': 'Return rejected successfully.',
            'return': serializer.data,
        }, status=status.HTTP_200_OK)

    def post(self, request, return_id):
        return self.patch(request, return_id)



class WarehouseReturnAssignView(APIView):
    """
    POST /api/warehouse/returns/<return_id>/assign/
    Assigns an approved return to a real active delivery partner employee.
    Enforces warehouse permission, verifies courier company and employee status.
    Sets return_status to 'Pickup Assigned' and creates corresponding Delivery record.
    """
    permission_classes = [AllowAny]

    def post(self, request, return_id):
        serializer = WarehouseReturnAssignSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        try:
            updated_return = WarehouseService.assign_return_pickup(
                return_id=return_id,
                delivery_partner=data['delivery_partner'],
                assigned_employee_id=data['assigned_employee_id'],
                manager_user=request.user
            )
        except WarehouseFeatureUnavailable as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_409_CONFLICT)
        except PermissionError as p_err:
            return Response({'detail': str(p_err)}, status=status.HTTP_403_FORBIDDEN)
        except Exception as exc:
            err_msg = str(exc)
            if 'not found' in err_msg.lower():
                return Response({'detail': err_msg}, status=status.HTTP_404_NOT_FOUND)
            return Response({'detail': err_msg}, status=status.HTTP_400_BAD_REQUEST)

        serializer_ret = WarehouseReturnSerializer(updated_return)
        return Response({
            'message': f"Return pickup '{return_id}' assigned successfully.",
            'return': serializer_ret.data,
        }, status=status.HTTP_200_OK)


class WarehouseReturnReceiveView(APIView):
    """
    PATCH /api/warehouse/returns/<return_id>/receive/
    Confirms physical receipt of returned merchandise at the warehouse.
    Only allowed after merchandise has been picked up by the delivery partner.
    Sets return_status to 'Completed'.
    """
    permission_classes = [AllowAny]

    def patch(self, request, return_id):
        try:
            updated_return = WarehouseService.receive_return(
                return_id=return_id,
                manager_user=request.user
            )
        except WarehouseFeatureUnavailable as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_409_CONFLICT)
        except PermissionError as p_err:
            return Response({'detail': str(p_err)}, status=status.HTTP_403_FORBIDDEN)
        except Exception as exc:
            err_msg = str(exc)
            if 'not found' in err_msg.lower():
                return Response({'detail': err_msg}, status=status.HTTP_404_NOT_FOUND)
            return Response({'detail': err_msg}, status=status.HTTP_400_BAD_REQUEST)

        serializer_ret = WarehouseReturnSerializer(updated_return)
        return Response({
            'message': f"Return '{return_id}' confirmed received at warehouse and marked completed.",
            'return': serializer_ret.data,
        }, status=status.HTTP_200_OK)

    def post(self, request, return_id):
        return self.patch(request, return_id)



class WarehouseCourierPartnersView(APIView):
    """
    GET /api/warehouse/courier-partners/
    Courier companies recorded in the database.

    This schema has no deliveries table and no employees table, so there is no
    courier data to list: the response is an empty list plus an explicit
    `available: false` and the reason, which lets the dispatch UI say "not
    tracked by this database" instead of showing a fabricated dropdown.
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        partners = WarehouseService.get_courier_partners()
        return Response({
            'count': len(partners),
            'partners': partners,
            'available': False,
            'detail': WarehouseService.DISPATCH_UNAVAILABLE,
        }, status=status.HTTP_200_OK)


class WarehouseDeliveryEmployeesView(APIView):
    """
    GET /api/warehouse/delivery-employees/?company=<company_name>
    Active delivery-partner employees, from the employees table.

    No employees table exists in this schema, so the list is empty and the
    response states that plainly (see WarehouseCourierPartnersView).
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        company = request.query_params.get('company')
        employees = WarehouseService.get_delivery_employees(company=company)
        return Response({
            'count': len(employees),
            'employees': employees,
            'available': False,
            'detail': WarehouseService.DISPATCH_UNAVAILABLE,
        }, status=status.HTTP_200_OK)


class WarehouseOrderDispatchView(APIView):
    """
    POST /api/warehouse/orders/<order_id>/dispatch/
    Dispatches a confirmed warehouse order to an assigned courier partner and employee:
    1. Enforces warehouse assignment (manager can only dispatch orders for their assigned warehouse).
    2. Validates courier partner, active delivery employee, and explicit expected delivery date.
    3. Prevents duplicate delivery rows (updates existing if present, otherwise creates).
    4. Updates order_status to 'shipped' and delivery_status to 'Assigned'.
    """
    permission_classes = [AllowAny]

    def post(self, request, order_id):
        serializer = WarehouseOrderDispatchSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'errors': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        data = serializer.validated_data
        try:
            order, delivery = WarehouseService.dispatch_order(
                order_id=order_id,
                delivery_partner=data['delivery_partner'],
                assigned_employee_id=data['assigned_employee_id'],
                expected_delivery_date=data['expected_delivery_date'],
                manager_user=request.user
            )
        except WarehouseFeatureUnavailable as exc:
            return Response(
                {'detail': str(exc)},
                status=status.HTTP_409_CONFLICT
            )
        except Order.DoesNotExist:
            return Response(
                {'detail': f"Order '{order_id}' not found."},
                status=status.HTTP_404_NOT_FOUND
            )
        except PermissionError as p_err:
            return Response(
                {'detail': str(p_err)},
                status=status.HTTP_403_FORBIDDEN
            )
        except ValueError as v_err:
            return Response(
                {'detail': str(v_err)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as exc:
            return Response(
                {'detail': f"Dispatch error: {str(exc)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        order_serializer = WarehouseOrderDetailSerializer(order)
        return Response({
            'message': f"Order '{order_id}' dispatched successfully.",
            'order': order_serializer.data,
            'delivery': {
                'delivery_id': delivery.delivery_id,
                'delivery_status': delivery.delivery_status,
                'delivery_partner': delivery.delivery_partner,
                'assigned_employee_id': delivery.assigned_employee_id,
                'assigned_employee_name': delivery.assigned_employee.full_name if delivery.assigned_employee else None,
                'dispatch_date': delivery.dispatch_date,
                'expected_delivery_date': delivery.expected_delivery_date,
            }
        }, status=status.HTTP_200_OK)
