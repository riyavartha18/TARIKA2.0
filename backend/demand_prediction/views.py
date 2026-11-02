import time
from datetime import datetime, timedelta

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db import connection

from accounts.permissions import IsAuthenticatedUser, IsAdmin
from catalog.normalize import normalize_category, sql_norm_expr
from demand_prediction import engine
from demand_prediction.engine import DecisionTreeEngine


# Valid time buckets for the sales-history graph (whitelisted, never raw input).
_GRANULARITY = {'day': 'day', 'week': 'week', 'month': 'month'}


class ProductSalesHistoryView(APIView):
    """GET /api/demand/history/?product_key=...&granularity=day|week|month

    Aggregated units sold over time for ONE product, straight from real
    ``public.orders`` -- never mock data. Uses the same completed-sale rule as
    units_sold (delivery_status = 'Delivered'; Returned / In Transit excluded)
    and sums ``orders.quantity`` so a multi-unit order counts its units. Only
    the selected product's history is aggregated server-side. ``purchase_date``
    is stored as TEXT 'DD-MM-YYYY', so only well-formed dates are converted.
    A product with no delivered sales returns an empty ``points`` list (the
    client shows an empty state).
    """
    permission_classes = [IsAuthenticatedUser, IsAdmin]

    def get(self, request):
        product_key = (request.query_params.get('product_key') or '').strip()
        if not product_key:
            return Response({'error': 'product_key is required.'},
                            status=status.HTTP_400_BAD_REQUEST)
        gran = _GRANULARITY.get((request.query_params.get('granularity') or 'month').strip().lower(), 'month')

        # `gran` is from the fixed whitelist above, so the interpolation is safe.
        query = f"""
            SELECT to_char(date_trunc('{gran}', to_date(purchase_date, 'DD-MM-YYYY')), 'YYYY-MM-DD') AS period,
                   SUM(quantity)::bigint AS units
            FROM orders
            WHERE product_id = %s
              AND delivery_status = 'Delivered'
              AND purchase_date ~ '^[0-9]{{2}}-[0-9]{{2}}-[0-9]{{4}}$'
            GROUP BY 1
            ORDER BY 1
        """
        try:
            with connection.cursor() as cursor:
                cursor.execute(query, [product_key])
                rows = cursor.fetchall()
        except Exception as exc:  # noqa: BLE001
            return Response({'error': f'Could not load sales history: {type(exc).__name__}'},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        points = [{'period': p, 'units': int(u or 0)} for p, u in rows]
        return Response({
            'product_key': product_key,
            'granularity': gran,
            'points': points,
            'total_units': sum(pt['units'] for pt in points),
            'period_count': len(points),
        }, status=status.HTTP_200_OK)


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
            cutoffs = model['cutoffs']
            low_max = cutoffs['low_max']
            medium_max = cutoffs['medium_max']
            # Authoritative demand tier = data-driven units_sold terciles. The
            # engagement-features tree has no signal here (see engine), so it is
            # not used as the per-product label.
            demand_case_sql, case_params = engine.demand_tier_sql(low_max, medium_max)

            page = max(1, int(request.query_params.get('page', 1) or 1))
            page_size = int(request.query_params.get('page_size', 12) or 12)
            page_size = min(max(page_size, 1), 50)

            search = request.query_params.get('search', '').strip()
            demand_level = request.query_params.get('demand_level', 'ALL').strip().upper()
            category = request.query_params.get('category', 'ALL').strip()
            sort_key = request.query_params.get('sort', 'demand').strip()
            sort_dir = request.query_params.get('dir', 'desc').strip().lower()
            sort_dir = 'ASC' if sort_dir == 'asc' else 'DESC'

            where_clauses = ['d.is_active = TRUE']  # hide archived products
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
                # Case- and whitespace-insensitive category filter.
                where_clauses.append(f"{sql_norm_expr('d.main_category')} = %s")
                where_params.append(normalize_category(category))

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
                    COALESCE(f.units_sold, 0)::float AS units_sold,
                    COALESCE(f.total_sales, 0)::float AS total_sales,
                    COALESCE(d.name, CONCAT('Product #', f.product_key)) AS product_name,
                    COALESCE(d.main_category, 'Uncategorised') AS main_category,
                    COALESCE(d.sub_category, '') AS sub_category,
                    d.image AS image,
                    d.discount_price AS discount_price,
                    COALESCE(NULLIF(regexp_replace(d.actual_price, '[^0-9.]', '', 'g'), '')::float8,
                             d.initial_price) AS selling_price,
                    d.available_quantity AS available_quantity,
                    {demand_case_sql} AS predicted_demand
                FROM fact_product_analysis f
                JOIN products d ON f.product_key = d.product_key
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

            # Enrich each card with a sales-based rationale + action. The tier
            # comes from the same units_sold terciles the SQL uses, so the badge
            # always matches the filtering/ordering applied server-side.
            items = []
            for r in rows:
                units = float(r['units_sold'] or 0)
                prediction = engine.units_sold_tier(units, low_max, medium_max)
                steps = [
                    f"Units sold (delivered): {units:g}",
                    f"Demand terciles: Low \u2264 {low_max:g} < Medium \u2264 {medium_max:g} < High",
                    f"Demand tier: {prediction}",
                ]
                items.append({
                    'product_key': r['product_key'],
                    'product_name': r['product_name'],
                    'main_category': r['main_category'],
                    'sub_category': r['sub_category'],
                    'image': r['image'],
                    'discount_price': r['discount_price'],
                    # Final discounted selling price (actual_price TEXT, parsed).
                    'selling_price': r['selling_price'],
                    'wishlist_count': int(r['wishlist_count'] or 0),
                    'cart_count': int(r['cart_count'] or 0),
                    'units_sold': units,
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
                # One entry per case/whitespace-insensitive category (a stable
                # display name is the MIN of the trimmed raw values).
                cursor.execute(
                    "SELECT MIN(TRIM(main_category)) AS main_category "
                    "FROM products "
                    "WHERE main_category IS NOT NULL AND TRIM(main_category) <> '' "
                    "GROUP BY LOWER(TRIM(main_category)) "
                    "ORDER BY 1"
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
    Slow-Moving Inventory Analysis.

    The original implementation joined the ``inventory``, ``order_items``,
    ``categories`` and ``warehouses`` tables and keyed stock by a per-warehouse
    ``inventory.stock_quantity``. None of those tables exist in the connected
    ``public`` schema (verified against the live database), and stock now lives
    directly on ``products.available_quantity``. Velocity analysis would need
    per-product sales over time, which the current single-snapshot ``orders``
    table (no ``order_date``/``order_items``) cannot supply.

    Rather than return fabricated figures, the feature is clearly retired with an
    explicit 503. Demand-driven replenishment (Stock to Be Ordered) is the
    supported, schema-correct replacement and already surfaces low/zero-stock and
    high-demand products.
    """
    permission_classes = [IsAuthenticatedUser, IsAdmin]

    def get(self, request):
        try:
            # Parse date range parameters (defaults to last 30 days)
            end_param = request.query_params.get('end_date')
            start_param = request.query_params.get('start_date')
            today = datetime.utcnow().date()
            if end_param:
                try:
                    end_date = datetime.strptime(end_param, '%d-%m-%Y').date()
                except Exception:
                    return Response({'error': 'Invalid end_date format, expected DD-MM-YYYY.'},
                                    status=status.HTTP_400_BAD_REQUEST)
            else:
                end_date = today
            if start_param:
                try:
                    start_date = datetime.strptime(start_param, '%d-%m-%Y').date()
                except Exception:
                    return Response({'error': 'Invalid start_date format, expected DD-MM-YYYY.'},
                                    status=status.HTTP_400_BAD_REQUEST)
            else:
                start_date = end_date - timedelta(days=30)

            # Query parameters
            group_by = (request.query_params.get('group_by') or 'product').strip().lower()
            allowed_groups = {'product', 'sub_category', 'main_category', 'overall'}
            if group_by not in allowed_groups:
                group_by = 'product'

            search = request.query_params.get('search', '').strip()
            category = request.query_params.get('category', '').strip()
            sub_category = request.query_params.get('sub_category', '').strip()
            movement_status = request.query_params.get('movement_status', '').strip().upper()

            limit = int(request.query_params.get('limit', 100) or 100)
            offset = int(request.query_params.get('offset', 0) or 0)

            # Build product filter WHERE clause
            product_where_clauses = []
            product_sql_params = []
            if search:
                product_where_clauses.append(
                    "(LOWER(p.name) LIKE %s OR LOWER(p.main_category) LIKE %s OR LOWER(p.sub_category) LIKE %s)"
                )
                like = f"%{search.lower()}%"
                product_sql_params.extend([like, like, like])
            if category and category.upper() != 'ALL':
                product_where_clauses.append("LOWER(p.main_category) = %s")
                product_sql_params.append(category.lower())
            if sub_category and sub_category.upper() != 'ALL':
                product_where_clauses.append("LOWER(p.sub_category) = %s")
                product_sql_params.append(sub_category.lower())
            where_sql = ''
            if product_where_clauses:
                where_sql = 'WHERE ' + ' AND '.join(product_where_clauses)

            # Build SELECT and GROUP clauses per aggregation level
            if group_by == 'product':
                select_clause = (
                    "p.product_key, p.name AS product_name, p.main_category, p.sub_category, "
                    "p.available_quantity AS stock, "
                    "COALESCE(p.discount_price, NULLIF(regexp_replace(p.actual_price, '[^0-9.]', '', 'g'), '')::float8) AS price, "
                    "oa.units_sold, oa.first_sale, oa.last_sale"
                )
                group_clause = ""
            elif group_by == 'sub_category':
                select_clause = (
                    "p.sub_category, SUM(p.available_quantity) AS stock, "
                    "COALESCE(p.discount_price, NULLIF(regexp_replace(p.actual_price, '[^0-9.]', '', 'g'), '')::float8) AS price, "
                    "SUM(oa.units_sold) AS units_sold, MIN(oa.first_sale) AS first_sale, MAX(oa.last_sale) AS last_sale"
                )
                group_clause = "GROUP BY p.sub_category"
            elif group_by == 'main_category':
                select_clause = (
                    "p.main_category, SUM(p.available_quantity) AS stock, "
                    "COALESCE(p.discount_price, NULLIF(regexp_replace(p.actual_price, '[^0-9.]', '', 'g'), '')::float8) AS price, "
                    "SUM(oa.units_sold) AS units_sold, MIN(oa.first_sale) AS first_sale, MAX(oa.last_sale) AS last_sale"
                )
                group_clause = "GROUP BY p.main_category"
            else:  # overall
                select_clause = (
                    "SUM(p.available_quantity) AS stock, "
                    "COALESCE(p.discount_price, NULLIF(regexp_replace(p.actual_price, '[^0-9.]', '', 'g'), '')::float8) AS price, "
                    "SUM(oa.units_sold) AS units_sold, MIN(oa.first_sale) AS first_sale, MAX(oa.last_sale) AS last_sale"
                )
                group_clause = ""

            # Build the full SQL with an aggregated orders sub‑query (oa)
            order_agg_sql = (
                "SELECT o.product_id AS product_key, "
                "SUM(o.quantity)::bigint AS units_sold, "
                "MIN(to_date(o.purchase_date, 'DD-MM-YYYY')) AS first_sale, "
                "MAX(to_date(o.purchase_date, 'DD-MM-YYYY')) AS last_sale "
                "FROM orders o "
                "WHERE o.delivery_status = 'Delivered' "
                "AND o.purchase_date ~ '^[0-9]{2}-[0-9]{2}-[0-9]{4}$' "
                "AND to_date(o.purchase_date, 'DD-MM-YYYY') BETWEEN %s AND %s "
                "GROUP BY o.product_id"
            )
            sql_params = [start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')]

            sql = f"""
                SELECT {select_clause}
                FROM products p
                LEFT JOIN ({order_agg_sql}) oa ON p.product_key = oa.product_key
                {where_sql}
                {group_clause}
                ORDER BY units_sold DESC
                LIMIT %s OFFSET %s
            """
            sql_params.extend(product_sql_params)
            sql_params.extend([limit, offset])

            with connection.cursor() as cursor:
                cursor.execute(sql, sql_params)
                cols = [c[0] for c in cursor.description]
                rows = [dict(zip(cols, r)) for r in cursor.fetchall()]

            # Post‑process rows and build summary
            days_span = (end_date - start_date).days or 1
            items = []
            summary = {
                'analysis_date': datetime.utcnow().strftime('%d-%m-%Y'),
                'analysis_period_days': days_span,
                'total_products': 0,
                'total_inventory': 0,
                'very_slow': 0,
                'slow': 0,
                'normal': 0,
                'out_of_stock': 0,
                'total_stock_units': 0,
                'total_inventory_value': 0,
            }
            for r in rows:
                stock = float(r.get('stock') or 0)
                units = float(r.get('units_sold') or 0)
                price = float(r.get('price') or 0)
                avg_daily = units / days_span if days_span else 0
                days_of_stock = stock / avg_daily if avg_daily else None
                # movement classification
                if stock <= 0:
                    movement = 'OUT OF STOCK'
                elif units == 0:
                    movement = 'VERY SLOW'
                elif days_of_stock is not None:
                    if days_of_stock > 180:
                        movement = 'VERY SLOW'
                    elif days_of_stock > 60:
                        movement = 'SLOW'
                    else:
                        movement = 'NORMAL'
                else:
                    movement = 'NORMAL'
                # recommended action
                if movement == 'OUT OF STOCK':
                    recommendation = 'Order restock'
                elif movement in ('VERY SLOW', 'SLOW'):
                    recommendation = 'Consider promotion / discount'
                else:
                    recommendation = 'Maintain stock'
                item = {
                    'product_key': r.get('product_key'),
                    'product_name': r.get('product_name'),
                    'image': r.get('image'),
                    'category_name': r.get('main_category'),
                    'main_category': r.get('main_category'),
                    'sub_category': r.get('sub_category'),
                    'stock': int(stock),
                    'units_sold': int(units),
                    'last_sale_date': r.get('last_sale').strftime('%d-%m-%Y') if r.get('last_sale') else None,
                    'average_daily_sales': round(avg_daily, 2),
                    'days_of_stock': round(days_of_stock, 2) if days_of_stock is not None else None,
                    'inventory_value': round(stock * price, 2),
                    'movement_status': movement,
                    'recommended_action': recommendation,
                }
                items.append(item)
                # update summary counters
                summary['total_products'] += 1
                summary['total_inventory'] += 1
                summary['total_stock_units'] += stock
                summary['total_inventory_value'] += stock * price
                if movement == 'OUT OF STOCK':
                    summary['out_of_stock'] += 1
                elif movement == 'VERY SLOW':
                    summary['very_slow'] += 1
                elif movement == 'SLOW':
                    summary['slow'] += 1
                elif movement == 'NORMAL':
                    summary['normal'] += 1

            return Response({
                'success': True,
                'summary': summary,
                'items': items,
                'pagination': {'limit': limit, 'offset': offset, 'total': summary['total_products']},
            }, status=status.HTTP_200_OK)
        except Exception as exc:
            return Response({
                'error': f'Error generating slow inventory analysis: {str(exc)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            end_param = request.query_params.get('end_date')
            start_param = request.query_params.get('start_date')
            today = datetime.utcnow().date()
            if end_param:
                try:
                    end_date = datetime.strptime(end_param, '%d-%m-%Y').date()
                except Exception:
                    return Response({'error': 'Invalid end_date format, expected DD-MM-YYYY.'},
                                    status=status.HTTP_400_BAD_REQUEST)
            else:
                end_date = today
            if start_param:
                try:
                    start_date = datetime.strptime(start_param, '%d-%m-%Y').date()
                except Exception:
                    return Response({'error': 'Invalid start_date format, expected DD-MM-YYYY.'},
                                    status=status.HTTP_400_BAD_REQUEST)
            else:
                start_date = end_date - timedelta(days=30)

            # Query parameters
            group_by = (request.query_params.get('group_by') or 'product').strip().lower()
            allowed_groups = {'product', 'sub_category', 'main_category', 'overall'}
            if group_by not in allowed_groups:
                group_by = 'product'

            search = request.query_params.get('search', '').strip()
            category = request.query_params.get('category', '').strip()
            sub_category = request.query_params.get('sub_category', '').strip()
            movement_status = request.query_params.get('movement_status', '').strip().upper()

            limit = int(request.query_params.get('limit', 100) or 100)
            offset = int(request.query_params.get('offset', 0) or 0)

            # Build base WHERE clauses for orders (only delivered, valid dates, date range)
            order_where_clauses = [
                "o.delivery_status = 'Delivered'",
                "o.purchase_date ~ '^[0-9]{2}-[0-9]{2}-[0-9]{4}$'",
                "to_date(o.purchase_date, 'DD-MM-YYYY') BETWEEN %s AND %s",
            ]
            order_sql_params = [
                start_date.strftime('%Y-%m-%d'),
                end_date.strftime('%Y-%m-%d'),
            ]
            # Product filters (search / category / sub_category)
            product_where_clauses = []
            product_sql_params = []
            if search:
                product_where_clauses.append(
                    "(LOWER(p.name) LIKE %s OR LOWER(p.main_category) LIKE %s OR LOWER(p.sub_category) LIKE %s)"
                )
                like = f"%{search.lower()}%"
                product_sql_params.extend([like, like, like])
            if category and category.upper() != 'ALL':
                product_where_clauses.append("LOWER(p.main_category) = %s")
                product_sql_params.append(category.lower())
            if sub_category and sub_category.upper() != 'ALL':
                product_where_clauses.append("LOWER(p.sub_category) = %s")
                product_sql_params.append(sub_category.lower())

            where_sql = ''
            if product_where_clauses:
                where_sql = 'WHERE ' + ' AND '.join(product_where_clauses)

            # Select & group clauses per aggregation level
            # Select & group clauses per aggregation level using pre‑aggregated orders
            if group_by == 'product':
                select_clause = (
                    "p.product_key, p.name AS product_name, p.main_category, p.sub_category, "
                    "p.available_quantity AS stock, "
                    "COALESCE(p.discount_price, NULLIF(regexp_replace(p.actual_price, '[^0-9.]', '', 'g'), '')::float8) AS price, "
                    "oa.units_sold, oa.first_sale, oa.last_sale"
                )
                group_clause = ""
            elif group_by == 'sub_category':
                select_clause = (
                    "p.sub_category, SUM(p.available_quantity) AS stock, "
                    "COALESCE(p.discount_price, NULLIF(regexp_replace(p.actual_price, '[^0-9.]', '', 'g'), '')::float8) AS price, "
                    "SUM(oa.units_sold) AS units_sold, MIN(oa.first_sale) AS first_sale, MAX(oa.last_sale) AS last_sale"
                )
                group_clause = "GROUP BY p.sub_category"
            elif group_by == 'main_category':
                select_clause = (
                    "p.main_category, SUM(p.available_quantity) AS stock, "
                    "COALESCE(p.discount_price, NULLIF(regexp_replace(p.actual_price, '[^0-9.]', '', 'g'), '')::float8) AS price, "
                    "SUM(oa.units_sold) AS units_sold, MIN(oa.first_sale) AS first_sale, MAX(oa.last_sale) AS last_sale"
                )
                group_clause = "GROUP BY p.main_category"
            else:  # overall
                select_clause = (
                    "SUM(p.available_quantity) AS stock, "
                    "COALESCE(p.discount_price, NULLIF(regexp_replace(p.actual_price, '[^0-9.]', '', 'g'), '')::float8) AS price, "
                    "SUM(oa.units_sold) AS units_sold, MIN(oa.first_sale) AS first_sale, MAX(oa.last_sale) AS last_sale"
                )
                group_clause = ""

            sql = f"""
                SELECT {select_clause}
                FROM products p
                LEFT JOIN orders o ON p.product_key = o.product_key
                {where_sql}
                {group_clause}
                ORDER BY units_sold DESC
                LIMIT %s OFFSET %s
            """
            sql_params.extend([limit, offset])

            with connection.cursor() as cursor:
                cursor.execute(sql, sql_params)
                cols = [c[0] for c in cursor.description]
                rows = [dict(zip(cols, r)) for r in cursor.fetchall()]

            # Post‑process rows
            days_span = (end_date - start_date).days or 1
            items = []
            # Summary counters
            summary = {
                'total_inventory': 0,
                'very_slow': 0,
                'slow': 0,
                'normal': 0,
                'out_of_stock': 0,
                'total_stock_units': 0,
                'total_inventory_value': 0,
                'date_range': f"{start_date.strftime('%d-%m-%Y')} to {end_date.strftime('%d-%m-%Y')}",
            }
            for r in rows:
                stock = float(r.get('stock') or 0)
                units = float(r.get('units_sold') or 0)
                price = float(r.get('price') or 0)
                avg_daily = units / days_span if days_span else 0
                days_of_stock = stock / avg_daily if avg_daily else None
                # movement classification
                if stock <= 0:
                    movement = 'OUT OF STOCK'
                elif units == 0:
                    movement = 'VERY SLOW'
                elif days_of_stock is not None:
                    if days_of_stock > 180:
                        movement = 'VERY SLOW'
                    elif days_of_stock > 60:
                        movement = 'SLOW'
                    else:
                        movement = 'NORMAL'
                else:
                    movement = 'NORMAL'
                # recommended action
                if movement == 'OUT OF STOCK':
                    recommendation = 'Order restock'
                elif movement in ('VERY SLOW', 'SLOW'):
                    recommendation = 'Consider promotion / discount'
                else:
                    recommendation = 'Maintain stock'
                item = {
                    'product_key': r.get('product_key'),
                    'product_name': r.get('product_name'),
                    'category_name': r.get('main_category'),
                    'main_category': r.get('main_category'),
                    'sub_category': r.get('sub_category'),
                    'stock': int(stock),
                    'units_sold': int(units),
                    'last_sale_date': r.get('last_sale').strftime('%d-%m-%Y') if r.get('last_sale') else None,
                    'average_daily_sales': round(avg_daily, 2),
                    'days_of_stock': round(days_of_stock, 2) if days_of_stock is not None else None,
                    'inventory_value': round(stock * price, 2),
                    'movement_status': movement,
                    'recommended_action': recommendation,
                }
                items.append(item)
                # update summary
                summary['total_inventory'] += 1
                summary['total_stock_units'] += stock
                summary['total_inventory_value'] += stock * price
                if movement == 'OUT OF STOCK':
                    summary['out_of_stock'] += 1
                elif movement == 'VERY SLOW':
                    summary['very_slow'] += 1
                elif movement == 'SLOW':
                    summary['slow'] += 1
                elif movement == 'NORMAL':
                    summary['normal'] += 1
            # Add pagination totals
            summary['total'] = summary['total_inventory']


            return Response({
                'success': True,
                'group_by': group_by,
                'summary': summary,
                'items': items,
                'pagination': {'limit': limit, 'offset': offset},
            }, status=status.HTTP_200_OK)
        except Exception as exc:
            return Response({
                'error': f'Error generating slow inventory analysis: {str(exc)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
