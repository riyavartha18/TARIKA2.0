import os, django, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
django.setup()
from django.db import connection
cur = connection.cursor()
cur.execute('''SELECT p.product_key, p.name, p.available_quantity,
       COUNT(o.id) AS delivered_orders,
       SUM(CASE WHEN o.delivery_status='Delivered' THEN o.quantity ELSE 0 END) AS total_delivered_qty,
       MAX(o.purchase_date) AS latest_purchase_date,
       SUM(CASE WHEN o.delivery_status='Delivered' AND to_date(o.purchase_date, 'DD-MM-YYYY') BETWEEN (CURRENT_DATE - INTERVAL '30 days') AND CURRENT_DATE THEN o.quantity ELSE 0 END) AS units_last_30,
       AVG(CASE WHEN o.delivery_status='Delivered' AND to_date(o.purchase_date, 'DD-MM-YYYY') BETWEEN (CURRENT_DATE - INTERVAL '30 days') AND CURRENT_DATE THEN o.quantity END) AS avg_daily_last_30,
       (p.available_quantity::float / NULLIF(AVG(CASE WHEN o.delivery_status='Delivered' AND to_date(o.purchase_date, 'DD-MM-YYYY') BETWEEN (CURRENT_DATE - INTERVAL '30 days') AND CURRENT_DATE THEN o.quantity END),0)) AS days_of_stock
FROM products p
LEFT JOIN orders o ON p.product_key = o.product_id
GROUP BY p.product_key, p.name, p.available_quantity
LIMIT 10;''')
rows = cur.fetchall()
for r in rows:
    print(r)

