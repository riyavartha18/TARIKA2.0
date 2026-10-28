"""
forecasting.py
--------------
Stock to Be Ordered — demand-driven replenishment.

Synchronised with the Demand Prediction module: it reuses the SAME trained ID3
decision tree and the SAME live tables (public.fact_product_analysis +
public.products, joined on product_key) so the demand tier shown here always
matches the Demand Forecasting dashboard. When the demand model is rebuilt
(its data fingerprint changes) the stock view reflects it automatically.

Replenishment calculation (unchanged):

    predicted_demand = round(units_sold)                 # demand actually observed
    current_stock    = products.available_quantity      # real stock on hand
    need_to_order    = max(0, predicted_demand - current_stock)
    demand_tier      = ID3 model prediction (High / Medium / Low)

Restock priority is derived only from those same values (no invented
thresholds):

    Low Priority : need_to_order == 0  (stock already covers predicted demand)
    Urgent       : need_to_order  > 0 AND (demand_tier == High OR current_stock <= 0)
    Soon         : every other product that still needs stock

`available_quantity` is stock only and never treated as demand. Missing values
default to zero, so zero stock / zero demand are handled safely.

Summary cards are aggregated from the same filtered query (one scan), so the
numbers always reflect the live data.

The query runs server-side and is paginated, so a ~90k product catalog stays
interactive (only one page of rows is transferred per request).
"""
from django.db import connection

from demand_prediction.engine import (
    DecisionTreeEngine,
    get_trained_model,
    demand_tier_sql,
)

# Columns the warehouse UI can sort on -> outer-query expressions (constants,
# never user input).
_SORTABLE = {
    'product_name': 'c.product_name',
    'category_name': 'c.category_name',
    'sub_category': 'c.sub_category',
    'current_stock': 'c.current_stock',
    'predicted_demand': 'c.predicted_demand',
    'need_to_order': 'c.need_to_order',
    'units_sold': 'c.units_sold',
}
_TIER_ORDER = "CASE c.demand_tier WHEN 'High' THEN 0 WHEN 'Medium' THEN 1 ELSE 2 END"
_PRIORITY_ORDER = "CASE c.priority WHEN 'Urgent' THEN 0 WHEN 'Soon' THEN 1 ELSE 2 END"

PRIORITY_LABELS = ('Urgent', 'Soon', 'Low Priority')


def _priority_expression():
    """SQL that classifies restock priority from already-computed columns."""
    return """
        CASE
            WHEN c.need_to_order = 0 THEN 'Low Priority'
            WHEN c.demand_tier = 'High' OR c.current_stock <= 0 THEN 'Urgent'
            ELSE 'Soon'
        END
    """


def _build_reason(priority, demand_tier, need_to_order, current_stock, predicted_demand):
    """Plain-language, data-anchored explanation for a single product."""
    stock_txt = 'out of stock' if current_stock <= 0 else f'{current_stock} in stock'
    if need_to_order <= 0:
        return (
            f'Current stock ({current_stock}) already covers predicted demand '
            f'({predicted_demand}) — no reorder needed.'
        )
    if priority == 'Urgent':
        if current_stock <= 0:
            return (
                f'{demand_tier} demand and out of stock — order {need_to_order} units now '
                f'(predicted demand {predicted_demand}).'
            )
        return (
            f'High demand with limited stock ({stock_txt}, predicted {predicted_demand}) — '
            f'reorder {need_to_order} units soon.'
        )
    # Soon
    return (
        f'{demand_tier} demand exceeds current stock ({stock_txt}) — '
        f'plan to reorder {need_to_order} units.'
    )


def run_stock_forecast(page=1, page_size=25, search='', tier='ALL',
                        category='ALL', sort='need_to_order', sort_dir='desc'):
    """Return one paginated page of demand-driven replenishment rows + totals."""
    model, _fingerprint, _rebuilt = get_trained_model()
    if not model.get('success'):
        return {'success': False, 'error': model.get('error', 'Demand model unavailable.')}

    cutoffs = model['cutoffs']
    tier_case_sql, tier_params = demand_tier_sql(cutoffs['low_max'], cutoffs['medium_max'])

    # Archived (soft-deleted) products never appear in the actionable list.
    where_clauses, where_params = ['d.is_active = TRUE'], []
    if search:
        where_clauses.append(
            "(LOWER(COALESCE(d.name, '')) LIKE %s "
            "OR LOWER(COALESCE(d.main_category, '')) LIKE %s "
            "OR LOWER(COALESCE(d.sub_category, '')) LIKE %s)"
        )
        like = f'%{search.lower()}%'
        where_params += [like, like, like]
    if category and category.upper() != 'ALL':
        where_clauses.append('d.main_category = %s')
        where_params.append(category)
    where_sql = ('WHERE ' + ' AND '.join(where_clauses)) if where_clauses else ''

    # Classified base query: demand tier (from the shared ID3 tree) plus the
    # reorder columns, all computed in SQL so no per-product rows ship to Python.
    # A LEFT JOIN surfaces any open (Pending) replenishment purchase order for
    # the product, so the actionable view can distinguish "needs ordering" from
    # "already ordered, awaiting receipt" and never re-orders the same need.
    base = f"""
        SELECT
            f.product_key,
            COALESCE(d.name, CONCAT('Product #', f.product_key)) AS product_name,
            COALESCE(d.main_category, 'Uncategorised') AS category_name,
            COALESCE(d.sub_category, '') AS sub_category,
            COALESCE(d.image, '') AS image,
            COALESCE(f.units_sold, 0)::float AS units_sold,
            COALESCE(d.available_quantity, 0)::int AS current_stock,
            ROUND(COALESCE(f.units_sold, 0))::int AS predicted_demand,
            GREATEST(0, ROUND(COALESCE(f.units_sold, 0))
                        - COALESCE(d.available_quantity, 0))::int AS need_to_order,
            COALESCE(po.pending_qty, 0)::int AS pending_qty,
            {tier_case_sql} AS demand_tier
        FROM fact_product_analysis f
        JOIN products d ON f.product_key = d.product_key
        LEFT JOIN (
            SELECT product_key,
                   SUM(GREATEST(0, quantity_ordered - quantity_received))::int AS pending_qty
            FROM replenishment_orders
            WHERE status = 'Pending'
            GROUP BY product_key
        ) po ON po.product_key = f.product_key
        {where_sql}
    """
    params = tier_params + where_params

    # Wrap the base so priority can reference the finished demand/stock columns
    # (keeps the tree CASE — and therefore its bound parameters — to one copy).
    enriched = f"SELECT c.*, {_priority_expression()} AS priority FROM ({base}) c"

    tier = (tier or 'ALL').upper()
    if tier not in ('HIGH', 'MEDIUM', 'LOW'):
        tier = 'ALL'

    sort_dir = 'ASC' if str(sort_dir).lower() == 'asc' else 'DESC'
    if sort == 'demand_tier':
        order_clause = (
            f"{_TIER_ORDER} {'ASC' if sort_dir == 'DESC' else 'DESC'}, c.need_to_order DESC"
        )
    elif sort == 'priority':
        order_clause = (
            f"{_PRIORITY_ORDER} {'ASC' if sort_dir == 'DESC' else 'DESC'}, c.need_to_order DESC"
        )
    else:
        order_expr = _SORTABLE.get(sort, 'c.need_to_order')
        order_clause = f"{order_expr} {sort_dir}, c.product_name ASC"

    with connection.cursor() as cursor:
        # One aggregate scan drives every summary card (tier + priority splits,
        # needs-replenishment, urgent, high-demand, low/zero stock, total need).
        cursor.execute(
            f"""
            SELECT demand_tier, priority,
                COUNT(*)::int AS cnt,
                COALESCE(SUM(need_to_order), 0)::int AS need_sum,
                COUNT(*) FILTER (WHERE need_to_order > 0)::int AS needs_repl,
                COUNT(*) FILTER (WHERE current_stock <= 0)::int AS zero_stock,
                COUNT(*) FILTER (WHERE current_stock <= 0 OR need_to_order > 0)::int AS low_or_zero
            FROM ({enriched}) q
            GROUP BY demand_tier, priority
            """,
            params,
        )
        tier_counts = {label: 0 for label in DecisionTreeEngine.CLASS_ORDER}
        priority_counts = {label: 0 for label in PRIORITY_LABELS}
        total_products = 0
        total_need = 0
        needs_replenishment = 0
        zero_stock = 0
        low_or_zero_stock = 0
        for tier_label, prio, cnt, need_sum, n_repl, n_zero, n_lzero in cursor.fetchall():
            tier_counts[tier_label] = tier_counts.get(tier_label, 0) + int(cnt)
            priority_counts[prio] = priority_counts.get(prio, 0) + int(cnt)
            total_products += int(cnt)
            total_need += int(need_sum)
            needs_replenishment += int(n_repl)
            zero_stock += int(n_zero)
            low_or_zero_stock += int(n_lzero)

        if tier != 'ALL':
            page_where = "WHERE c.demand_tier = %s"
            page_params = [tier.title()]  # High / Medium / Low
            filtered_total = tier_counts.get(tier.title(), 0)
        else:
            page_where = ""
            page_params = []
            filtered_total = total_products

        page_size = min(max(int(page_size), 1), 100)
        page = max(int(page), 1)
        offset = (page - 1) * page_size
        cursor.execute(
            f"SELECT * FROM ({enriched}) c {page_where} ORDER BY {order_clause} LIMIT %s OFFSET %s",
            params + page_params + [page_size, offset],
        )
        columns = [col[0] for col in cursor.description]
        rows = [dict(zip(columns, r)) for r in cursor.fetchall()]

    products = []
    for r in rows:
        current_stock = int(r['current_stock'] or 0)
        predicted_demand = int(r['predicted_demand'] or 0)
        need_to_order = int(r['need_to_order'] or 0)
        pending_qty = int(r.get('pending_qty') or 0)
        priority = r['priority']
        # Stock already on order still counts as replenished, so the amount that
        # genuinely needs ordering now excludes what a Pending PO already covers.
        order_now_qty = max(0, need_to_order - pending_qty)
        products.append({
            'product_key': r['product_key'],
            'product_id': str(r['product_key']),
            'product_name': r['product_name'],
            'category_name': r['category_name'],
            'sub_category': r['sub_category'],
            'image': r['image'] or '',
            'units_sold': float(r['units_sold'] or 0),
            'current_stock': current_stock,
            'predicted_demand': predicted_demand,
            'need_to_order': need_to_order,
            'pending_qty': pending_qty,
            'pending_order': pending_qty > 0,
            'order_now_qty': order_now_qty,
            'demand_tier': r['demand_tier'],
            'priority': priority,
            'reason': _build_reason(
                priority, r['demand_tier'], need_to_order, current_stock, predicted_demand
            ),
        })

    return {
        'success': True,
        'error': None,
        'forecast_month': None,
        'forecast_month_label': 'Live demand snapshot',
        'products': products,
        'pagination': {
            'page': page,
            'page_size': page_size,
            'total_filtered': filtered_total,
            'total_pages': (filtered_total + page_size - 1) // page_size if page_size else 1,
        },
        'summary': {
            'total_products': total_products,
            'tier_counts': tier_counts,
            'priority_counts': priority_counts,
            'needs_replenishment': needs_replenishment,
            'urgent': priority_counts.get('Urgent', 0),
            'high_demand': tier_counts.get('High', 0),
            'zero_stock': zero_stock,
            'low_or_zero_stock': low_or_zero_stock,
            'total_need_to_order': total_need,
        },
    }


def clean_demand_tier(value):
    """Normalise a requested tier to 'High' / 'Medium' / 'Low' (default High)."""
    label = str(value or '').strip().title()
    return label if label in ('High', 'Medium', 'Low') else 'High'


def fetch_demand_orderable(tier='High'):
    """All active products in the given demand tier that still need stock and
    are not already on order (no Pending purchase order).

    Used by the bulk "Order All High / Medium / Low Demand Products" actions.
    Each row's default order quantity is the existing recommended reorder
    quantity (``need_to_order``). Reuses the same shared ID3 tree as Demand
    Prediction, so the tier here always matches the forecasting dashboard.
    """
    tier = clean_demand_tier(tier)
    model, _fingerprint, _rebuilt = get_trained_model()
    if not model.get('success'):
        return {'success': False, 'error': model.get('error', 'Demand model unavailable.')}

    cutoffs = model['cutoffs']
    tier_case_sql, tier_params = demand_tier_sql(cutoffs['low_max'], cutoffs['medium_max'])

    query = f"""
        SELECT product_key, product_name, need_to_order, demand_tier
        FROM (
            SELECT
                f.product_key,
                COALESCE(d.name, CONCAT('Product #', f.product_key)) AS product_name,
                GREATEST(0, ROUND(COALESCE(f.units_sold, 0))
                            - COALESCE(d.available_quantity, 0))::int AS need_to_order,
                COALESCE(po.pending_qty, 0)::int AS pending_qty,
                {tier_case_sql} AS demand_tier
            FROM fact_product_analysis f
            JOIN products d ON f.product_key = d.product_key
            LEFT JOIN (
                SELECT product_key,
                       SUM(GREATEST(0, quantity_ordered - quantity_received))::int AS pending_qty
                FROM replenishment_orders
                WHERE status = 'Pending'
                GROUP BY product_key
            ) po ON po.product_key = f.product_key
            WHERE d.is_active = TRUE
        ) c
        WHERE c.demand_tier = %s AND c.need_to_order > 0 AND c.pending_qty = 0
        ORDER BY c.need_to_order DESC
    """
    with connection.cursor() as cursor:
        cursor.execute(query, list(tier_params) + [tier])
        columns = [col[0] for col in cursor.description]
        rows = [dict(zip(columns, r)) for r in cursor.fetchall()]

    items = [{
        'product_key': str(r['product_key']),
        'product_name': r['product_name'],
        'recommended_qty': int(r['need_to_order'] or 0),
        'demand_tier': r['demand_tier'],
    } for r in rows]

    return {'success': True, 'items': items, 'total_quantity': sum(i['recommended_qty'] for i in items)}


def fetch_high_demand_orderable():
    """Backwards-compatible alias for the High tier of ``fetch_demand_orderable``."""
    return fetch_demand_orderable('High')
