"""Durable store for each buyer's *latest complete* RFM result.

Why this exists: the analysis snapshot itself lives in the shared cache (the
admin dashboard needs its percentiles and per-segment buckets there), so a
customer page that read the segment from the snapshot had two expensive options
- deserialize ~100k cached records, or wait for a fresh full computation after
every server restart. Here a completed run also writes one row per buyer with
the whole result (metrics, scores, segment, tags, version, timestamps). Reading
a buyer is a single primary-key lookup that survives restarts, TTLs and
multi-worker deployments, it is written only from a *successfully completed*
analysis (so nothing partial can reach a customer), and the CLV module reuses
its Monetary/Frequency/segment instead of re-aggregating the orders table.

Synchronization semantics (the architecture contract for this table):

* New buyer with valid orders                -> INSERT  (Case A)
* Existing buyer changed metrics/segment      -> UPDATE  (Cases B/C)
* Existing buyer's values are identical       -> untouched, no ``updated_at``
                                               churn (Case D)
* Buyer whose orders became ineligible        -> removed by an eligibility
                                               anti-join, never left stale (E)
* Buyer simply absent from a partial batch    -> never deleted on batch
                                               membership (F)

The write is split by database backend:

* PostgreSQL (production Neon) uses a real multi-row
  ``INSERT ... ON CONFLICT (customer_id) DO UPDATE ... WHERE <changed>`` - the
  conditional upsert above, plus a ``version <= EXCLUDED.version`` guard so an
  older run can never overwrite a newer result.
* Other backends (the SQLite used for unit tests, which has no ``public.orders``
  table) fall back to the ORM's ``bulk_create(update_conflicts=True)`` and a
  version-based reconciliation, so the existing test suite keeps passing without
  touching PostgreSQL-only SQL.

Batched (buyers are ~100k); everything for one run happens in one transaction,
so readers keep seeing the previous analysis until the new one is fully written.
"""

import json
from datetime import date

from django.db import connection, transaction
from django.utils import timezone

from . import utils
from .models import CustomerSegment, RfmAnalysisState

# Buyers are ~100k, so the upsert is batched; a smaller batch just means more
# round trips to the database.
BULK_BATCH_SIZE = 5000

# Columns the results table stores per buyer (order matters for the SQL VALUES).
_RESULT_FIELDS = (
    'customer_id', 'segment', 'tags', 'monetary', 'recency', 'frequency',
    'r_score', 'f_score', 'm_score', 'rfm_score',
    'first_purchase_date', 'last_purchase_date', 'version',
    'computed_at', 'updated_at',
)
# The subset that counts as a *meaningful data change* (Case D). Version and the
# two timestamps are run bookkeeping and are not compared for change detection.
_DATA_FIELDS = (
    'segment', 'tags', 'monetary', 'recency', 'frequency',
    'r_score', 'f_score', 'm_score', 'rfm_score',
    'first_purchase_date', 'last_purchase_date',
)


def _combined_score(record):
    """Classic RFM score string (R||F||M band scores), '' when any is missing."""
    r, f, m = record.get('r_score'), record.get('f_score'), record.get('m_score')
    if r is None or f is None or m is None:
        return ''
    return f'{r}{f}{m}'


def _parse_date(value):
    """The RFM record carries purchase dates as 'YYYY-MM-DD' text or None."""
    if isinstance(value, date):
        return value
    if not value:
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def _result_tuple(record, version, now):
    """Positional values for one buyer matching ``_RESULT_FIELDS`` order."""
    return (
        record['customer_id'],
        record['segment'],
        json.dumps(list(record.get('tags') or [])),
        round(float(record.get('monetary') or 0), 2),
        record.get('recency_days'),
        record.get('frequency'),
        record.get('r_score'),
        record.get('f_score'),
        record.get('m_score'),
        _combined_score(record),
        _parse_date(record.get('first_purchase_date')),
        _parse_date(record.get('last_purchase_date')),
        version,
        now,
        now,
    )


def _build_upsert_sql(batch_size):
    """Multi-row conditional UPSERT for PostgreSQL (Case A/B/C/D + version guard).

    ``DO UPDATE`` runs only when the incoming version is at least the stored one
    (an older run cannot win) AND at least one meaningful data column actually
    differs (an unchanged buyer is left completely untouched, so ``updated_at``
    does not move). ``RETURNING ... (xmax = 0)`` tells the caller which rows were
    fresh INSERTs versus UPDATEs; skipped rows return nothing.
    """
    row_ph = '(%s,%s,%s::jsonb,%s,%s,%s,%s,%s,%s,%s,%s::date,%s::date,%s,%s,%s)'
    values_sql = ','.join(row_ph for _ in range(batch_size))
    set_sql = ', '.join(f'{f} = EXCLUDED.{f}' for f in _DATA_FIELDS)
    set_sql += ', version = EXCLUDED.version, computed_at = EXCLUDED.computed_at, ' \
               'updated_at = EXCLUDED.updated_at'
    distinct_sql = ' OR '.join(
        f'rfm_customer_segments.{f} IS DISTINCT FROM EXCLUDED.{f}'
        for f in _DATA_FIELDS
    )
    cols = ', '.join(_RESULT_FIELDS)
    return (
        f'INSERT INTO rfm_customer_segments ({cols}) VALUES {values_sql} '
        'ON CONFLICT (customer_id) DO UPDATE SET '
        f'{set_sql} '
        'WHERE rfm_customer_segments.version <= EXCLUDED.version '
        f'AND ({distinct_sql}) '
        'RETURNING customer_id, (xmax = 0) AS inserted'
    )


def _upsert_postgres(records, version, now):
    """Run the conditional UPSERT in batches; return {inserted, updated} counts."""
    inserted = 0
    updated = 0
    with connection.cursor() as cursor:
        for start in range(0, len(records), BULK_BATCH_SIZE):
            batch = records[start:start + BULK_BATCH_SIZE]
            sql = _build_upsert_sql(len(batch))
            params = []
            for record in batch:
                params.extend(_result_tuple(record, version, now))
            cursor.execute(sql, params)
            for _customer_id, was_insert in cursor.fetchall():
                if was_insert:
                    inserted += 1
                else:
                    updated += 1
    return {'inserted': inserted, 'updated': updated}


def _reconcile_postgres():
    """Drop stored buyers who no longer have any eligible order (Case E).

    Deletion is decided by live eligibility, never by whether a buyer appeared in
    the batch just written, so a customer is only removed when their order
    history genuinely stopped qualifying (a return/cancellation) - a partial
    batch can never delete an still-eligible customer (Case F)."""
    statuses = utils.eligible_delivery_statuses()
    exclude_negative = utils.EXCLUDE_NEGATIVE_FINAL_PRICE
    with connection.cursor() as cursor:
        cursor.execute(
            """
            DELETE FROM rfm_customer_segments cs
            WHERE NOT EXISTS (
                SELECT 1 FROM public.orders o
                WHERE o.customer_id = cs.customer_id
                  AND o.delivery_status = ANY(%s)
                  AND o.purchase_date IS NOT NULL
                  AND (%s OR o.final_price >= 0)
            )
            """,
            [statuses, exclude_negative],
        )
        return cursor.rowcount if cursor.rowcount and cursor.rowcount > 0 else 0


def _upsert_orm(records, version, now):
    """SQLite/other backends: ORM upsert of every buyer at the given version.

    Uses the same field list as the PostgreSQL path so the stored columns match.
    ``bulk_create(update_conflicts=True)`` performs ON CONFLICT DO UPDATE without
    a change guard, so on these backends every buyer is (re)written; the
    conditional-skip optimization is a production-PostgreSQL behaviour.
    """
    rows = [
        CustomerSegment(
            customer_id=record['customer_id'],
            segment=record['segment'],
            tags=list(record.get('tags') or []),
            monetary=round(float(record.get('monetary') or 0), 2),
            recency=record.get('recency_days'),
            frequency=record.get('frequency'),
            r_score=record.get('r_score'),
            f_score=record.get('f_score'),
            m_score=record.get('m_score'),
            rfm_score=_combined_score(record),
            first_purchase_date=_parse_date(record.get('first_purchase_date')),
            last_purchase_date=_parse_date(record.get('last_purchase_date')),
            version=version,
            computed_at=now,
            updated_at=now,
        )
        for record in records
    ]
    if rows:
        CustomerSegment.objects.bulk_create(
            rows,
            batch_size=BULK_BATCH_SIZE,
            update_conflicts=True,
            unique_fields=['customer_id'],
            update_fields=list(_DATA_FIELDS) + ['version', 'computed_at', 'updated_at'],
        )
    return {'inserted': len(rows), 'updated': 0}


def store_records(records, version, analysis_date=None, full=True,
                  source_fingerprint='', return_stats=False):
    """Persist a completed run's full RFM results and mark that version current.

    ``full`` selects the reconciliation policy on backends that lack a live
    ``orders`` table (see `_upsert_orm`/SQLite path): a full refresh drops rows
    not refreshed by this run, an incremental refresh leaves them. On PostgreSQL
    reconciliation is always by live eligibility, so ``full`` does not change the
    outcome there. Returns the number of buyers synced, or a stats dict when
    ``return_stats`` is set (inserted / updated / deleted / unchanged / buyers).
    """
    now = timezone.now()
    records = list(records)

    with transaction.atomic():
        if connection.vendor == 'postgresql':
            stats = _upsert_postgres(records, version, now)
            deleted = _reconcile_postgres()
        else:
            stats = _upsert_orm(records, version, now)
            if full:
                deleted = CustomerSegment.objects.exclude(version=version).delete()[0]
            else:
                deleted = 0

        buyer_ids = {record['customer_id'] for record in records}
        touched = stats['inserted'] + stats['updated']
        # Buyers written this run whose stored values were already identical are
        # the untouched remainder (PostgreSQL conditional skip only).
        unchanged = max(len(buyer_ids) - touched, 0)

        RfmAnalysisState.objects.update_or_create(
            id=RfmAnalysisState.SINGLETON_ID,
            defaults={'version': version,
                      'buyer_count': len(buyer_ids),
                      'analysis_date': analysis_date,
                      'completed_at': now,
                      'source_fingerprint': source_fingerprint},
        )

    # The summary dashboard memoizes this single-row state so a warm read does
    # not pay a remote round trip to fetch the version/dates. Rewrite the memo
    # with the just-committed values (the version bump already makes the old
    # cached bundle unreachable, so the next summary recomputes it).
    _refresh_state_memo(version, len(buyer_ids), analysis_date, now)

    # The CLV module memoizes this version for cheap freshness checks; a new
    # completed run must drop the memo immediately so the next CLV read sees
    # the new version (and rebuilds its snapshot) instead of waiting on the
    # memo TTL. Imported lazily - clv depends on this module, not vice versa.
    try:
        from clv import utils as clv_utils
        from django.core.cache import cache
        cache.delete(clv_utils.CLV_STORED_RFM_VERSION_KEY)
    except Exception:  # noqa: BLE001 - a missing memo is self-healing anyway
        pass

    if return_stats:
        return {'inserted': stats['inserted'], 'updated': stats['updated'],
                'deleted': deleted, 'unchanged': unchanged,
                'buyers': len(buyer_ids)}
    return len(buyer_ids)


def get(customer_id):
    """The stored CustomerSegment row for one buyer, or None."""
    if not customer_id:
        return None
    return CustomerSegment.objects.filter(customer_id=customer_id).first()


def get_state():
    """The current stored analysis, or None when no analysis has ever completed."""
    return RfmAnalysisState.objects.filter(pk=RfmAnalysisState.SINGLETON_ID).first()


def _refresh_state_memo(version, buyer_count, analysis_date, completed_at):
    """Publish the just-committed state to the short-lived summary memo."""
    try:
        from . import cache_manager
        cache_manager.set_state_memo({
            'version': version,
            'buyer_count': buyer_count,
            'analysis_date': (analysis_date.isoformat() if analysis_date else None),
            'completed_at': (completed_at.isoformat() if completed_at else None),
        })
    except Exception:  # noqa: BLE001 - a missing memo simply falls back to the DB
        pass


def get_cached_state():
    """Analysis state as a small dict, served from the memo when warm (no DB).

    Falls back to one read of the singleton row and repopulates the memo on a
    miss. Returns None when no analysis has ever completed. Values mirror
    `RfmAnalysisState` but with dates/timestamps as ISO strings so the cached
    payload is cache-backend agnostic.
    """
    from . import cache_manager
    memo = cache_manager.get_state_memo()
    if isinstance(memo, dict) and 'version' in memo:
        return memo
    state = get_state()
    if state is None:
        return None
    payload = {
        'version': state.version,
        'buyer_count': state.buyer_count,
        'analysis_date': (state.analysis_date.isoformat()
                          if state.analysis_date else None),
        'completed_at': (state.completed_at.isoformat()
                         if state.completed_at else None),
    }
    cache_manager.set_state_memo(payload)
    return payload


def latest_version():
    state = get_state()
    return state.version if state else None
