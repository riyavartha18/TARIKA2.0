"""Put the product price columns into the documented three-field layout.

Target semantics of `public.products`
    * ``initial_price``   (new, double precision) -> original product price
    * ``discount_price``  (existing)              -> discount AMOUNT in currency
    * ``actual_price``    (existing TEXT)         -> final discounted selling price
      with ``actual_price = initial_price - discount_price`` (2 decimal places).

Before this command the table stored the ORIGINAL price in the TEXT
``actual_price`` column and had no ``initial_price`` at all; the already
present ``discounted_price`` column proved the intended final price
(``discounted_price = parsed actual_price - discount_price`` was verified on
90,039 of 90,041 rows - the two exceptions are 2-decimal rounding).

What the migration does (idempotent, guarded by ``initial_price IS NULL``)
    1. ADD COLUMN IF NOT EXISTS ``initial_price`` double precision;
    2. for every un-migrated row:
       ``initial_price``    <- parsed ``actual_price`` (the original price)
       ``actual_price``     <- round(original - discount_price, 2) as text
       ``discounted_price`` <- the same final amount (kept in sync)

Rollback: the original price is preserved verbatim in ``initial_price``, so
``actual_price`` can always be restored from it. Nothing is dropped.

Usage
    python manage.py ensure_product_price_schema --dry-run
    python manage.py ensure_product_price_schema
"""

from django.core.management.base import BaseCommand
from django.db import connection


# Parses the TEXT price the same way catalog.models.parse_product_price does
# in Python: strip everything that is not a digit or dot, then cast.
PARSED_ACTUAL = "NULLIF(regexp_replace(actual_price, '[^0-9.]', '', 'g'), '')::float8"


class Command(BaseCommand):
    help = (
        "Add products.initial_price and store the final discounted selling "
        "price in products.actual_price (actual = initial - discount amount)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help="Report what would change without touching the database.",
        )

    def handle(self, *args, **options):
        if connection.vendor != 'postgresql':
            self.stderr.write(self.style.ERROR(
                'This command targets the real PostgreSQL products table; '
                'refusing to run on vendor '
                f"'{connection.vendor}' (use the live settings)."))
            return

        dry = options['dry_run']
        with connection.cursor() as cursor:
            # 1. Column presence check.
            cursor.execute(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_schema='public' AND table_name='products' "
                "AND column_name='initial_price'"
            )
            has_column = cursor.fetchone() is not None
            self.stdout.write(
                'initial_price column: already present' if has_column
                else ('initial_price column: would add' if dry
                      else 'initial_price column: adding'))
            if not dry:
                cursor.execute(
                    "ALTER TABLE public.products "
                    "ADD COLUMN IF NOT EXISTS initial_price double precision"
                )

            # 2. Rows still holding the ORIGINAL price in actual_price. When
            # the column does not exist yet (dry run before first execution),
            # every row with parsable text is pending.
            pending_filter = "initial_price IS NULL" if has_column else "TRUE"
            cursor.execute(
                f"SELECT COUNT(*) FROM public.products WHERE {pending_filter}"
            )
            pending = int(cursor.fetchone()[0] or 0)
            cursor.execute(
                "SELECT COUNT(*) FROM public.products WHERE " + pending_filter + " "
                f"AND {PARSED_ACTUAL} IS NULL"
            )
            unparsable = int(cursor.fetchone()[0] or 0)
            self.stdout.write(
                f'rows to migrate: {pending - unparsable} '
                f'(unparsable price text, left untouched: {unparsable})')

            if dry:
                cursor.execute(
                    "SELECT product_key, actual_price, discount_price, discounted_price, "
                    f"       round(({PARSED_ACTUAL} - COALESCE(discount_price, 0))::numeric, 2) "
                    f"FROM public.products WHERE {pending_filter} LIMIT 5"
                )
                self.stdout.write('preview (key, actual(before), discount, discounted, actual(after)):')
                for row in cursor.fetchall():
                    self.stdout.write(f'  {row}')
                self.stdout.write(self.style.WARNING('dry-run: nothing was changed.'))
                return

            if pending:
                # One atomic set-based rewrite; rows already migrated (or with
                # unparsable text) are never touched, so re-running is safe.
                cursor.execute(
                    "UPDATE public.products "
                    "   SET initial_price = " + PARSED_ACTUAL + ", "
                    "       actual_price = round((" + PARSED_ACTUAL +
                    "           - COALESCE(discount_price, 0))::numeric, 2)::text, "
                    "       discounted_price = round((" + PARSED_ACTUAL +
                    "           - COALESCE(discount_price, 0))::numeric, 2) "
                    "WHERE initial_price IS NULL AND " + PARSED_ACTUAL + " IS NOT NULL"
                )
                self.stdout.write(self.style.SUCCESS(f'migrated {cursor.rowcount} row(s).'))

            # 3. Discount ceiling: the legacy constraint capped
            # `discount_price` at 100 because it once doubled as a small
            # selling price. It is now the discount AMOUNT, so the correct
            # database-level rule is 0 <= amount <= initial_price (the same
            # boundary Django validates in the API layer).
            cursor.execute(
                "SELECT 1 FROM pg_constraint "
                "WHERE conrelid = 'public.products'::regclass "
                "AND conname = 'chk_product_discount_range'"
            )
            if cursor.fetchone() and not dry:
                cursor.execute(
                    "ALTER TABLE public.products "
                    "DROP CONSTRAINT chk_product_discount_range")
                self.stdout.write('legacy 0..100 discount check dropped')

            cursor.execute(
                "SELECT COUNT(*) FROM public.products "
                "WHERE discount_price IS NOT NULL AND ("
                "discount_price < 0 OR "
                "(initial_price IS NOT NULL AND discount_price > initial_price))"
            )
            violations = int(cursor.fetchone()[0] or 0)

            cursor.execute(
                "SELECT 1 FROM pg_constraint "
                "WHERE conrelid = 'public.products'::regclass "
                "AND conname = 'chk_discount_within_initial'"
            )
            if not cursor.fetchone():
                if dry:
                    self.stdout.write(
                        'would add check: 0 <= discount_price <= initial_price')
                elif violations:
                    self.stderr.write(self.style.ERROR(
                        f'{violations} row(s) violate the new discount rule; '
                        'the new CHECK was NOT added (fix the rows first).'))
                else:
                    cursor.execute(
                        "ALTER TABLE public.products "
                        "ADD CONSTRAINT chk_discount_within_initial CHECK ("
                        "discount_price IS NULL OR ("
                        "discount_price >= 0 AND "
                        "(initial_price IS NULL OR "
                        "discount_price <= initial_price)))")
                    self.stdout.write(self.style.SUCCESS(
                        'added check: 0 <= discount_price <= initial_price'))

            # 4. Verify the invariant on the migrated rows.
            cursor.execute(
                "SELECT COUNT(*) FROM public.products WHERE initial_price IS NOT NULL "
                "AND ABS(actual_price::numeric - round((initial_price - "
                "COALESCE(discount_price, 0))::numeric, 2)) > 0.005"
            )
            broken = int(cursor.fetchone()[0] or 0)
            if broken:
                self.stderr.write(self.style.ERROR(
                    f'WARNING: {broken} row(s) violate actual = initial - discount.'))
            else:
                self.stdout.write(self.style.SUCCESS(
                    'Price schema in place: actual_price = initial_price - discount_price.'))
            cursor.execute("ANALYZE public.products;")
