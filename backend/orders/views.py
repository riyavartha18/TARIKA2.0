from rest_framework import status
from rest_framework.response import Response

from cart.views import CustomerAPIView
from cart.services import CustomerResolver
from .serializers import (
    CheckoutRequestSerializer,
    OrderDetailSerializer,
    OrderReturnRequestSerializer,
)
from .services import OrderCreationService, OrderQueryService, CustomerReturnService


class CheckoutView(CustomerAPIView):
    """
    POST /api/orders/checkout/
    Re-checks stock, prices the bag from the database, writes one row per line
    into the existing public.orders table and clears the cart afterwards.
    """

    def post(self, request):
        customer = CustomerResolver.get_customer_for_user(request.user)
        serializer = CheckoutRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        orders = OrderCreationService.create_orders_from_cart(
            customer=customer,
            checkout_data=serializer.validated_data,
        )

        payloads = OrderDetailSerializer(orders, many=True).data
        first = payloads[0]
        grand_total = round(sum(order['total_amount'] for order in payloads), 2)

        return Response({
            'message': (
                f'{len(payloads)} order(s) placed successfully.'
                if len(payloads) > 1 else 'Order placed successfully.'
            ),
            # `order` keeps the single-order contract the confirmation page uses.
            'order': first,
            'orders': payloads,
            'order_count': len(payloads),
            'total_amount': grand_total,
        }, status=status.HTTP_201_CREATED)


class OrderDetailView(CustomerAPIView):
    """
    GET /api/orders/<order_id>/
    Ownership is enforced inside the query, so an order belonging to someone
    else is simply not found.
    """

    def get(self, request, order_id):
        customer = CustomerResolver.get_customer_for_user(request.user)
        order = OrderQueryService.get_customer_order(customer, order_id)
        return Response(OrderDetailSerializer(order).data, status=status.HTTP_200_OK)


class CustomerOrdersListView(CustomerAPIView):
    """
    GET /api/orders/
    The signed-in customer's own orders, newest first, with product details
    joined from public.products.
    """

    def get(self, request):
        customer = CustomerResolver.get_customer_for_user(request.user)
        orders = OrderQueryService.get_customer_orders(customer)
        payloads = OrderDetailSerializer(orders, many=True).data
        return Response({
            'count': len(payloads),
            'results': payloads,
        }, status=status.HTTP_200_OK)


class CustomerOrderReturnView(CustomerAPIView):
    """
    POST /api/orders/<order_id>/return/
    The current database has no returns records, so this answers with a clear
    validation message after verifying that the order belongs to the requester.
    """

    def post(self, request, order_id):
        customer = CustomerResolver.get_customer_for_user(request.user)
        serializer = OrderReturnRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        CustomerReturnService.request_return(
            customer=customer,
            order_id=order_id,
            order_item_id=data['order_item_id'],
            return_reason=data['return_reason'],
            condition_on_return=data.get('condition_on_return'),
        )
