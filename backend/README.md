# Django database setup

## Neon connection

1. Create or select a Neon PostgreSQL project and copy its connection string
   from the Neon dashboard's **Connect** dialog.
2. Put that complete URL in `backend/.env` as `DATABASE_URL`. Use the Neon
   connection URL as provided; do not put it in frontend environment variables
   or source code. `backend/.env` is ignored by Git.
3. The Django PostgreSQL backend enforces `sslmode=require`. URL-encoded
   usernames and passwords are supported.
4. From `backend/`, run:

   ```powershell
   python manage.py check
   python manage.py shell -c "from django.db import connection; cursor = connection.cursor(); cursor.execute('SELECT 1'); print(cursor.fetchone())"
   ```

   After importing the application schema, smoke-test a representative table:

   ```powershell
   python manage.py shell -c "from catalog.models import Product; print(Product.objects.order_by('product_id').first())"
   ```

Do not run `migrate` against a populated database until its migration plan and
schema have been reviewed. Many business models in this project use
`managed = False`, and there is no initial migration history for those existing
tables. The `demand_predictions` table is managed by app code and may be created
with `CREATE TABLE IF NOT EXISTS`; this does not copy any existing rows.

## Safe data migration

Changing `DATABASE_URL` only changes where Django connects; it does not copy
the current database. Before cutover:

1. Back up the source database and record row counts for every table, including
   tables not represented by Django models. Inventory the schema, constraints,
   indexes, triggers, extensions, sequences, and views.
2. Review a schema-only export for Supabase-managed objects and PostgreSQL
   extensions before importing anything. Import into a separate Neon database
   or staging branch first; do not overwrite a populated target.
3. Transfer application schema and data in dependency order, preserving primary
   keys and foreign keys. For CSV sources, validate headers and types, load
   parent tables before dependent tables, then reset sequences where needed.
   Compare source and destination row counts and key aggregates, and verify
   representative application queries before cutover.
4. Pause writes, take a final source backup, apply only reviewed incremental
   changes, run read-only smoke checks, then switch `DATABASE_URL`. Keep the
   source intact until reconciliation and application validation are complete.

There are no CSV files in this repository, so CSV sources and their schemas
must be inventoried separately before choosing a `COPY`/`\copy` or ETL process.

## Supabase dependencies and migration boundary

The React app calls the Django API and does not include a Supabase client
dependency or direct Supabase Auth/Storage API calls. The backend does,
however, directly query and write Supabase's `auth.users` schema in its custom
authentication service and uses `crypt`/`gen_salt` for password hashes. Staff
profiles and app data are read from `public` tables such as `app_users`,
`customers`, and `employees`.

Before importing, reconcile the customer table naming: the Django `Customer`
model maps to `customer`, while authentication SQL refers to
`public.customers`. Also inventory `public.app_users`, which is accessed with
raw SQL rather than a Django model.

Neon provides PostgreSQL, not Supabase's managed `auth` schema, Auth service,
Storage service, or Supabase APIs. The existing custom Supabase Auth flows
therefore will not work on Neon unless Auth is migrated separately and the
backend code is changed. Plan to move identities to Django Auth or another
identity provider; users may need password resets or a supported password-hash
migration. Preserve Supabase Auth until that cutover is complete. No direct
Storage integration was found in the application code or frontend dependencies;
URLs already stored in application rows may still reference the old Supabase
project and need separate review. PostgreSQL SQL can generally move, but
`pgcrypto` functions/extensions and schema permissions must be checked on the
Neon target.
