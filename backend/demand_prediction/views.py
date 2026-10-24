import time
from datetime import datetime, timedelta

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db import connection

from accounts.permissions import IsAuthenticatedUser, IsAdmin
from demand_prediction import engine
from demand_prediction.engine import DecisionTreeEngine


class DemandPredictionAnalyticsView(APIView):
    """
    Aggregate analytics for the Demand Forecasting dashboard.

    Returns the ID3 model explanation only (summary, entropy, information
    gains, best split, decision tree and the demand-class distribution). It
    never ships per-product rows -- those come from the paged products
    endpoint -- so the response stays small and cached.
    """
    permission_classes = [IsAuthenticatedUser, IsAdmin]

    def get(self, request):
        try:
            force = request.query_params.get('refresh', '').lower() in ('1', 'true')
            results = engine.build_analytics_summary(force_refresh=force)

            if not results.get('success'):
                return Response(
                    {'error': results.get('error', 'Failed to calculate demand predictions.')},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
            return Response(results, status=status.HTTP_200_OK)

        except Exception as exc:
            return Response(
                {'error': f'An error occurred during demand prediction calculation: {str(exc)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# Whitelist of sortable columns -> safe SQL ORDER BY expressions that reference
# the aliases produced by the classified sub-select. These are internal
# constants (never user input).
_SORTABLE = {
    'units_sold': 'c.units_sold',
    'total_sales': 'c.total_sales',
    'purchase_count': 'c.purchase_count',
    'cart_count': 'c.cart_count',
    'wishlist_count': 'c.wishlist_count',
    'available_quantity': 'c.available_quantity',
    'product_name': 'c.product_name',
}
_DEMAND_ORDER = (
    "CASE c.predicted_demand WHEN 'High' THEN 0 WHEN 'Medium' THEN 1 ELSE 2 END"
)


class DemandPredictionProductsView(APIView):
    """
    Server-side paged / filtered product demand predictions.

    Only the requested page of products is fetched from Supabase (a few dozen
    rows), keeping the response well under a second even for the ~90k catalog.
    The trained ID3 tree is applied server-side (via a SQL CASE derived from the
    cached tree) so filtering and ordering by demand happen in the database, and
    each returned card carries a plain-language decision-path explanation plus
    the real available_quantity (kept clearly separate from demand).
    """
    permission_classes = [IsAuthenticatedUser, IsAdmin]

    def get(self, request):
        try:
            t0 = time.perf_counter()

            model, _fingerprint, _rebuilt = engine.get_trained_model()
            if not model.get('success'):
                return Response(
                    {'error': model.get('error', 'Demand model unavailable.')},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            tree = model['decision_tree']
            demand_case_sql, case_params = engine.tree_to_sql_case(tree)

            page = max(1, int(request.query_params.get('page', 1) or 1))
            page_size = int(request.query_params.get('page_size', 12) or 12)
            page_size = min(max(page_size, 1), 50)

            search = request.query_params.get('search', '').strip()
            demand_level = request.query_params.get('demand_level', 'ALL').strip().upper()
            category = request.query_params.get('category', 'ALL').strip()
            sort_key = request.query_params.get('sort', 'demand').strip()
            sort_dir = request.query_params.get('dir', 'desc').strip().lower()
            sort_dir = 'ASC' if sort_dir == 'asc' else 'DESC'

            where_clauses = []
            where_params = []
            if search:
                where_clauses.append(
                    "(LOWER(COALESCE(d.name, '')) LIKE %s "
                    "OR LOWER(COALESCE(d.main_category, '')) LIKE %s "
                    "OR LOWER(COALESCE(d.sub_category, '')) LIKE %s)"
                )
                like = f'%{search.lower()}%'
                where_params += [like, like, like]
            if category and category.upper() != 'ALL':
                where_clauses.append("d.main_category = %s")
                where_params.append(category)

            # Normalise demand_level to a validated value.
            if demand_level not in ('HIGH', 'MEDIUM', 'LOW'):
                demand_level = 'ALL'

            where_sql = ('WHERE ' + ' AND '.join(where_clauses)) if where_clauses else ''

            # One classified sub-select is reused for both the filtered class
            # distribution (aggregate) and the paged rows -- no duplicated
            # requests, no per-row Python work over the whole catalog.
            inner = f"""
                SELECT
                    f.product_key,
                    COALESCE(f.wishlist_count, 0)::int AS wishlist_count,
                    COALESCE(f.cart_count, 0)::int AS cart_count,
                    COALESCE(f.purchase_count, 0)::int AS purchase_count,
                    COALESCE(f.units_sold, 0)::float AS units_sold,
                    COALESCE(f.total_sales, 0)::float AS total_sales,
                    COALESCE(d.name, CONCAT('Product #', f.product_key)) AS product_name,
                    COALESCE(d.main_category, 'Uncategorised') AS main_category,
                    COALESCE(d.sub_category, '') AS sub_category,
                    d.image AS image,
                    d.discount_price AS discount_price,
                    d.available_quantity AS available_quantity,
                    {demand_case_sql} AS predicted_demand
                FROM fact_product_analysis f
                JOIN dim_product d ON f.product_key = d.product_key
                {where_sql}
            """
            inner_params = case_params + where_params

            # Ordering: default groups by demand tier (High first) then by the
            # strongest demand evidence (units_sold). Within a single tier, or
            # for an explicit numeric column, sort by that column.
            if sort_key == 'demand' or sort_key not in _SORTABLE:
                order_clause = f"{_DEMAND_ORDER} {'ASC' if sort_dir == 'DESC' else 'DESC'}, c.units_sold DESC"
            else:
                order_clause = f"{_SORTABLE[sort_key]} {sort_dir}"

            with connection.cursor() as cursor:
                # Filtered class distribution. When there are no search/category
                # filters we reuse the cached whole-catalog distribution instead
                # of re-scanning all ~90k rows -- identical result, one less scan.
                if not where_clauses:
                    cached = model['predicted_distribution']
                    filtered_counts = [(label, cached.get(label, 0)) for label in DecisionTreeEngine.CLASS_ORDER]
                else:
                    cursor.execute(
                        f"SELECT predicted_demand, COUNT(*)::int FROM ({inner}) c GROUP BY predicted_demand",
                        inner_params,
                    )
                    filtered_counts = cursor.fetchall()
                total_filtered = sum(int(cnt) for _, cnt in filtered_counts)

                if demand_level != 'ALL':
                    page_where = "WHERE c.predicted_demand = %s"
                    page_params = [demand_level.title()]
                    # Within a single tier, rank by demand strength.
                    page_order = "ORDER BY c.units_sold DESC"
                else:
                    page_where = ""
                    page_params = []
                    page_order = f"ORDER BY {order_clause}"

                cursor.execute(
                    f"SELECT * FROM ({inner}) c {page_where} {page_order} LIMIT %s OFFSET %s",
                    inner_params + page_params + [page_size, (page - 1) * page_size],
                )
                columns = [col[0] for col in cursor.description]
                rows = [dict(zip(columns, r)) for r in cursor.fetchall()]

            # Enrich each card with a decision-path explanation + action.
            items = []
            for r in rows:
                sample = {
                    'wishlist_count': float(r['wishlist_count'] or 0),
                    'cart_count': float(r['cart_count'] or 0),
                    'purchase_count': float(r['purchase_count'] or 0),
                }
                prediction, steps = engine.classify_sample(tree, sample)
                items.append({
                    'product_key': r['product_key'],
                    'product_name': r['product_name'],
                    'main_category': r['main_category'],
                    'sub_category': r['sub_category'],
                    'image': r['image'],
                    'discount_price': r['discount_price'],
                    'wishlist_count': int(r['wishlist_count'] or 0),
                    'cart_count': int(r['cart_count'] or 0),
                    'purchase_count': int(r['purchase_count'] or 0),
                    'units_sold': float(r['units_sold'] or 0),
                    'total_sales': float(r['total_sales'] or 0),
                    'available_quantity': float(r['available_quantity'] or 0),
                    'predicted_demand': prediction,
                    'decision_path': steps,
                    'recommended_action': engine.recommended_action(
                        prediction, r['available_quantity'], r['units_sold']
                    ),
                })

            filtered_distribution = {label: 0 for label in DecisionTreeEngine.CLASS_ORDER}
            for cls, cnt in filtered_counts:
                filtered_distribution[cls] = filtered_distribution.get(cls, 0) + int(cnt)

            return Response({
                'items': items,
                'pagination': {
                    'page': page,
                    'page_size': page_size,
                    'total_filtered': total_filtered,
                    'total_pages': (total_filtered + page_size - 1) // page_size,
                    'filtered_distribution': filtered_distribution,
                },
                'timing': {'view_ms': round((time.perf_counter() - t0) * 1000)},
            }, status=status.HTTP_200_OK)

        except Exception as exc:
            return Response(
                {'error': f'An error occurred during demand prediction product fetch: {str(exc)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class CategoryFilterView(APIView):
    """Distinct main categories for the demand forecasting filter dropdown."""
    permission_classes = [IsAuthenticatedUser, IsAdmin]

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

            today = datetime.now().date()
            thirty_days_ago = today - timedelta(days=30)

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

            items = []
            for row in rows:
                product_id = row[0]
                product_name = row[1]
                category_name = row[2]
                warehouse_id = row[3]
                warehouse_name = row[4]
                current_stock = int(row[5] or 0)
                sales_last_30 = int(row[6] or 0)

                avg_daily_sales = round(sales_last_30 / 30.0, 2) if sales_last_30 > 0 else 0.0

                if avg_daily_sales > 0:
                    days_of_stock = round(current_stock / avg_daily_sales, 1)
                else:
                    days_of_stock = None

                if sales_last_30 == 0 or (days_of_stock is not None and days_of_stock > 180):
                    movement_status = 'VERY SLOW'
                    recommended_action = 'Consider discount, bundle or stock transfer'
                elif days_of_stock is not None and days_of_stock > 60:
                    movement_status = 'SLOW'
                    recommended_action = 'Consider promotional campaign'
                else:
                    movement_status = 'NORMAL'
                    recommended_action = 'No action required'

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
                filtered = [i for i in filtered if i['movement_status'] == movement_filter]

            if warehouse_filter and warehouse_filter.lower() != 'all':
                filtered = [i for i in filtered if str(i['warehouse_id']) == warehouse_filter]

            very_slow_count = sum(1 for i in items if i['movement_status'] == 'VERY SLOW')
            slow_count = sum(1 for i in items if i['movement_status'] == 'SLOW')
            normal_count = sum(1 for i in items if i['movement_status'] == 'NORMAL')

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
