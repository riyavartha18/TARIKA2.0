from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny

from .services import (
    RecommendationService,
    PersonalizedRecommendationService,
    SmartBudgetOutfitService,
)
from .serializers import ProductRecommendationsResponseSerializer


class ProductRecommendationView(APIView):
    """
    GET /api/recommendations/<product_id>/

    Retrieves Apriori-based 'frequently bought together' product recommendations
    for a given product_id.
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


class PersonalizedRecommendationView(APIView):
    """
    GET /api/recommendations/personalized/
    Parameters:
      - gender (optional): 'men' or 'women' (overrides or falls back for guest sessions)
    Provides customer-specific recommendations based on past purchase history and gender segmentation.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        gender_param = request.query_params.get('gender')
        data = PersonalizedRecommendationService.get_recommendations_for_user(
            user=request.user,
            gender_param=gender_param
        )
        return Response(data, status=status.HTTP_200_OK)


class SmartBudgetOutfitView(APIView):
    """
    GET /api/recommendations/smart-budget/
    Parameters:
      - budget (optional, default 3000): Target outfit price cap
      - gender (optional, default 'men'): 'men' or 'women'
      - occasion (optional, default 'casual'): 'casual', 'formal', 'party', 'ethnic'
    Generates genuine, stylistically coordinated outfits adhering to color theory, occasion harmony,
    and Knapsack budget optimization.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        budget = request.query_params.get('budget', 2000)
        gender = request.query_params.get('gender', 'women')
        occasion = request.query_params.get('occasion', 'casual')
        style = request.query_params.get('style', 'chic')
        color = request.query_params.get('color')
        category_direction = request.query_params.get('category_direction', 'all')
        sort = request.query_params.get('sort', 'best')
        personalise = request.query_params.get('personalise', 'true')
        personalise_flag = str(personalise).strip().lower() in ('true', '1')

        customer_id = None
        if request.user and request.user.is_authenticated:
            try:
                from cart.services import CustomerResolver
                customer = CustomerResolver.get_customer_for_user(request.user)
                if customer:
                    customer_id = customer.customer_id
            except Exception:
                customer_id = getattr(request.user, 'auth_user_id', None) or getattr(request.user, 'id', None)

        if not customer_id:
            customer_id = request.query_params.get('customer_id') or request.headers.get('X-Customer-Id')

        wardrobe_item_ids = request.query_params.getlist('wardrobe_item_ids')
        if not wardrobe_item_ids:
            w_str = request.query_params.get('wardrobe_item_ids', '')
            if w_str:
                wardrobe_item_ids = [s.strip() for s in str(w_str).split(',') if s.strip()]

        try:
            budget_val = float(budget)
        except (ValueError, TypeError):
            budget_val = 2000.0

        data = SmartBudgetOutfitService.generate_budget_outfits(
            budget=budget_val,
            gender=gender,
            occasion=occasion,
            style=style,
            preferred_color=color,
            fashion_direction=category_direction,
            sort_by=sort,
            wardrobe_item_ids=wardrobe_item_ids,
            customer_id=customer_id,
            personalise=personalise_flag
        )
        resp = Response(data, status=status.HTTP_200_OK)
        resp['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
        resp['Pragma'] = 'no-cache'
        resp['Expires'] = '0'
        return resp

    def post(self, request):
        budget = request.data.get('budget', 2000)
        gender = request.data.get('gender', 'women')
        occasion = request.data.get('occasion', 'casual')
        style = request.data.get('style', 'chic')
        color = request.data.get('color')
        category_direction = request.data.get('category_direction', 'all')
        sort = request.data.get('sort', 'best')
        personalise = request.data.get('personalise', request.query_params.get('personalise', 'true'))
        personalise_flag = str(personalise).strip().lower() in ('true', '1')

        customer_id = None
        if request.user and request.user.is_authenticated:
            try:
                from cart.services import CustomerResolver
                customer = CustomerResolver.get_customer_for_user(request.user)
                if customer:
                    customer_id = customer.customer_id
            except Exception:
                customer_id = getattr(request.user, 'auth_user_id', None) or getattr(request.user, 'id', None)

        if not customer_id:
            customer_id = request.data.get('customer_id') or request.query_params.get('customer_id') or request.headers.get('X-Customer-Id')

        wardrobe_item_ids = request.data.get('wardrobe_item_ids', [])
        if isinstance(wardrobe_item_ids, str):
            wardrobe_item_ids = [s.strip() for s in wardrobe_item_ids.split(',') if s.strip()]

        try:
            budget_val = float(budget)
        except (ValueError, TypeError):
            budget_val = 2000.0

        data = SmartBudgetOutfitService.generate_budget_outfits(
            budget=budget_val,
            gender=gender,
            occasion=occasion,
            style=style,
            preferred_color=color,
            fashion_direction=category_direction,
            sort_by=sort,
            wardrobe_item_ids=wardrobe_item_ids,
            customer_id=customer_id,
            personalise=personalise_flag
        )
        resp = Response(data, status=status.HTTP_200_OK)
        resp['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
        resp['Pragma'] = 'no-cache'
        resp['Expires'] = '0'
        return resp
