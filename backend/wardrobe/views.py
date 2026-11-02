from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from accounts.permissions import IsCustomer
from cart.services import CustomerResolver
from .models import WardrobeItem
from .serializers import WardrobeItemSerializer

class WardrobeListCreateView(APIView):
    """
    GET  /api/wardrobe/ -> List all items in the authenticated customer's wardrobe.
    POST /api/wardrobe/ -> Add a new item to the authenticated customer's wardrobe.
    Strictly scopes queries to authenticated user's customer profile.
    """
    permission_classes = [IsCustomer]

    def get(self, request):
        customer = CustomerResolver.get_customer_for_user(request.user)
        if not customer:
            return Response({'detail': 'Customer account profile not found.'}, status=status.HTTP_400_BAD_REQUEST)

        qs = WardrobeItem.objects.filter(customer_id=customer.customer_id)
        category = request.query_params.get('category')
        color = request.query_params.get('color')
        occasion = request.query_params.get('occasion')

        if category and category.lower() != 'all':
            qs = qs.filter(category__iexact=category)
        if color and color.lower() != 'all':
            qs = qs.filter(primary_color__iexact=color)
        if occasion and occasion.lower() != 'all':
            qs = qs.filter(occasion__iexact=occasion)

        serializer = WardrobeItemSerializer(qs, many=True)
        return Response({
            'count': len(serializer.data),
            'results': serializer.data
        }, status=status.HTTP_200_OK)

    def post(self, request):
        customer = CustomerResolver.get_customer_for_user(request.user)
        if not customer:
            return Response({'detail': 'Customer account profile not found.'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = WardrobeItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Enforce server-side ownership by explicitly binding to authenticated customer
        item = serializer.save(customer_id=customer.customer_id)
        return Response(WardrobeItemSerializer(item).data, status=status.HTTP_201_CREATED)


class WardrobeDetailView(APIView):
    """
    GET    /api/wardrobe/<id>/ -> Retrieve single wardrobe item (owner only).
    PUT    /api/wardrobe/<id>/ -> Update wardrobe item (owner only).
    DELETE /api/wardrobe/<id>/ -> Delete wardrobe item (owner only).
    Enforces server-side ownership check: customers cannot see or modify other users' items.
    """
    permission_classes = [IsCustomer]

    def get_object(self, pk, customer):
        try:
            return WardrobeItem.objects.get(pk=pk, customer_id=customer.customer_id)
        except WardrobeItem.DoesNotExist:
            return None

    def get(self, request, pk):
        customer = CustomerResolver.get_customer_for_user(request.user)
        if not customer:
            return Response({'detail': 'Customer account profile not found.'}, status=status.HTTP_400_BAD_REQUEST)

        item = self.get_object(pk, customer)
        if not item:
            return Response({'detail': 'Wardrobe item not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(WardrobeItemSerializer(item).data, status=status.HTTP_200_OK)

    def put(self, request, pk):
        customer = CustomerResolver.get_customer_for_user(request.user)
        if not customer:
            return Response({'detail': 'Customer account profile not found.'}, status=status.HTTP_400_BAD_REQUEST)

        item = self.get_object(pk, customer)
        if not item:
            return Response({'detail': 'Wardrobe item not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = WardrobeItemSerializer(item, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        updated_item = serializer.save(customer_id=customer.customer_id)
        return Response(WardrobeItemSerializer(updated_item).data, status=status.HTTP_200_OK)

    def delete(self, request, pk):
        customer = CustomerResolver.get_customer_for_user(request.user)
        if not customer:
            return Response({'detail': 'Customer account profile not found.'}, status=status.HTTP_400_BAD_REQUEST)

        item = self.get_object(pk, customer)
        if not item:
            return Response({'detail': 'Wardrobe item not found.'}, status=status.HTTP_404_NOT_FOUND)

        item.delete()
        return Response({'message': 'Wardrobe item deleted successfully.'}, status=status.HTTP_200_OK)
