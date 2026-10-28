"""Add the inventory/warehouse columns and tables the new workflows need.

Two purely additive, non-destructive schema objects:

1. ``public.products.is_active``
   The real ``products`` table has no active flag, so a warehouse "delete" of a
   product that still appears in historical ``orders`` (or in a customer's live
   ``cart`` / ``wishlist``) cannot be a hard ``DELETE`` without breaking those
   foreign keys or erasing business history. A soft delete (archive) flag lets a
   product disappear from every storefront and actionable list while its sales
   history is preserved untouched.

2. ``public.replenishment_orders``
   A supplier replenishment order is NOT a customer sales order, so it must not
   be inserted into ``public.orders``. This table tracks each replenishment
   purchase order (quantity, status, receipt) separately. There is deliberately
   no FK to ``products`` so a purchase order survives even if the product row is
   later archived.

Everything uses IF NOT EXISTS, so the command is safe to re-run. No existing
rows or columns are modified or dropped.

Usage
    python manage.py ensure_inventory_schema
    python manage.py ensure_inventory_schema --dry-run
"""

from django.core.management.base import BaseCommand
from django.db import connection, DatabaseError


STATEMENTS = [
    ('products.is_active column',
     'ALTER TABLE public.products '
     "ADD COLUMN IF NOT EXISTS is_active boolean NOT NULL DEFAULT TRUE"),

    # Whole-unit, non-negative stock enforced at the database (item 6). A NULL
    # is permitted and means "stock unknown"; a value, when present, must be a
    # non-negative whole number so fractional/negative stock can never be
    # written by any code path. Additive only: the existing rows already satisfy
    # it (0 null, 0 negative, 0 fractional at time of writing), and the
    # DROP/ADD pair makes the statement idempotent and safe to re-run.
    ('products.available_quantity stock check (drop)',
     'ALTER TABLE public.products '
     'DROP CONSTRAINT IF EXISTS products_available_quantity_stock_check'),
    ('products.available_quantity stock check (add)',
     'ALTER TABLE public.products '
     'ADD CONSTRAINT products_available_quantity_stock_check '
     'CHECK (available_quantity IS NULL '
     'OR (available_quantity >= 0 AND available_quantity = floor(available_quantity)))'),

    ('replenishment_orders table',
     """
     CREATE TABLE IF NOT EXISTS public.replenishment_orders (
         po_key            text PRIMARY KEY,
         product_key       text NOT NULL,
         product_name      text,
         quantity_ordered  integer NOT NULL CHECK (quantity_ordered > 0),
         quantity_received integer NOT NULL DEFAULT 0 CHECK (quantity_received >= 0),
         status            text NOT NULL DEFAULT 'Pending',
         demand_tier       text,
         created_by        text,
         created_at        text,
         updated_at        text,
         received_at       text
     )
     """),

    ('replenishment_orders product/status index',
     'CREATE INDEX IF NOT EXISTS replenishment_orders_product_status_idx '
     'ON public.replenishment_orders (product_key, status)'),

    # A single-product reorder adds its quantity straight to available_quantity
    # the moment it is placed (the current business rule). stock_applied records
    # that those units are ALREADY counted, so a later goods receipt must not
    # add them a second time. Default FALSE keeps the historical behaviour for
    # rows that did not pre-apply stock (e.g. bulk purchase orders, whose units
    # are still added only on receipt).
    ('replenishment_orders.stock_applied column',
     'ALTER TABLE public.replenishment_orders '
     'ADD COLUMN IF NOT EXISTS stock_applied boolean NOT NULL DEFAULT FALSE'),
]


class Command(BaseCommand):
    help = (
        "Create products.is_active and the replenishment_orders table "
        "(idempotent, additive only)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help="Report the statements that would run without touching the schema.",
        )

    def handle(self, *args, **options):
        if options['dry_run']:
            for label, _sql in STATEMENTS:
                self.stdout.write(f"would run: {label}")
            return

        with connection.cursor() as cursor:
            for label, statement in STATEMENTS:
                try:
                    cursor.execute(statement)
                except DatabaseError as exc:
                    self.stderr.write(
                        f"failed: {label} (database error: {type(exc).__name__})"
                    )
                    continue
                self.stdout.write(self.style.SUCCESS(f"ready: {label}"))

            for table in ('products', 'replenishment_orders'):
                try:
                    cursor.execute(f"ANALYZE public.{table};")
                except DatabaseError:
                    pass

        self.stdout.write(self.style.SUCCESS("Inventory schema is in place."))
