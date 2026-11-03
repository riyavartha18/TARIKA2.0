"""Build / rebuild the cached inventory-velocity metrics table.

Creates ``public.inventory_velocity_metrics`` (+ refresh-state row and the
supporting indexes) if missing, then recomputes stock, 30-day delivered sales,
average daily sales, days of stock and the FAST / NORMAL / SLOW / NON MOVING
classification for EVERY active product in one SQL aggregation.

    python manage.py rebuild_inventory_metrics            # schema + rebuild
    python manage.py rebuild_inventory_metrics --schema-only
"""
from django.core.management.base import BaseCommand

from demand_prediction import inventory_metrics as metrics


class Command(BaseCommand):
    help = "Create and/or rebuild the cached inventory-velocity metrics table."

    def add_arguments(self, parser):
        parser.add_argument('--schema-only', action='store_true',
                            help='Only create tables/indexes; do not rebuild.')

    def handle(self, *args, **options):
        metrics.ensure_schema()
        self.stdout.write(self.style.SUCCESS(
            f"schema ready: {metrics.METRICS_TABLE}, {metrics.STATE_TABLE} + indexes"))
        if options['schema_only']:
            return

        metrics.rebuild_metrics()
        state = metrics.state_snapshot()
        self.stdout.write(self.style.SUCCESS(
            f"rebuilt {state['product_count']} product rows "
            f"for window {state['window_start']} -> {state['window_end']} "
            f"(thresholds fast<={metrics.FAST_MAX_DAYS}d normal<={metrics.NORMAL_MAX_DAYS}d "
            f"slow<={metrics.SLOW_MAX_DAYS}d, window {metrics.SALES_WINDOW_DAYS}d)"))
