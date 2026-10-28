"""
views.py
--------
API view for Stock to Be Ordered — Warehouse Manager only.

GET /api/stock-to-be-ordered/
  -> Warehouse Manager authentication required
  -> Demand-driven replenishment, synchronised with the Demand Prediction model
     (reuses the trained ID3 tree + public.fact_product_analysis / products).
  -> Server-side paginated / searchable / sortable so the ~90k catalog stays fast.

Response:
{
    "forecast_month_label": "Live demand snapshot",
    "products": [
        {
            "product_key": "...", "product_name": "...",
            "category_name": "...", "sub_category": "...",
            "current_stock": 5,        <- products.available_quantity
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
from catalog.models import Product
from stock_to_be_ordered.services.forecasting import (
    run_stock_forecast,
    fetch_demand_orderable,
    clean_demand_tier,
)
from stock_to_be_ordered.services import replenishment
from stock_to_be_ordered.services.replenishment import ReplenishmentError
from stock_to_be_ordered.serializers import (
    ReplenishmentOrderSerializer,
    ReplenishmentReceiveSerializer,
    ReplenishmentAmendSerializer,
    ReplenishmentOrderOutSerializer,
    BulkDemandOrderSerializer,
)


def _actor_id(request):
    user = getattr(request, 'user', None)
    if not user:
        return None
    return getattr(user, 'email', None) or getattr(user, 'auth_user_id', None) or getattr(user, 'id', None)


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
    current_stock is the real products.available_quantity.
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
                    "SELECT DISTINCT main_category FROM products "
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


class ReplenishmentOrderView(APIView):
    """Place a replenishment order for one product.

    POST /api/stock-to-be-ordered/order/
        { "product_key": "P123", "quantity": 25 }
    Records a Pending purchase order. Does NOT change available stock and refuses
    a second order while an equivalent one is still pending.
    """
    permission_classes = [IsAuthenticatedUser, IsWarehouseManager]

    def post(self, request):
        serializer = ReplenishmentOrderSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        product_key = serializer.validated_data['product_key']
        quantity = serializer.validated_data['quantity']
        try:
            po = replenishment.create_replenishment_order(
                product_key=product_key,
                quantity=quantity,
                created_by=_actor_id(request),
            )
        except ReplenishmentError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:  # noqa: BLE001
            return Response({'detail': f'Could not place order: {str(exc)}'},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        # The reorder committed the purchase order AND the stock increment in one
        # transaction. Read the persisted value back from the database so the
        # client refreshes from the authoritative server number, not local state.
        available_quantity = (
            Product.objects
            .filter(product_id=str(product_key))
            .values_list('available_quantity', flat=True)
            .first()
        )
        return Response({
            'message': f'Ordered {int(quantity)} unit(s). '
                       f'Available stock is now {int(available_quantity or 0)}.',
            'added_quantity': int(quantity),
            'available_quantity': available_quantity,
            'order': ReplenishmentOrderOutSerializer(po).data,
        }, status=status.HTTP_201_CREATED)


class HighDemandPreviewView(APIView):
    """GET /api/stock-to-be-ordered/high-demand/ — preview the bulk order."""
    permission_classes = [IsAuthenticatedUser, IsWarehouseManager]

    def get(self, request):
        result = fetch_demand_orderable('High')
        if not result.get('success'):
            return Response({'error': result.get('error', 'Demand model unavailable.')},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response({
            'items': result['items'],
            'product_count': len(result['items']),
            'total_quantity': result['total_quantity'],
        }, status=status.HTTP_200_OK)


class HighDemandOrderView(APIView):
    """POST /api/stock-to-be-ordered/order-high-demand/ — confirm the bulk order."""
    permission_classes = [IsAuthenticatedUser, IsWarehouseManager]

    def post(self, request):
        try:
            summary = replenishment.order_all_demand('High', created_by=_actor_id(request))
        except ReplenishmentError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:  # noqa: BLE001
            return Response({'detail': f'Could not place bulk order: {str(exc)}'},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response({'message': 'High-demand replenishment orders placed.', **summary},
                        status=status.HTTP_201_CREATED)


class DemandPreviewView(APIView):
    """GET /api/stock-to-be-ordered/demand-preview/?tier=Medium

    Preview the products a bulk "Order All <tier> Demand Products" action would
    order: active, still short of stock, and not already covered by a Pending
    purchase order. Quantities are the existing recommended reorder amounts.
    """
    permission_classes = [IsAuthenticatedUser, IsWarehouseManager]

    def get(self, request):
        tier = clean_demand_tier(request.query_params.get('tier'))
        result = fetch_demand_orderable(tier)
        if not result.get('success'):
            return Response({'error': result.get('error', 'Demand model unavailable.')},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response({
            'tier': tier,
            'items': result['items'],
            'product_count': len(result['items']),
            'total_quantity': result['total_quantity'],
        }, status=status.HTTP_200_OK)


class DemandOrderView(APIView):
    """POST /api/stock-to-be-ordered/demand-order/  { "tier": "Medium", "product_keys": [...] }

    Confirm a bulk replenishment order for one demand tier. ``product_keys``
    optionally narrows the order to the reviewed selection. No stock changes:
    placing a PO only records the request to the supplier."""
    permission_classes = [IsAuthenticatedUser, IsWarehouseManager]

    def post(self, request):
        serializer = BulkDemandOrderSerializer(data=request.data or {})
        if not serializer.is_valid():
            return Response({'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        tier = serializer.validated_data['tier']
        try:
            summary = replenishment.order_all_demand(
                tier,
                created_by=_actor_id(request),
                product_keys=serializer.validated_data.get('product_keys'),
            )
        except ReplenishmentError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:  # noqa: BLE001
            return Response({'detail': f'Could not place bulk order: {str(exc)}'},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response(
            {'message': f'{tier}-demand replenishment orders placed.', **summary},
            status=status.HTTP_201_CREATED,
        )


class ReplenishmentOrderDetailView(APIView):
    """GET/PUT/DELETE /api/stock-to-be-ordered/orders/<po_key>/

    Inspect, amend or cancel a supplier purchase order before the goods arrive.
    Editing the proposed reorder quantity never touches products.available_quantity -
    only a receipt does. Once any units were received the order refuses edits
    and the caller must receive the balance or cancel instead.
    """
    permission_classes = [IsAuthenticatedUser, IsWarehouseManager]

    def get(self, request, po_key):
        po = (
            replenishment.ReplenishmentOrder.objects
            .filter(po_key=str(po_key).strip()).first()
        )
        if not po:
            return Response({'detail': 'Replenishment order not found.'},
                            status=status.HTTP_404_NOT_FOUND)
        return Response({'order': ReplenishmentOrderOutSerializer(po).data},
                        status=status.HTTP_200_OK)

    def put(self, request, po_key):
        serializer = ReplenishmentAmendSerializer(data=request.data or {})
        if not serializer.is_valid():
            return Response({'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        try:
            po = replenishment.update_replenishment_order(
                po_key, quantity=serializer.validated_data['quantity'],
            )
        except ReplenishmentError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:  # noqa: BLE001
            return Response({'detail': f'Could not update order: {str(exc)}'},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response({
            'message': f'Order {po.po_key} updated to {po.quantity_ordered} unit(s). '
                       'Stock is unchanged until the goods are received.',
            'order': ReplenishmentOrderOutSerializer(po).data,
        }, status=status.HTTP_200_OK)

    def delete(self, request, po_key):
        try:
            po = replenishment.cancel_replenishment_order(po_key)
        except ReplenishmentError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:  # noqa: BLE001
            return Response({'detail': f'Could not cancel order: {str(exc)}'},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response({
            'message': f'Order {po.po_key} cancelled. Available stock is unchanged.',
            'order': ReplenishmentOrderOutSerializer(po).data,
        }, status=status.HTTP_200_OK)


class ReplenishmentReceiveView(APIView):
    """POST /api/stock-to-be-ordered/orders/<po_key>/receive/ — record receipt.

    This is the only action that increases products.available_quantity."""
    permission_classes = [IsAuthenticatedUser, IsWarehouseManager]

    def post(self, request, po_key):
        serializer = ReplenishmentReceiveSerializer(data=request.data or {})
        if not serializer.is_valid():
            return Response({'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        try:
            po, add_qty, new_stock = replenishment.receive_replenishment_order(
                po_key,
                received_qty=serializer.validated_data.get('quantity_received'),
            )
        except ReplenishmentError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:  # noqa: BLE001
            return Response({'detail': f'Could not record receipt: {str(exc)}'},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response({
            'message': f'Received {add_qty} unit(s). Available stock is now {int(new_stock)}.',
            'added_quantity': add_qty,
            'available_quantity': new_stock,
            'order': ReplenishmentOrderOutSerializer(po).data,
        }, status=status.HTTP_200_OK)


class ReplenishmentOrderListView(APIView):
    """GET /api/stock-to-be-ordered/orders/?status=&product_key= — purchase orders."""
    permission_classes = [IsAuthenticatedUser, IsWarehouseManager]

    def get(self, request):
        status_filter = (request.query_params.get('status') or '').strip().title()
        if status_filter not in ('Pending', 'Received', 'Cancelled'):
            status_filter = None
        orders = replenishment.list_replenishment_orders(
            status=status_filter,
            product_key=(request.query_params.get('product_key') or '').strip() or None,
        )
        return Response({
            'orders': ReplenishmentOrderOutSerializer(orders, many=True).data,
            'count': len(orders),
        }, status=status.HTTP_200_OK)
