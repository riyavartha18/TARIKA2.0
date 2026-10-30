"""Performance index for the RFM aggregation (Section 18).

The single expensive step of a run is the grouped scan over the 1M-row
`public.orders` table filtered to completed purchases. This partial, covering
index lets PostgreSQL satisfy that aggregation with an index-only scan over
just the delivered rows (already ordered by `customer_id`, so it groups without
a hash), rather than a full table scan of all 1,000,002 orders.

The index is created only on PostgreSQL, where `public.orders` is a real,
pre-existing dataset table. On other backends (e.g. the SQLite used for unit
tests, which has no `orders` table) the operation is a deliberate no-op, so
migrations stay portable without touching any stored row.
"""

from django.db import migrations

INDEX_SQL = (
    "CREATE INDEX IF NOT EXISTS orders_rfm_delivered_idx "
    "ON public.orders (customer_id) "
    "INCLUDE (final_price, purchase_date) "
    "WHERE delivery_status = 'Delivered';"
)
DROP_SQL = "DROP INDEX IF EXISTS public.orders_rfm_delivered_idx;"


def create_index(apps, schema_editor):
    if schema_editor.connection.vendor == 'postgresql':
        schema_editor.execute(INDEX_SQL)


def drop_index(apps, schema_editor):
    if schema_editor.connection.vendor == 'postgresql':
        schema_editor.execute(DROP_SQL)


class Migration(migrations.Migration):

    dependencies = [
        ('rfm_analysis', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_index, drop_index),
    ]
