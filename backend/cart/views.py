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
from .services import CustomerResolver, WishlistService, CartService


class WishlistListView(APIView):
    """
    GET  /api/wishlist/ -> List all items in customer's wishlist.
    POST /api/wishlist/ -> Add a product to customer's wishlist (prevents duplicates).
    Requires authenticated CUSTOMER role.
    """
    permission_classes = [IsCustomer]

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
        else:
            return Response({
                'message': 'Product is already in your wishlist.',
                'already_in_wishlist': True,
                'item': item_data
            }, status=status.HTTP_200_OK)


class WishlistRemoveView(APIView):
    """
    DELETE /api/wishlist/<product_id>/ -> Remove product from customer's wishlist.
    Requires authenticated CUSTOMER role.
    """
    permission_classes = [IsCustomer]

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


class CartView(APIView):
    """
    GET  /api/cart/ (or /api/bag/) -> View customer's bag with subtotal & total.
    POST /api/cart/ (or /api/bag/) -> Add product with quantity to customer's bag.
    Requires authenticated CUSTOMER role.
    """
    permission_classes = [IsCustomer]

    def get(self, request):
        customer = CustomerResolver.get_customer_for_user(request.user)
        summary = CartService.get_cart_summary(customer)
        return Response(summary, status=status.HTTP_200_OK)

    def post(self, request):
        customer = CustomerResolver.get_customer_for_user(request.user)
        serializer = AddToCartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        product_id = serializer.validated_data['product_id']
        quantity = serializer.validated_data.get('quantity', 1)

        item, created = CartService.add_to_cart(customer, product_id, quantity)
        summary = CartService.get_cart_summary(customer)

        return Response({
            'message': 'Product added to your bag successfully.',
            'item': CartItemSerializer(item).data,
            'summary': summary
        }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class CartItemDetailView(APIView):
    """
    PATCH  /api/cart/<product_id>/ -> Update item quantity in bag.
    PUT    /api/cart/<product_id>/ -> Update item quantity in bag.
    DELETE /api/cart/<product_id>/ -> Remove item from bag.
    Requires authenticated CUSTOMER role.
    """
    permission_classes = [IsCustomer]

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
            'summary': summary
        }, status=status.HTTP_200_OK)

    def delete(self, request, product_id):
        customer = CustomerResolver.get_customer_for_user(request.user)
        removed = CartService.remove_from_cart(customer, product_id)
        if removed:
            summary = CartService.get_cart_summary(customer)
            return Response({
                'message': 'Product removed from your bag successfully.',
                'product_id': product_id,
                'summary': summary
            }, status=status.HTTP_200_OK)
        return Response({
            'message': 'Product was not found in your bag.',
            'product_id': product_id
        }, status=status.HTTP_404_NOT_FOUND)


class CartClearView(APIView):
    """
    DELETE /api/cart/clear/ -> Empty the customer's bag.
    Requires authenticated CUSTOMER role.
    """
    permission_classes = [IsCustomer]

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
