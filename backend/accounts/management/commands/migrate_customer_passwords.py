"""Hash the legacy plain-text passwords in public.customers with bcrypt.

The imported retail dataset stores customer passwords as plain text in
public.customers.password. Login already refuses to treat those values as
hashes (accounts/services/supabase_auth.py re-hashes a row with bcrypt the
first time its owner signs in), but plain text must not remain the stored
secret, so this command migrates the rest of the table in place.

How it works
    * Hashing happens entirely inside PostgreSQL with pgcrypto
      `crypt(plain, gen_salt('bf', 10))` - the same function the auth service
      uses - so no password is ever transferred to the application.
    * Each batch is a single UPDATE whose `crypt(h.plain, h.new_hash) =
      h.new_hash` guard writes a row only when the new hash verifiably matches
      the value it replaced, so a failed batch can never corrupt a password.
    * The command is idempotent and resumable: rows already carrying a bcrypt
      hash are skipped, so it can be re-run at any time and stopped freely.
    * Only counts are reported. No password, hash, email or customer id is
      printed.

Usage
    python manage.py migrate_customer_passwords --dry-run
    python manage.py migrate_customer_passwords --batch-size 500
    python manage.py migrate_customer_passwords --shard 0/3   # repeat for 0,1,2
"""

from time import monotonic

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, DatabaseError

from accounts.services.supabase_auth import BCRYPT_SALT_COST

# Rows whose stored value is not already a pgcrypto bcrypt hash.
PLAINTEXT_WHERE = (
    "password IS NOT NULL "
    "AND left(password, 4) NOT IN ('$2a$', '$2b$', '$2y$')"
)

ALREADY_HASHED_WHERE = (
    "password IS NOT NULL "
    "AND left(password, 4) IN ('$2a$', '$2b$', '$2y$')"
)

BATCH_UPDATE_SQL = f"""
WITH batch AS (
    SELECT customer_id, password AS plain
    FROM public.customers
    WHERE {PLAINTEXT_WHERE}{{shard}}
    LIMIT %s
),
hashed AS (
    SELECT customer_id, plain, crypt(plain, gen_salt('bf', {{cost}})) AS new_hash
    FROM batch
)
UPDATE public.customers AS c
SET password = h.new_hash
FROM hashed AS h
WHERE c.customer_id = h.customer_id
  -- Re-check the guard against the current row version: a customer who signed
  -- in while this batch was queued has already been upgraded, and must not be
  -- re-hashed from the stale plain text read above.
  AND c.password IS NOT NULL
  AND left(c.password, 4) NOT IN ('$2a$', '$2b$', '$2y$')
  -- Write only hashes that provably verify against the value they replace.
  AND crypt(h.plain, h.new_hash) = h.new_hash
RETURNING 1
"""

BATCH_PREVIEW_SQL = f"""
SELECT count(*)
FROM (
    SELECT password
    FROM public.customers
    WHERE {PLAINTEXT_WHERE}{{shard}}
    LIMIT %s
) s
"""


class Command(BaseCommand):
    help = (
        "Convert plain-text public.customers.password values to bcrypt hashes "
        "in place (idempotent, resumable)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch-size", type=int, default=500,
            help="Rows hashed per statement (default: 500).",
        )
        parser.add_argument(
            "--limit", type=int, default=0,
            help="Stop after this many rows overall; 0 means the whole table.",
        )
        parser.add_argument(
            "--shard", type=str, default="",
            help="Process only 1/N of the table, as 'I/N' (e.g. '0/3'). Run "
                 "one process per shard index to parallelise the migration.",
        )
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Report the first batch without writing anything.",
        )

    def _parse_shard(self, value):
        if not value:
            return None
        try:
            index, total = (int(part) for part in value.split("/"))
        except ValueError:
            raise CommandError("--shard must look like 'I/N', e.g. '0/3'.")
        if total < 1 or index < 0 or index >= total:
            raise CommandError("--shard needs 0 <= I < N and N >= 1.")
        return index, total

    def handle(self, *args, **options):
        batch_size = options["batch_size"]
        if batch_size < 1:
            raise CommandError("--batch-size must be at least 1.")
        limit = options["limit"]
        shard = self._parse_shard(options["shard"])

        # Sharding keeps concurrent workers on disjoint rows, so nothing is
        # hashed twice by two processes.
        shard_sql = ""
        shard_params = []
        if shard:
            index, total = shard
            shard_sql = " AND mod(hashtext(customer_id), %s) = %s"
            shard_params = [total, index]

        with connection.cursor() as cursor:
            cursor.execute(
                f"SELECT count(*) FROM public.customers WHERE {PLAINTEXT_WHERE}"
            )
            remaining = cursor.fetchone()[0]
            cursor.execute(
                f"SELECT count(*) FROM public.customers WHERE {ALREADY_HASHED_WHERE}"
            )
            already = cursor.fetchone()[0]

        scope = f" (shard {shard[0]}/{shard[1]})" if shard else ""
        self.stdout.write(
            f"plain-text rows: {remaining}, already bcrypt: {already}{scope}"
        )

        if remaining == 0:
            self.stdout.write(self.style.SUCCESS("Nothing to migrate."))
            return

        if options["dry_run"]:
            with connection.cursor() as cursor:
                cursor.execute(
                    BATCH_PREVIEW_SQL.format(shard=shard_sql),
                    [*shard_params, batch_size],
                )
                candidates = cursor.fetchone()[0]
            self.stdout.write(
                self.style.WARNING(
                    f"dry run: would hash {candidates} row(s) in the next batch. "
                    f"No changes written."
                )
            )
            return

        if limit:
            remaining = min(remaining, limit)

        migrated = 0
        started = monotonic()

        while True:
            if limit and migrated >= options["limit"]:
                break
            size = batch_size
            if limit:
                size = min(batch_size, options["limit"] - migrated)

            try:
                with connection.cursor() as cursor:
                    cursor.execute(
                        BATCH_UPDATE_SQL.format(
                            cost=BCRYPT_SALT_COST, shard=shard_sql
                        ),
                        [*shard_params, size],
                    )
                    written = len(cursor.fetchall())
            except DatabaseError as exc:
                # The driver message can quote the statement; log the class
                # only, which never contains credentials.
                raise CommandError(
                    f"Migration stopped on a database error ({type(exc).__name__}). "
                    f"{migrated} row(s) already migrated; it is safe to re-run."
                )

            if written == 0:
                # Nothing in this shard could be written: either the rows were
                # upgraded concurrently by sign-ins, or a hash failed its
                # verification guard. Stop instead of looping forever.
                with connection.cursor() as cursor:
                    cursor.execute(
                        f"SELECT 1 FROM public.customers WHERE {PLAINTEXT_WHERE}"
                        f"{shard_sql} LIMIT 1;",
                        shard_params,
                    )
                    stuck = cursor.fetchone() is not None
                if stuck:
                    self.stdout.write(
                        self.style.WARNING(
                            "Stopped: remaining rows could not be hashed in this "
                            "batch. Sign-in upgrades still cover them; re-run to "
                            "retry."
                        )
                    )
                break

            migrated += written
            elapsed = monotonic() - started
            rate = migrated / elapsed if elapsed else 0
            left = max(remaining - migrated, 0)
            eta = left / rate if rate else 0
            self.stdout.write(
                f"migrated {migrated}/{remaining} "
                f"({rate:.1f} rows/s, ~{eta / 60:.1f} min remaining)"
            )

        self.stdout.write(
            self.style.SUCCESS(f"Done. {migrated} row(s) migrated in "
                               f"{monotonic() - started:.1f}s.")
        )
