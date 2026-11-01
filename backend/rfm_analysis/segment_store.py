"""Durable read-through store for each buyer's latest RFM segment.

Why this exists: the analysis snapshot itself lives in the shared cache (the
admin dashboard needs its percentiles and per-segment buckets there), so a
customer page that read the segment from the snapshot had two expensive options
- deserialize ~100k cached records, or wait for a fresh full computation after
every server restart. That is what made Member Privileges sit on
"Tailoring your offers" for tens of seconds.

Here a completed run also writes one tiny row per buyer (segment + secondary
tags). Reading it is a single primary-key lookup that survives restarts, TTLs
and multi-worker deployments, and it is written only from a *successfully
completed* analysis, so nothing partial can ever reach a customer.
"""

from django.db import transaction
from django.utils import timezone

from .models import CustomerSegment, RfmAnalysisState

# Buyers are ~100k, so the upsert is batched; a smaller batch just means more
# round trips to the database.
BULK_BATCH_SIZE = 5000


def store_records(records, version, analysis_date=None):
    """Persist a completed run's segment labels and mark that version current.

    Upserts every buyer (so unchanged customers are not deleted and reinserted),
    then drops rows for customers who no longer qualify, and finally records the
    version in the single-row state table. All of it in one transaction: readers
    keep seeing the previous analysis until the new one is fully written.
    """
    now = timezone.now()
    rows = [
        CustomerSegment(customer_id=record['customer_id'],
                        segment=record['segment'],
                        tags=list(record.get('tags') or []),
                        version=version,
                        computed_at=now)
        for record in records
    ]

    with transaction.atomic():
        if rows:
            CustomerSegment.objects.bulk_create(
                rows,
                batch_size=BULK_BATCH_SIZE,
                update_conflicts=True,
                unique_fields=['customer_id'],
                update_fields=['segment', 'tags', 'version', 'computed_at'],
            )
        # Anyone not refreshed by this run no longer belongs to a segment
        # (their order history changed), so their old label must go.
        CustomerSegment.objects.exclude(version=version).delete()
        RfmAnalysisState.objects.update_or_create(
            id=RfmAnalysisState.SINGLETON_ID,
            defaults={'version': version,
                      'buyer_count': len(rows),
                      'analysis_date': analysis_date,
                      'completed_at': now},
        )
    return len(rows)


def get(customer_id):
    """The stored CustomerSegment row for one buyer, or None."""
    if not customer_id:
        return None
    return CustomerSegment.objects.filter(customer_id=customer_id).first()


def get_state():
    """The current stored analysis, or None when no analysis has ever completed."""
    return RfmAnalysisState.objects.filter(pk=RfmAnalysisState.SINGLETON_ID).first()


def latest_version():
    state = get_state()
    return state.version if state else None
