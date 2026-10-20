from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response

from accounts.permissions import IsCustomer
from cart.services import CustomerResolver
from .serializers import CheckoutRequestSerializer, OrderDetailSerializer, OrderReturnRequestSerializer
from .services import OrderCreationService, OrderQueryService, CustomerReturnService
from .models import Order


class CheckoutView(APIView):
    """
    POST /api/orders/checkout/
    Validates delivery address & payment selection, re-checks real-time inventory,
    creates Order + OrderItem(s) + Payment, and clears the customer's cart.
    Requires authenticated CUSTOMER role.
    """
    permission_classes = [IsCustomer]

    def post(self, request):
        customer = CustomerResolver.get_customer_for_user(request.user)
        serializer = CheckoutRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        order = OrderCreationService.create_order_from_cart(
            customer=customer,
            checkout_data=serializer.validated_data
        )

        response_data = OrderDetailSerializer(order).data
        return Response({
            'message': 'Order placed successfully.',
            'order': response_data,
        }, status=status.HTTP_201_CREATED)


class OrderDetailView(APIView):
    """
    GET /api/orders/<order_id>/
    Retrieves full details of an order.
    Enforces authorization: Customers can only view their own orders.
    Requires authenticated CUSTOMER role.
    """
    permission_classes = [IsCustomer]

    def get(self, request, order_id):
        customer = CustomerResolver.get_customer_for_user(request.user)
        order = OrderQueryService.get_customer_order(customer, order_id)
        serializer = OrderDetailSerializer(order)
        return Response(serializer.data, status=status.HTTP_200_OK)


class CustomerOrdersListView(APIView):
    """
    GET /api/orders/
    Lists all orders placed by the authenticated customer.
    Requires authenticated CUSTOMER role.
    """
    permission_classes = [IsCustomer]

    def get(self, request):
        customer = CustomerResolver.get_customer_for_user(request.user)
        orders = Order.objects.filter(customer=customer).order_by('-order_date')
        serializer = OrderDetailSerializer(orders, many=True)
        return Response({
            'count': len(serializer.data),
            'results': serializer.data
        }, status=status.HTTP_200_OK)


class CustomerOrderReturnView(APIView):
    """
    POST /api/orders/<order_id>/return/
    Allows customer to submit a return request for an eligible delivered order item.
    Enforces authorization: Customer can only request returns for their own orders.
    Requires authenticated CUSTOMER role.
    """
    permission_classes = [IsCustomer]

    def post(self, request, order_id):
        customer = CustomerResolver.get_customer_for_user(request.user)
        serializer = OrderReturnRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        ret = CustomerReturnService.request_return(
            customer=customer,
            order_id=order_id,
            order_item_id=data['order_item_id'],
            return_reason=data['return_reason'],
            condition_on_return=data.get('condition_on_return')
        )

        return Response({
            'message': 'Return request submitted successfully.',
            'return': {
                'return_id': ret.return_id,
                'order_item_id': ret.order_item_id,
                'customer_id': ret.customer_id,
                'return_reason': ret.return_reason,
                'return_date': ret.return_date,
                'return_status': ret.return_status,
                'refund_amount': ret.refund_amount,
                'condition_on_return': ret.condition_on_return,
            }
        }, status=status.HTTP_201_CREATED)
