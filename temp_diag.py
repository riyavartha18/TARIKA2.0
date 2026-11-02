import os, sys, django
# ensure settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
# load django
django.setup()
from django.db import connection

def exec_query(sql, params=None):
    with connection.cursor() as cursor:
        cursor.execute(sql, params or [])
        columns = [col[0] for col in cursor.description]
        rows = cursor.fetchall()
        return [dict(zip(columns, row)) for row in rows]

# 1. Count products
print('COUNT_PRODUCTS')
res = exec_query('SELECT COUNT(*) AS cnt FROM products')
print(res)

# 2. Count orders
print('COUNT_ORDERS')
res = exec_query('SELECT COUNT(*) AS cnt FROM orders')
print(res)

# 3. Delivery status distribution
print('DELIVERY_STATUS')
res = exec_query('SELECT delivery_status, COUNT(*) AS cnt FROM orders GROUP BY delivery_status')
print(res)

# 4. Purchase date distribution (top 20)
print('PURCHASE_DATE_DISTRIB')
res = exec_query('SELECT purchase_date, COUNT(*) AS cnt FROM orders GROUP BY purchase_date ORDER BY cnt DESC LIMIT 20')
print(res)

# 5. 10 product aggregate (all delivered orders, no date filter)
print('PRODUCT_AGGREGATE')
sql = '''
SELECT p.product_key, p.name, p.available_quantity,
       COUNT(o.id) FILTER (WHERE TRIM(LOWER(o.delivery_status)) = 'delivered') AS delivered_order_count,
       SUM(o.quantity) FILTER (WHERE TRIM(LOWER(o.delivery_status)) = 'delivered') AS total_delivered_qty,
       MAX(CASE WHEN TRIM(LOWER(o.delivery_status)) = 'delivered' THEN o.purchase_date END) AS latest_delivered_purchase_date
FROM products p
LEFT JOIN orders o ON p.product_key = o.product_id
GROUP BY p.product_key, p.name, p.available_quantity
LIMIT 10;
'''
res = exec_query(sql)
print(res)

# 6. Overall earliest and latest purchase dates across all orders (any status)
print('EARLIEST_LATEST_DATES')
res = exec_query('SELECT MIN(purchase_date) AS earliest, MAX(purchase_date) AS latest FROM orders')
print(res)

