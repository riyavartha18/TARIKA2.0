"""Create the indexes the Demand Forecasting queries rely on.

Idempotent and non-destructive: every statement is ``CREATE INDEX IF NOT
EXISTS``, so re-running is a no-op and no data or schema is ever dropped. The
tables are unmanaged dataset tables, so these live here (raw SQL) instead of in
a Django model migration.

What gets indexed and why (verified against the live schema):

* ``fact_product_analysis(units_sold DESC)``
  The products endpoint orders by the units_sold demand terciles and pages a
  small slice (``... ORDER BY <tier>, units_sold DESC LIMIT n``). A b-tree on
  ``units_sold`` lets PostgreSQL walk the index in order and stop at the page
  size instead of sorting the whole ~90k-row catalog.

* ``products (LOWER(TRIM(COALESCE(main_category, ''))))``
  The category filter compares ``sql_norm_expr(d.main_category)`` -- the exact
  ``LOWER(TRIM(COALESCE(...,'')))`` expression -- so an expression index on the
  identical expression turns the filter into an index scan. The join column
  ``product_key`` is already the primary key on both tables, and the ``orders``
  history query is already served by ``orders_product_delivery_idx``; neither is
  duplicated here.
"""

from django.core.management.base import BaseCommand
from django.db import connection

_INDEXES = [
    (
        'idx_fpa_units_sold_desc',
        'CREATE INDEX IF NOT EXISTS idx_fpa_units_sold_desc '
        'ON fact_product_analysis (units_sold DESC)',
    ),
    (
        'idx_products_main_category_norm',
        "CREATE INDEX IF NOT EXISTS idx_products_main_category_norm "
        "ON products (LOWER(TRIM(COALESCE(main_category, ''))))",
    ),
]


class Command(BaseCommand):
    help = 'Create (idempotently) the indexes used by Demand Forecasting.'

    def handle(self, *args, **options):
        if connection.vendor != 'postgresql':
            self.stdout.write(self.style.WARNING(
                f'Index optimisation targets PostgreSQL; skipping on '
                f"'{connection.vendor}'."))
            return

        for name, ddl in _INDEXES:
            with connection.cursor() as cursor:
                cursor.execute(ddl)
            self.stdout.write(self.style.SUCCESS(f' ensured index {name}'))

        # Refresh planner statistics so the new indexes are actually chosen.
        with connection.cursor() as cursor:
            cursor.execute('ANALYZE fact_product_analysis')
            cursor.execute('ANALYZE products')
        self.stdout.write(self.style.SUCCESS(' ANALYZE complete.'))
