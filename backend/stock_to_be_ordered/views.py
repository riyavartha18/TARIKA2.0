"""
views.py
--------
API views for Stock to Be Ordered — Warehouse Manager only.

GET /api/stock-to-be-ordered/
  → Warehouse Manager authentication required
  → Runs OLS Multiple Linear Regression pipeline
  → Returns next-month demand forecast with current stock and need-to-order

Response format:
{
    "forecast_month": "2026-10",
    "forecast_month_label": "October 2026",
    "products": [
        {
            "product_key": 1,
            "product_id": "P001",
            "product_name": "Product A",
            "color": "Black",
            "size": "M",
            "current_stock": 5,
            "predicted_demand": 12,
            "need_to_order": 7
        },
        ...
    ]
}
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from accounts.permissions import IsAuthenticatedUser, IsWarehouseManager
from stock_to_be_ordered.services.forecasting import run_stock_forecast


class StockToBeOrderedView(APIView):
    """
    Stock to Be Ordered — Next-Month Demand Forecasting via Multiple Linear Regression.

    Access: Warehouse Manager only.

    GET /api/stock-to-be-ordered/

    Runs OLS regression across the existing Data Warehouse
    (fact_demand, dim_time, dim_product, dim_category) and returns
    product-wise predicted demand vs. current stock for the next calendar month.

    current_stock comes from dim_product.current_stock.
    need_to_order = max(0, predicted_demand - current_stock)
    """
    permission_classes = [IsAuthenticatedUser, IsWarehouseManager]

    def get(self, request):
        try:
            # Run the full forecasting pipeline (optimised: bulk queries, no N+1)
            result = run_stock_forecast()

            if not result.get('success'):
                return Response(
                    {'error': result.get('error', 'Forecasting pipeline failed.')},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            # Optional search filter (client-side preferred, but support server-side too)
            search = request.query_params.get('search', '').strip().lower()

            products = result['products']

            if search:
                products = [
                    p for p in products
                    if search in (p.get('product_name') or '').lower()
                ]

            return Response({
                'forecast_month': result['forecast_month'],
                'forecast_month_label': result['forecast_month_label'],
                'products': products,
            }, status=status.HTTP_200_OK)

        except Exception as exc:
            return Response(
                {'error': f'An error occurred in the Stock to Be Ordered pipeline: {str(exc)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
