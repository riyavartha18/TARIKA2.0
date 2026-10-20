from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from accounts.permissions import IsAuthenticatedUser, IsAdmin
from demand_prediction.engine import DecisionTreeEngine
from django.db import connection
from datetime import datetime, timedelta


class DemandPredictionAnalyticsView(APIView):
    """
    API View for Demand Forecasting & Prediction module.
    
    Provides:
    - Executive summary & metrics
    - Entropy (Shannon Entropy calculation)
    - Information Gain for each feature (units_sold, cart_quantity, wishlist_count, discount_percentage, notify_me_count)
    - Best Split parameters (feature, threshold, Information Gain)
    - Decision Tree visual structure
    - Product-wise demand predictions (High, Medium, Low)
    """
    permission_classes = [IsAuthenticatedUser, IsAdmin]

    def get(self, request):
        try:
            results = DecisionTreeEngine.run_pipeline()

            if not results.get('success'):
                return Response({
                    'error': results.get('error', 'Failed to calculate demand predictions.')
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # Optional query filters for product predictions
            search = request.query_params.get('search', '').strip().lower()
            demand_level = request.query_params.get('demand_level', '').strip().upper()
            category = request.query_params.get('category', '').strip().lower()

            predictions = results['product_predictions']

            if search:
                predictions = [
                    p for p in predictions 
                    if search in p['product_name'].lower() or search in p['category_name'].lower()
                ]

            if demand_level and demand_level != 'ALL':
                predictions = [
                    p for p in predictions 
                    if p['predicted_demand'].upper() == demand_level
                ]

            if category and category != 'all':
                predictions = [
                    p for p in predictions 
                    if category in p['category_name'].lower()
                ]

            # Return response with filtered predictions and complete analytical metrics
            response_data = {
                'metadata': results['metadata'],
                'summary': results['summary'],
                'entropy': results['entropy'],
                'information_gains': results['information_gains'],
                'best_split': results['best_split'],
                'decision_tree': results['decision_tree'],
                'product_predictions': predictions,
                'total_filtered_products': len(predictions)
            }

            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'error': f'An error occurred during demand prediction calculation: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SlowMovingInventoryView(APIView):
    """
    API View for Slow-Moving Inventory Analysis.
    
    Calculates inventory velocity for each product-warehouse combination using
    existing tables: inventory, order_items, orders, products, categories, warehouses.
    
    Classification:
    - VERY SLOW: sales_last_30_days == 0 OR days_of_stock > 180
    - SLOW: days_of_stock > 60 AND <= 180
    - NORMAL: days_of_stock <= 60
    """
    permission_classes = [IsAuthenticatedUser, IsAdmin]

    def get(self, request):
        try:
            cursor = connection.cursor()

            # Calculate the date 30 days ago for sales window
            today = datetime.now().date()
            thirty_days_ago = today - timedelta(days=30)

            # Query: For each product+warehouse, get current stock and sales in last 30 days
            query = """
                SELECT
                    inv.product_id,
                    COALESCE(p.product_name, CONCAT('Product #', inv.product_id)) AS product_name,
                    COALESCE(c.category_name, 'Uncategorized') AS category_name,
                    inv.warehouse_id,
                    COALESCE(w.warehouse_name, CONCAT('Warehouse #', inv.warehouse_id)) AS warehouse_name,
                    COALESCE(inv.stock_quantity, 0) AS current_stock,
                    COALESCE(sales.total_sold, 0) AS sales_last_30_days
                FROM inventory inv
                LEFT JOIN products p ON inv.product_id = p.product_id
                LEFT JOIN categories c ON p.category_id = c.category_id
                LEFT JOIN warehouses w ON inv.warehouse_id = w.warehouse_id
                LEFT JOIN (
                    SELECT
                        oi.product_id,
                        o.warehouse_id,
                        COALESCE(SUM(oi.quantity), 0) AS total_sold
                    FROM order_items oi
                    JOIN orders o ON oi.order_id = o.order_id
                    WHERE o.order_date >= %s
                      AND LOWER(COALESCE(o.order_status, '')) NOT IN ('cancelled', 'returned', 'failed')
                    GROUP BY oi.product_id, o.warehouse_id
                ) sales ON inv.product_id = sales.product_id AND inv.warehouse_id = sales.warehouse_id
                WHERE COALESCE(inv.stock_quantity, 0) > 0
                ORDER BY inv.product_id, inv.warehouse_id
            """
            cursor.execute(query, [str(thirty_days_ago)])
            rows = cursor.fetchall()

            # Build result list with calculations
            items = []
            for row in rows:
                product_id = row[0]
                product_name = row[1]
                category_name = row[2]
                warehouse_id = row[3]
                warehouse_name = row[4]
                current_stock = int(row[5] or 0)
                sales_last_30 = int(row[6] or 0)

                # Calculate average daily sales (safe division)
                avg_daily_sales = round(sales_last_30 / 30.0, 2) if sales_last_30 > 0 else 0.0

                # Calculate days of stock (safe division by zero)
                if avg_daily_sales > 0:
                    days_of_stock = round(current_stock / avg_daily_sales, 1)
                else:
                    days_of_stock = None  # Infinite / no sales

                # Classify movement status
                if sales_last_30 == 0 or (days_of_stock is not None and days_of_stock > 180):
                    movement_status = 'VERY SLOW'
                    recommended_action = 'Consider discount, bundle or stock transfer'
                elif days_of_stock is not None and days_of_stock > 60:
                    movement_status = 'SLOW'
                    recommended_action = 'Consider promotional campaign'
                else:
                    movement_status = 'NORMAL'
                    recommended_action = 'No action required'

                # For display: if no sales, show ∞ for days_of_stock
                display_days = days_of_stock if days_of_stock is not None else 999999

                items.append({
                    'product_id': product_id,
                    'product_name': product_name,
                    'category_name': category_name,
                    'warehouse_id': warehouse_id,
                    'warehouse_name': warehouse_name,
                    'current_stock': current_stock,
                    'sales_last_30_days': sales_last_30,
                    'avg_daily_sales': avg_daily_sales,
                    'days_of_stock': display_days,
                    'movement_status': movement_status,
                    'recommended_action': recommended_action,
                })

            # Apply optional query filters
            search = request.query_params.get('search', '').strip().lower()
            movement_filter = request.query_params.get('movement_status', '').strip().upper()
            warehouse_filter = request.query_params.get('warehouse_id', '').strip()

            filtered = items

            if search:
                filtered = [
                    i for i in filtered
                    if search in i['product_name'].lower() or search in i['category_name'].lower()
                ]

            if movement_filter and movement_filter != 'ALL':
                filtered = [
                    i for i in filtered
                    if i['movement_status'] == movement_filter
                ]

            if warehouse_filter and warehouse_filter.lower() != 'all':
                filtered = [
                    i for i in filtered
                    if str(i['warehouse_id']) == warehouse_filter
                ]

            # Build summary counts from FULL (unfiltered) data
            very_slow_count = sum(1 for i in items if i['movement_status'] == 'VERY SLOW')
            slow_count = sum(1 for i in items if i['movement_status'] == 'SLOW')
            normal_count = sum(1 for i in items if i['movement_status'] == 'NORMAL')

            # Get unique warehouses for filter dropdown
            warehouses_list = sorted(list(set(
                (i['warehouse_id'], i['warehouse_name']) for i in items
            )), key=lambda x: x[1])

            response_data = {
                'summary': {
                    'total_inventory': len(items),
                    'very_slow': very_slow_count,
                    'slow': slow_count,
                    'normal': normal_count,
                },
                'warehouses': [
                    {'warehouse_id': wid, 'warehouse_name': wname}
                    for wid, wname in warehouses_list
                ],
                'items': filtered,
                'total_filtered': len(filtered),
                'analysis_date': str(today),
                'sales_window_start': str(thirty_days_ago),
            }

            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'error': f'An error occurred during slow-moving inventory analysis: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
