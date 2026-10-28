"""Rebuild the authoritative sales metric and consolidate purchase_count.

Per the Admin-analytics consolidation decision:

  1. Treat every ``Delayed`` order as completed: ``delivery_status`` is set to
     ``Delivered`` (idempotent; run once against the historical data).
  2. Recompute ``fact_product_analysis.units_sold`` as the SUM of delivered
     ``orders.quantity`` grouped by product (``orders.product_id`` ->
     ``products.product_key``). A product with no delivered order becomes 0.
     Only genuine sales count: ``Returned``/``In Transit`` are excluded; a
     multi-unit order contributes its full quantity, not one per row.
  3. Add an index on ``orders (product_id, delivery_status)`` (verified absent)
     so the delivered aggregate and the per-product sales history are cheap.
  4. Back up ``purchase_count`` (product_key, purchase_count) into a recovery
     table, then DROP the ``purchase_count`` column: ``units_sold`` is now the
     single authoritative sales-quantity metric.

Everything runs inside one transaction so a failure leaves the schema/data
unchanged. Re-running is safe (guards on existing column/index/rows).

    python manage.py rebuild_sales_metrics --dry-run
    python manage.py rebuild_sales_metrics
"""
from django.core.management.base import BaseCommand
from django.db import connection, transaction


class Command(BaseCommand):
    help = ("Convert Delayed->Delivered, backfill units_sold from delivered "
            "orders, index orders for sales history, and drop purchase_count "
            "(after backing it up).")

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='Report the steps without writing anything.')

    def _column_exists(self, cursor, table, column):
        cursor.execute(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name=%s AND column_name=%s",
            [table, column],
        )
        return cursor.fetchone() is not None

    def _index_exists(self, cursor, name):
        cursor.execute("SELECT 1 FROM pg_indexes WHERE schemaname='public' AND indexname=%s", [name])
        return cursor.fetchone() is not None

    def handle(self, *args, **options):
        dry = options['dry_run']

        with connection.cursor() as cursor:
            has_purchase = self._column_exists(cursor, 'fact_product_analysis', 'purchase_count')
            has_index = self._index_exists(cursor, 'orders_product_delivery_idx')

        if dry:
            self.stdout.write("would: UPDATE orders SET delivery_status='Delivered' WHERE delivery_status='Delayed'")
            self.stdout.write("would: backfill units_sold = SUM(delivered orders.quantity) per product_key")
            self.stdout.write("would: CREATE INDEX orders_product_delivery_idx ON orders(product_id, delivery_status)"
                              if not has_index else "index already present (skip)")
            self.stdout.write("would: backup purchase_count -> fact_product_analysis_purchase_count_backup"
                              if has_purchase else "purchase_count already removed (skip backup)")
            self.stdout.write("would: ALTER TABLE fact_product_analysis DROP COLUMN purchase_count"
                              if has_purchase else "purchase_count already removed (skip drop)")
            return

        with transaction.atomic():
            with connection.cursor() as cursor:
                # 1. Delayed -> Delivered (idempotent).
                cursor.execute(
                    "UPDATE orders SET delivery_status = 'Delivered' WHERE delivery_status = 'Delayed'"
                )
                converted = cursor.rowcount
                self.stdout.write(self.style.SUCCESS(f"orders: {converted} 'Delayed' rows -> 'Delivered'"))

                # 2a. units_sold = SUM(delivered quantity) for products that have one.
                cursor.execute(
                    """
                    UPDATE fact_product_analysis f
                       SET units_sold = d.q
                      FROM (
                            SELECT product_id, SUM(quantity)::numeric AS q
                              FROM orders
                             WHERE delivery_status = 'Delivered' AND product_id IS NOT NULL
                             GROUP BY product_id
                           ) d
                     WHERE f.product_key = d.product_id
                    """
                )
                updated = cursor.rowcount

                # 2b. products with no delivered order -> units_sold 0.
                cursor.execute(
                    """
                    UPDATE fact_product_analysis
                       SET units_sold = 0
                     WHERE product_key NOT IN (
                            SELECT product_id FROM orders
                             WHERE delivery_status = 'Delivered' AND product_id IS NOT NULL
                           )
                    """
                )
                zeroed = cursor.rowcount
                self.stdout.write(self.style.SUCCESS(
                    f"units_sold backfilled: {updated} from delivered orders, {zeroed} set to 0"))

                # 3. Supporting index (verified absent above).
                if not has_index:
                    cursor.execute(
                        "CREATE INDEX orders_product_delivery_idx "
                        "ON public.orders (product_id, delivery_status)"
                    )
                    self.stdout.write(self.style.SUCCESS("created index orders_product_delivery_idx"))
                else:
                    self.stdout.write("index orders_product_delivery_idx already present")

                # 4. Backup then drop purchase_count (only if it still exists).
                if has_purchase:
                    cursor.execute("DROP TABLE IF EXISTS public.fact_product_analysis_purchase_count_backup")
                    cursor.execute(
                        "CREATE TABLE public.fact_product_analysis_purchase_count_backup AS "
                        "SELECT product_key, purchase_count FROM public.fact_product_analysis"
                    )
                    self.stdout.write(self.style.SUCCESS(
                        "backed up purchase_count -> fact_product_analysis_purchase_count_backup"))
                    cursor.execute("ALTER TABLE public.fact_product_analysis DROP COLUMN purchase_count")
                    self.stdout.write(self.style.SUCCESS("dropped column fact_product_analysis.purchase_count"))
                else:
                    self.stdout.write("purchase_count already removed; nothing to drop")

        self.stdout.write(self.style.SUCCESS("Sales metrics rebuilt. The ID3 model retrains automatically "
                                             "on the next demand calculation (units_sold fingerprint changed)."))
