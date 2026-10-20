"""
views.py
--------
API views for the Revenue Forecasting module (Admin Analysis feature).

GET /api/revenue-forecasting/
  -> Admin authentication required (mirrors Demand Prediction analytics access)
  -> Consumes the existing predicted-sales output and converts it into
     expected revenue (expected_revenue = predicted_sales * selling_price)

All business logic (revenue math, aggregation, category breakdown) runs in the
Python service layer; the React frontend only consumes and displays it.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from accounts.permissions import IsAuthenticatedUser, IsAdmin
from revenue_forecasting.services import run_revenue_forecast


class RevenueForecastView(APIView):
    """
    Revenue Forecasting — Expected Revenue from Predicted Sales.

    Access: Admin only.

    Supports the same optional client filters used by the existing Demand
    Prediction analytics endpoint (search / category / demand_level) so the
    Admin Analysis UI behaves consistently.
    """
    permission_classes = [IsAuthenticatedUser, IsAdmin]

    def get(self, request):
        try:
            result = run_revenue_forecast()

            if not result.get('success'):
                return Response(
                    {'error': result.get('error', 'Revenue forecasting pipeline failed.')},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            products = result['products']

            # Optional query filters (same conventions as demand prediction).
            search = request.query_params.get('search', '').strip().lower()
            demand_level = request.query_params.get('demand_level', '').strip().upper()
            category = request.query_params.get('category', '').strip().lower()

            if search:
                products = [
                    p for p in products
                    if search in (p.get('product_name') or '').lower()
                    or search in (p.get('category_name') or '').lower()
                ]

            if demand_level and demand_level != 'ALL':
                products = [
                    p for p in products
                    if (p.get('predicted_demand') or '').upper() == demand_level
                ]

            if category and category != 'all':
                products = [
                    p for p in products
                    if category in (p.get('category_name') or '').lower()
                ]

            return Response({
                'forecast_month': result['forecast_month'],
                'forecast_month_label': result['forecast_month_label'],
                'summary': result['summary'],
                'products': products,
                'total_filtered_products': len(products),
            }, status=status.HTTP_200_OK)

        except Exception as exc:
            return Response(
                {'error': f'An error occurred during revenue forecasting: {str(exc)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
