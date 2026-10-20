from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny

from .services import RecommendationService
from .serializers import ProductRecommendationsResponseSerializer


class ProductRecommendationView(APIView):
    """
    GET /api/recommendations/<product_id>/

    Retrieves Apriori-based 'frequently bought together' product recommendations
    for a given product_id.

    - Resolves product_id using the catalog products table.
    - Matches association rules from the product_recommendations table.
    - Returns recommended products and statistical metrics (support, confidence, lift).
    - If the product exists but has no association rules, returns an empty recommendation list.
    - If product_id does not exist, returns 404.
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, product_id):
        if not product_id or not str(product_id).strip():
            return Response(
                {'detail': 'A valid product_id parameter is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        clean_product_id = str(product_id).strip()
        data = RecommendationService.get_recommendations_for_product(clean_product_id)

        if data is None:
            return Response(
                {'detail': f'Product with id "{clean_product_id}" was not found.'},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = ProductRecommendationsResponseSerializer(data)
        return Response(serializer.data, status=status.HTTP_200_OK)
