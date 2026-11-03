import time

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db import connection

from accounts.permissions import IsAuthenticatedUser, IsAdmin
from catalog.normalize import normalize_category, sql_norm_expr
from demand_prediction import engine, inventory_metrics as metrics
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
    Inventory Velocity Analysis — served from the cached summary table.

    Every active product (never a truncated 50) is classified from real
    delivered-order sales in the last 30 days:

      FAST MOVING  – days of stock <= 15  (needs frequent replenishment)
      NORMAL       – days of stock <= 60
      SLOW         – days of stock <= 180
      NON MOVING   – zero valid sales in the window, or 180+ days of stock

    Metrics per product: current_stock, sales_last_30_days (SUM of delivered
    orders.quantity in the window), avg_daily_sales (window units / window
    days) and days_of_stock (CEIL(stock / avg daily); NULL = no sales, which
    the UI shows as “∞ / No Sales”).

    The heavy aggregation runs once per TTL (or on invalidation) inside
    demand_prediction.inventory_metrics; requests here are indexed reads with
    server-side search / filter / sort / pagination, so the whole ~90k catalog
    is pageable without re-aggregating orders on every render.
    """
    permission_classes = [IsAuthenticatedUser, IsAdmin]

    # Whitelisted sort keys -> internal ORDER BY SQL (never user input).
    # The default is the required fixed display order: Fast -> Normal -> Slow ->
    # Not Moving, and highest sales first within each tier (backed by the
    # (movement_rank, sales_last_30_days DESC) index).
    _ORDER_BY = {
        'movement': "v.movement_rank ASC, v.sales_last_30_days DESC",
        'sales_last_30_days': "v.sales_last_30_days DESC, v.current_stock DESC",
        'avg_daily_sales': "v.avg_daily_sales DESC, v.sales_last_30_days DESC",
        'days_of_stock': ("v.days_of_stock ASC NULLS LAST, "
                          "v.sales_last_30_days DESC"),
        'current_stock': "v.current_stock DESC",
        'product_name': "v.product_name ASC",
    }

    def get(self, request):
        t0 = time.perf_counter()
        try:
            force = request.query_params.get('refresh', '').lower() in ('1', 'true')
            state = metrics.ensure_fresh(force=force)

            page = max(1, int(request.query_params.get('page', 1) or 1))
            page_size = int(request.query_params.get('page_size', 50) or 50)
            page_size = min(max(page_size, 1), 200)

            search = request.query_params.get('search', '').strip().lower()
            category = request.query_params.get('category', '').strip()
            movement = request.query_params.get('movement_status', '').strip().upper()
            sort_key = request.query_params.get('sort', 'movement').strip()
            if movement not in metrics.MOVEMENT_LABELS:
                movement = ''

            where = []
            params = []
            has_search = bool(search)
            has_category = bool(category and category.upper() != 'ALL')
            if search:
                where.append(
                    "(LOWER(COALESCE(v.product_name, '')) LIKE %s "
                    "OR LOWER(COALESCE(v.main_category, '')) LIKE %s "
                    "OR LOWER(COALESCE(v.sub_category, '')) LIKE %s)")
                like = f'%{search}%'
                params += [like, like, like]
            if has_category:
                where.append(f"{sql_norm_expr('v.main_category')} = %s")
                params.append(normalize_category(category))
            if movement:
                where.append("v.movement_status = %s")
                params.append(movement)
            where_sql = ('WHERE ' + ' AND '.join(where)) if where else ''
            order_sql = self._ORDER_BY.get(sort_key, self._ORDER_BY['movement'])

            # Summary tiles come straight from the cached state row: they only
            # change when the metrics table is rebuilt, so no per-request scan.
            st_summary = (state or {}).get('summary', {})
            total_products = int((state or {}).get('product_count', 0))
            summary = {
                'total_products': total_products,
                'fast_moving': int(st_summary.get('fast_moving', 0)),
                'normal_moving': int(st_summary.get('normal_moving', 0)),
                'slow_moving': int(st_summary.get('slow_moving', 0)),
                'not_moving': int(st_summary.get('not_moving', 0)),
                'out_of_stock': int(st_summary.get('out_of_stock', 0)),
                'total_window_units': int(st_summary.get('window_units', 0)),
            }

            # The filtered total is derivable from the cache in two cheap cases
            # and only needs a COUNT scan for a genuine search / category.
            if not where_sql:
                filtered_total = total_products
            elif movement and not has_search and not has_category:
                _tier_key = {metrics.MOVEMENT_FAST: 'fast_moving',
                             metrics.MOVEMENT_NORMAL: 'normal_moving',
                             metrics.MOVEMENT_SLOW: 'slow_moving',
                             metrics.MOVEMENT_NOT: 'not_moving'}[movement]
                filtered_total = summary[_tier_key]
            else:
                with connection.cursor() as cursor:
                    cursor.execute(
                        f"SELECT COUNT(*)::int FROM {metrics.METRICS_TABLE} v {where_sql}",
                        params)
                    filtered_total = int(cursor.fetchone()[0])

            total_pages = (filtered_total + page_size - 1) // page_size
            page = min(page, max(total_pages, 1))

            # The requested page is a pure index+LIMIT scan. It carries no
            # window function: COUNT(*) OVER() would force a full 88k scan and
            # erase the index benefit for the default (unfiltered) view.
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT v.product_key, v.product_name, v.main_category,
                           v.sub_category, v.current_stock, v.sales_last_30_days,
                           v.movement_status
                    FROM {metrics.METRICS_TABLE} v
                    {where_sql}
                    ORDER BY {order_sql}
                    LIMIT %s OFFSET %s
                    """,
                    params + [page_size, (page - 1) * page_size])
                cols = [c[0] for c in cursor.description]
                rows = [dict(zip(cols, r)) for r in cursor.fetchall()]

            items = []
            for r in rows:
                stock = float(r['current_stock'] or 0)
                units = int(r['sales_last_30_days'] or 0)
                items.append({
                    'product_key': r['product_key'],
                    'product_name': r['product_name'] or 'Unknown Product',
                    'category_name': r['main_category'] or '',
                    'sub_category': r['sub_category'] or '',
                    'current_stock': int(stock),
                    'sales_last_30_days': units,
                    'movement_status': r['movement_status'],
                })

            def _fmt(date_text):
                # 'YYYY-MM-DD' -> 'DD-MM-YYYY' for display, same as before.
                if not date_text:
                    return None
                y, m, d = date_text.split('-')
                return f'{d}-{m}-{y}'

            return Response({
                'success': True,
                'analysis_date': _fmt(state and state['window_end']),
                'sales_window_start': _fmt(state and state['window_start']),
                'sales_window_days': metrics.SALES_WINDOW_DAYS,
                # Data-driven, transparent tier boundaries: the sales-quantity
                # cut points (units in the window) from the seller distribution.
                'thresholds': {
                    'basis': 'sales_quantity',
                    'window_days': metrics.SALES_WINDOW_DAYS,
                    'fast_percentile': metrics.FAST_PERCENTILE,
                    'normal_percentile': metrics.NORMAL_PERCENTILE,
                    'fast_cut': (state or {}).get('thresholds', {}).get('fast_cut'),
                    'normal_cut': (state or {}).get('thresholds', {}).get('normal_cut'),
                    'not_moving_rule': 'zero units sold in the window',
                },
                'summary': summary,
                'items': items,
                'pagination': {
                    'page': page,
                    'page_size': page_size,
                    'total_filtered': filtered_total,
                    'total_pages': total_pages,
                },
                'cache': {
                    'refreshed_at': state and state['refreshed_at'],
                    'ttl_seconds': metrics.METRICS_TTL_SECONDS,
                },
                'timing': {'view_ms': round((time.perf_counter() - t0) * 1000, 1)},
            }, status=status.HTTP_200_OK)

        except Exception as exc:
            return Response(
                {"error": f"Error generating slow inventory analysis: {str(exc)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


