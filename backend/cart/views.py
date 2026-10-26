import logging

from django.db import DatabaseError
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from accounts.permissions import IsCustomer
from .serializers import (
    WishlistItemSerializer,
    AddToWishlistSerializer,
    CartItemSerializer,
    AddToCartSerializer,
    UpdateCartQuantitySerializer
)
from .services import CustomerResolver, WishlistService, CartService, ServiceUnavailable


logger = logging.getLogger(__name__)


class CustomerAPIView(APIView):
    """Customer-scoped endpoint that never leaks a database failure detail.

    Any database error that survives the service layer (an outage, a schema
    change) becomes a generic 503 with no driver message, which can quote SQL.
    """
    permission_classes = [IsCustomer]

    def handle_exception(self, exc):
        if isinstance(exc, DatabaseError):
            logger.error("%s: database error (%s)", self.__class__.__name__, type(exc).__name__)
            return Response(
                {'detail': ServiceUnavailable.default_detail},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return super().handle_exception(exc)


class WishlistListView(CustomerAPIView):
    """
    GET  /api/wishlist/ -> List the signed-in customer's saved products.
    POST /api/wishlist/ -> Save a product for the signed-in customer.
    Duplicates are impossible: (customer_id, product_id) is unique in the
    existing public.wishlist table.
    """

    def get(self, request):
        customer = CustomerResolver.get_customer_for_user(request.user)
        items = WishlistService.get_customer_wishlist(customer)
        serializer = WishlistItemSerializer(items, many=True)
        return Response({
            'count': len(serializer.data),
            'results': serializer.data
        }, status=status.HTTP_200_OK)

    def post(self, request):
        customer = CustomerResolver.get_customer_for_user(request.user)
        serializer = AddToWishlistSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        product_id = serializer.validated_data['product_id']
        item, created = WishlistService.add_to_wishlist(customer, product_id)
        item_data = WishlistItemSerializer(item).data

        if created:
            return Response({
                'message': 'Product added to wishlist successfully.',
                'already_in_wishlist': False,
                'item': item_data
            }, status=status.HTTP_201_CREATED)
        return Response({
            'message': 'Product is already in your wishlist.',
            'already_in_wishlist': True,
            'item': item_data
        }, status=status.HTTP_200_OK)


class WishlistRemoveView(CustomerAPIView):
    """
    DELETE /api/wishlist/<product_id>/ -> Remove the signed-in customer's row.
    The customer is taken from the session, so another customer's row can never
    be targeted by name or id.
    """

    def delete(self, request, product_id):
        customer = CustomerResolver.get_customer_for_user(request.user)
        removed = WishlistService.remove_from_wishlist(customer, product_id)
        if removed:
            return Response({
                'message': 'Product removed from wishlist successfully.',
                'product_id': product_id
            }, status=status.HTTP_200_OK)
        return Response({
            'message': 'Product was not found in your wishlist.',
            'product_id': product_id
        }, status=status.HTTP_404_NOT_FOUND)


class CartView(CustomerAPIView):
    """
    GET  /api/cart/ (or /api/bag/) -> The customer's bag with subtotal & total.
    POST /api/cart/ (or /api/bag/) -> Add a product, or raise the quantity of
    the line that already holds it.
    """

    def get(self, request):
        customer = CustomerResolver.get_customer_for_user(request.user)
        summary = CartService.get_cart_summary(customer)
        return Response(summary, status=status.HTTP_200_OK)

    def post(self, request):
        customer = CustomerResolver.get_customer_for_user(request.user)
        serializer = AddToCartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        product_id = serializer.validated_data['product_id']
        quantity = serializer.validated_data.get('quantity') or 1

        item, created = CartService.add_to_cart(customer, product_id, quantity)
        summary = CartService.get_cart_summary(customer)

        return Response({
            'message': (
                'Product added to your bag successfully.'
                if created else 'Quantity updated in your bag successfully.'
            ),
            'created': created,
            'item': CartItemSerializer(item).data,
            'cart': summary,
            # Kept for existing callers.
            'summary': summary,
        }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class CartItemDetailView(CustomerAPIView):
    """
    PATCH/PUT /api/cart/<product_id>/ -> Set a line's quantity.
    DELETE    /api/cart/<product_id>/ -> Remove a line.
    """

    def patch(self, request, product_id):
        return self._update_quantity(request, product_id)

    def put(self, request, product_id):
        return self._update_quantity(request, product_id)

    def _update_quantity(self, request, product_id):
        customer = CustomerResolver.get_customer_for_user(request.user)
        serializer = UpdateCartQuantitySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        quantity = serializer.validated_data['quantity']
        item = CartService.update_cart_quantity(customer, product_id, quantity)
        summary = CartService.get_cart_summary(customer)

        return Response({
            'message': 'Bag quantity updated successfully.',
            'item': CartItemSerializer(item).data,
            'cart': summary,
            'summary': summary,
        }, status=status.HTTP_200_OK)

    def delete(self, request, product_id):
        customer = CustomerResolver.get_customer_for_user(request.user)
        removed = CartService.remove_from_cart(customer, product_id)
        if removed:
            summary = CartService.get_cart_summary(customer)
            return Response({
                'message': 'Product removed from your bag successfully.',
                'product_id': product_id,
                'cart': summary,
                'summary': summary,
            }, status=status.HTTP_200_OK)
        return Response({
            'message': 'Product was not found in your bag.',
            'product_id': product_id
        }, status=status.HTTP_404_NOT_FOUND)


class CartClearView(CustomerAPIView):
    """DELETE /api/cart/clear/ -> Empty the signed-in customer's bag."""

    def delete(self, request):
        customer = CustomerResolver.get_customer_for_user(request.user)
        CartService.clear_cart(customer)
        return Response({
            'message': 'Shopping bag cleared successfully.',
            'items': [],
            'total_items': 0,
            'subtotal': 0,
            'total': 0
        }, status=status.HTTP_200_OK)
