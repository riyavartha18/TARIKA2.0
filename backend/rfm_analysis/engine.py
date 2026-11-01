"""RFM analysis orchestration and background execution.

A run is the full pipeline over the live Neon order history: aggregate the
eligible metrics, score them by dynamic percentile, apply the finalized
segmentation rules, and publish an immutable snapshot version. Expensive work
is executed on a daemon thread so a request never blocks on a ~100k-customer
computation, and a shared cache lock makes repeated "Run" clicks safe.

The snapshot stores one compact record per buyer plus the aggregate totals; the
Never Purchased population is intentionally kept out of it (they carry no RFM
metrics) and is read on demand from `queries`.
"""

import logging
import threading

from django.db import close_old_connections
from django.utils import timezone

from . import (cache_manager, queries, rfm_calculator, rfm_scoring,
               segment_store, segmentation, utils)

logger = logging.getLogger(__name__)


def compute_snapshot():
    """Run the full pipeline synchronously and return the snapshot payload.

    Raises on database failure; the caller decides how to record that. Returns
    a dict ready to publish, or an empty-but-valid analysis state when there
    are no eligible buyers (never a partial/None snapshot).
    """
    import time
    started = time.perf_counter()

    buyer_rows, analysis_date = queries.fetch_buyer_metrics()
    metrics = rfm_calculator.build_metrics(buyer_rows)[0]

    # Percentile scoring needs the whole buyer population, so it is only
    # meaningful when there is at least one buyer. Never Purchased customers are
    # excluded from these percentile calculations by construction: they are not
    # in `buyer_rows` at all.
    rfm_scoring.score_metrics(metrics)
    segmentation.apply_segments(metrics)

    counts, big_spender_count = segmentation.segment_counts(metrics)

    # Dashboard totals are derived from the metrics already in memory, so the
    # 1M-row orders table is scanned exactly once per run. Only the total
    # customer count (from the small `customers` table) needs a second read.
    total_customers = queries.fetch_total_customers()
    totals = {
        'total_customers': total_customers,
        'total_eligible_buyers': len(metrics),
        'never_purchased_customers': max(total_customers - len(metrics), 0),
        'total_eligible_orders': sum(m['frequency'] for m in metrics),
        'total_eligible_revenue': round(sum(m['monetary'] for m in metrics), 2),
    }

    metrics.sort(key=lambda m: m['customer_id'])
    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)

    return {
        'status': 'completed',
        'analysis_date': analysis_date,
        'totals': totals,
        'segment_counts': counts,
        'big_spender_count': big_spender_count,
        'buyer_count': len(metrics),
        'customer_ids': [m['customer_id'] for m in metrics],
        'records': metrics,
        'compute_ms': elapsed_ms,
    }


def run_and_publish():
    """Compute, publish the cache snapshot and persist the segment labels."""
    cache_manager.set_run_status('running', started_at=utils.utcnow().isoformat())
    try:
        snapshot = compute_snapshot()
        # publish_snapshot() pops the records out of the dict, so keep the list
        # for the durable per-customer store.
        records = snapshot['records']
        analysis_date = snapshot['analysis_date']
        # Keep numbering monotonic: the store survives a restart while the
        # snapshot cache does not, so a fresh process must not reuse an old
        # version number (customer offer caches are keyed by it).
        next_version = max(cache_manager.get_latest_version() or 0,
                           segment_store.latest_version() or 0) + 1
        version = cache_manager.publish_snapshot(snapshot, version=next_version)
        store_segments(version, records, analysis_date)
        cache_manager.set_run_status(
            'completed',
            finished_at=utils.utcnow().isoformat(),
            version=version,
            compute_ms=snapshot['compute_ms'],
        )
        return version
    except Exception as exc:  # noqa: BLE001 - a background run must record failure
        logger.exception('RFM analysis run failed')
        cache_manager.set_run_status('failed', error_type=type(exc).__name__)
        raise
    finally:
        cache_manager.release_run_lock()


def store_segments(version, records, analysis_date=None):
    """Persist per-buyer segments for a published snapshot (never fails a run).

    The dashboard works from the cache snapshot alone, so if this write hits a
    database problem the analysis is still published; the next completed run
    repairs the store, and until then the customer path simply falls back to the
    snapshot instead of showing wrong data.
    """
    try:
        stored = segment_store.store_records(records, version, analysis_date)
        logger.info('Stored RFM segments for %s buyers (version %s)', stored, version)
        return stored
    except Exception:  # noqa: BLE001 - logging is enough, the run itself succeeded
        logger.exception('Could not persist RFM segment labels (version %s)', version)
        return None


def start_background_run():
    """Kick off a run on a worker thread.

    Returns (accepted, status). A second request while one is in flight is
    refused (accepted=False) using the shared lock, so repeated clicks never
    stack up overlapping full-population computations.
    """
    if not cache_manager.acquire_run_lock():
        return False, cache_manager.get_run_status()

    cache_manager.set_run_status('queued', started_at=utils.utcnow().isoformat())

    def _worker():
        # A background thread must open (and later close) its own DB
        # connection; Django only reaps them between requests on the main
        # thread, so an untouched thread would leak a Neon connection.
        close_old_connections()
        try:
            run_and_publish()
        except Exception:  # noqa: BLE001 - status already recorded as failed
            logger.warning('Background RFM run ended in failure')
        finally:
            close_old_connections()

    thread = threading.Thread(target=_worker, name='rfm-analysis', daemon=True)
    thread.start()
    return True, {'status': 'queued'}


def _snapshot_age_seconds(meta, now):
    computed_at = (meta or {}).get('computed_at')
    if not computed_at:
        return None
    try:
        from django.utils.dateparse import parse_datetime
        stamp = parse_datetime(computed_at)
    except (TypeError, ValueError):
        return None
    if stamp is None:
        return None
    if timezone.is_naive(stamp):
        stamp = timezone.make_aware(stamp, timezone.get_current_timezone())
    return (now - stamp).total_seconds()


def ensure_latest():
    """Serve the latest completed analysis and refresh it in the background.

    Called whenever an admin opens the analysis (and by the customer offer path
    when nothing is available yet), so no manual Run action is needed. It never
    blocks the request and never exposes an incomplete run:

    * If a run is already in flight, it is left alone (the lock guarantees it).
    * If the in-cache snapshot is gone but a completed analysis is still stored
      per customer, that stored result is reused: at most a background refresh
      is scheduled when it is older than the threshold, never a blocking
      recompute. A restarted server therefore keeps serving real offers.
    * If no analysis has ever completed, one is started in the background.
    * If the latest snapshot is older than the refresh threshold, a refresh is
      started in the background while the existing completed snapshot is kept.

    Returns a small dict describing what the caller should report.
    """
    now = timezone.now()
    status = cache_manager.get_run_status()
    current = status.get('status')

    if current in ('queued', 'running'):
        return {'refreshing': True, 'started': False, 'run_status': status}

    meta = cache_manager.get_meta()
    if meta is None:
        state = segment_store.get_state()
        if state is not None:
            # Reuse the stored analysis; only schedule a refresh when stale.
            age = (now - state.completed_at).total_seconds()
            threshold = utils.RFM_REFRESH_AFTER_SECONDS
            if threshold > 0 and age > threshold:
                accepted, run_status = start_background_run()
                return {'refreshing': accepted, 'started': accepted,
                        'run_status': run_status, 'stored_version': state.version}
            return {'refreshing': False, 'started': False, 'run_status': status,
                    'stored_version': state.version}

        accepted, run_status = start_background_run()
        return {'refreshing': True, 'started': accepted, 'run_status': run_status}

    age = _snapshot_age_seconds(meta, now)
    threshold = utils.RFM_REFRESH_AFTER_SECONDS
    if threshold > 0 and (age is None or age > threshold):
        accepted, run_status = start_background_run()
        return {'refreshing': accepted, 'started': accepted, 'run_status': run_status}

    return {'refreshing': False, 'started': False, 'run_status': status}
