"""READ-ONLY live check of the Customer CLV table payload against Neon.

Runs the exact same query path the /api/clv/customers endpoint uses and
cross-checks each displayed value against an independent raw SQL read.
Nothing is written: SELECTs only.
"""
import os

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.db import connection  # noqa: E402

from clv import calc, queries, utils  # noqa: E402
from rfm_analysis import segment_store  # noqa: E402

LIMIT = queries.__dict__.get('LIMIT', 50)

state = segment_store.get_state()
cutoff = state.analysis_date if state else None
print(f'reporting cutoff (rfm_analysis_state) = {cutoff}')

matrix = queries.fetch_cohort_matrix()
print(f'cohort cells = {len(matrix.get("cells") or {})}  horizon = {matrix.get("horizon_date")}')
retention = calc.retention_report(matrix, cutoff)
print(f'retention status = {retention["status"]}  mature_ages = {len(retention.get("mature_ages") or [])}')
future_expr = calc.future_clv_sql(retention)
print(f'future_sql built = {bool(future_expr)}')

agg = queries.fetch_clv_aggregates(future_sql=future_expr)
queries.set_tier_boundaries(agg['high_value'], agg['medium_value'])
print(f'population avg_future_clv (aggregate) = {agg["avg_future_clv"]}  '
      f'tier boundaries high/medium = {agg["high_value"]}/{agg["medium_value"]}')

# ---- page 1 exactly as the endpoint reads it (50 rows, server-side sort) ----
rows, total = queries.fetch_customer_page(
    segment=None, tier='ALL', search='', order_by='historical_clv', direction='desc',
    limit=LIMIT, offset=0, future_sql=future_expr)
derived = [calc.derive_page_row(r, cutoff, agg['high_value'], agg['medium_value'], retention)
           for r in rows]
print(f'\ntotal customers = {total}  page rows = {len(derived)}  '
      f'total_pages = {(total + LIMIT - 1) // LIMIT}')

# ---- independent raw SQL cross-check for the first 8 displayed rows ----
sample = derived[:8]
ids = [d['customer_id'] for d in sample]
with connection.cursor() as cur:
    cur.execute(
        f'SELECT cs.customer_id, cu.customer_name, cs.monetary, cs.frequency, '
        f'({future_expr}) AS future_sql_value, cs.first_purchase_date, cs.last_purchase_date '
        f'FROM rfm_customer_segments cs '
        f'LEFT JOIN public.customers cu ON cu.customer_id = cs.customer_id '
        f'WHERE cs.customer_id = ANY(%s)', [ids])
    cols = [c.name for c in cur.description]
    raw = {r[0]: dict(zip(cols, r)) for r in cur.fetchall()}

print('\ncustomer_id | name (db) | hist CLV (db monetary) | future CLV (python row) '
      '| future (SQL expr) | tier | match')
all_ok = True
for d in sample:
    r = raw[d['customer_id']]
    db_future = float(r['future_sql_value']) if r['future_sql_value'] is not None else None
    py_future = d['future_clv']
    name_ok = (r['customer_name'] or None) == (d['customer_name'] or None)
    hist_ok = round(float(r['monetary']), 2) == d['historical_clv']
    fut_ok = ((db_future is None and py_future is None)
              or (db_future is not None and py_future is not None
                  and abs(db_future - py_future) < 0.01))
    ok = name_ok and hist_ok and fut_ok
    all_ok = all_ok and ok
    print(f'{d["customer_id"]} | {r["customer_name"]} | {float(r["monetary"]):.2f} '
          f'| {py_future} | {db_future} | {d["clv_tier"]} | {"OK" if ok else "MISMATCH"}')
print(f'\nSQL expression == per-row Python Future CLV for the sample: {all_ok}')

# ---- distinct per-customer values (no aggregate echoed back) ----
futures = [d['future_clv'] for d in derived if d['future_clv'] is not None]
distinct = len(set(futures))
print(f'rows with a Future CLV = {len(futures)}/{len(derived)}; '
      f'distinct values = {distinct}; equals the aggregate avg for every row: '
      f'{sum(1 for f in futures if f == agg["avg_future_clv"])}/{len(futures)}')

# ---- pagination + search still server-side ----
rows2, total2 = queries.fetch_customer_page(
    segment=None, tier='ALL', search='', order_by='historical_clv', direction='desc',
    limit=LIMIT, offset=LIMIT, future_sql=future_expr)
ids1 = {r['customer_id'] for r in rows}
ids2 = {r['customer_id'] for r in rows2}
print(f'page 2 rows = {len(rows2)}  overlap with page 1 = {len(ids1 & ids2)}  total agrees = {total2 == total}')

one_id = sample[0]['customer_id']
found, ftotal = queries.fetch_customer_page(
    segment=None, tier='ALL', search=one_id, order_by='customer_id', direction='asc',
    limit=LIMIT, offset=0, future_sql=future_expr)
print(f'search by ID "{one_id}": {ftotal} row(s) -> {[r["customer_id"] for r in found]}')

high, high_total = queries.fetch_customer_page(
    segment=None, tier='High Value', search='', order_by='future_clv', direction='desc',
    limit=5, offset=0, future_sql=future_expr)
print(f'High Value tier + sort by Future CLV desc: total={high_total} '
      f'-> {[ (r["customer_id"], str(r["monetary"])) for r in high ]}')

lo, lo_total = queries.fetch_customer_page(
    segment=None, tier='ALL', search='', order_by='historical_clv', direction='desc',
    limit=LIMIT, offset=0, future_sql=future_expr, future_min=1000, future_max=50000)
lo_futures = [calc.derive_page_row(r, cutoff, agg['high_value'], agg['medium_value'], retention)['future_clv']
              for r in lo]
in_range = [f for f in lo_futures if f is not None]
print(f'Future CLV range 1000..50000: total={lo_total} rows={len(lo)} '
      f'min/max of returned rows = {min(in_range) if in_range else None}/'
      f'{max(in_range) if in_range else None} '
      f'(all within range: {all(1000 <= f <= 50000 for f in in_range)})')

print(f'\nutils.exclude_negative_final_price = {utils.exclude_negative_final_price()}')
print(f'eligible delivery statuses = {utils.eligible_delivery_statuses()}')
