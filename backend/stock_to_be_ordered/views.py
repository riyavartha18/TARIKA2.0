"""
views.py
--------
API view for Stock to Be Ordered — Warehouse Manager only.

GET /api/stock-to-be-ordered/
  -> Warehouse Manager authentication required
  -> Demand-driven replenishment, synchronised with the Demand Prediction model
     (reuses the trained ID3 tree + public.fact_product_analysis / dim_product).
  -> Server-side paginated / searchable / sortable so the ~90k catalog stays fast.

Response:
{
    "forecast_month_label": "Live demand snapshot",
    "products": [
        {
            "product_key": "...", "product_name": "...",
            "category_name": "...", "sub_category": "...",
            "current_stock": 5,        <- dim_product.available_quantity
            "predicted_demand": 12,    <- round(units_sold)
            "need_to_order": 7,        <- max(0, predicted_demand - current_stock)
            "demand_tier": "High"      <- shared ID3 prediction
        }, ...
    ],
    "pagination": {...},
    "summary": {...}
}
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db import connection

from accounts.permissions import IsAuthenticatedUser, IsWarehouseManager
from stock_to_be_ordered.services.forecasting import run_stock_forecast


def _as_int(value, default):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


class StockToBeOrderedView(APIView):
    """
    Stock to Be Ordered — demand-driven replenishment.

    Access: Warehouse Manager only. need_to_order = max(0, predicted_demand -
    current_stock), where predicted_demand reflects the demand model and
    current_stock is the real dim_product.available_quantity.
    """
    permission_classes = [IsAuthenticatedUser, IsWarehouseManager]

    def get(self, request):
        try:
            qp = request.query_params
            result = run_stock_forecast(
                page=_as_int(qp.get('page'), 1),
                page_size=_as_int(qp.get('page_size'), 25),
                search=(qp.get('search') or '').strip(),
                tier=(qp.get('demand_tier') or qp.get('tier') or 'ALL').strip().upper(),
                category=(qp.get('category') or 'ALL').strip(),
                sort=(qp.get('sort') or 'need_to_order').strip(),
                sort_dir=(qp.get('dir') or qp.get('sort_dir') or 'desc').strip(),
            )

            if not result.get('success'):
                return Response(
                    {'error': result.get('error', 'Stock forecasting pipeline failed.')},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            return Response(result, status=status.HTTP_200_OK)

        except Exception as exc:
            return Response(
                {'error': f'An error occurred in the Stock to Be Ordered pipeline: {str(exc)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class StockCategoriesView(APIView):
    """Distinct product categories for the Stock to Be Ordered filter."""
    permission_classes = [IsAuthenticatedUser, IsWarehouseManager]

    def get(self, request):
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT DISTINCT main_category FROM dim_product "
                    "WHERE main_category IS NOT NULL AND main_category <> '' "
                    "ORDER BY main_category"
                )
                categories = [row[0] for row in cursor.fetchall()]
            return Response({'categories': categories}, status=status.HTTP_200_OK)
        except Exception as exc:
            return Response(
                {'error': f'An error occurred while loading categories: {str(exc)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
