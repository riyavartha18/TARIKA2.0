"""Durable, versioned cache for the assembled RFM dashboard bundle.

The RFM page needs three aggregates: the KPI totals, the segment distribution
and the K-Means cluster counts. They already come from ONE grouped statement
(`queries.fetch_dashboard_bundle`, a GROUPING SETS pass over the small persisted
result table) plus one cheap `customers` count, and the result is memoized in
the shared cache per (analysis version, clustering epoch).

The problem was the *cold* path: that in-process cache dies with every
`runserver` restart, so the first admin to open the page after a restart paid
for the aggregation over remote Neon again - several hundred milliseconds, on
the critical path of a page that is otherwise a cache read. This module keeps
the same assembled bundle in one row of `rfm_dashboard_snapshot`, keyed by the
analysis version it was computed from and by the clustering run whose labels it
contains, so a restarted process reads one primary-key row instead of
re-aggregating ~100k buyers.

Correctness rules, which is why the keys are what they are:

* The snapshot is only ever served for the *current* completed analysis version
  AND the current clustering run. A new run bumps the version, re-clustering
  bumps the run, and either makes the stored row unreachable - the dashboard
  then recomputes from live data rather than showing superseded numbers.
* A completed analysis and a completed clustering both warm this cache
  immediately (`engine.run_and_publish`, `clustering._store_run_state`), so the
  steady state is: writes happen next to the data they summarise, reads never
  run an aggregate.
* Nothing here is authoritative: it is a derived cache. Deleting every row only
  costs one recompute, which is what the fallback below does anyway.
"""

import logging
import time

from django.utils import timezone

from . import cache_manager, queries
from .models import DashboardSnapshot

logger = logging.getLogger(__name__)


def current_clustering_run_id():
    """The stored clustering run id, without adding a database query.

    `clustering.get_run_state()` is itself memoized, and every caller of this
    module has already reconciled/warmed it on the same request.
    """
    from . import clustering

    state = clustering.get_run_state()
    return (state or {}).get('run_id')


def load(version, run_id=None):
    """The bundle for this analysis version + clustering run, or None.

    Tries the in-process cache first (a pure memory read), then the durable
    snapshot row, and reports which one answered so the caller can put a real
    timing breakdown in the API response.
    """
    if version is None:
        return None, 'miss'
    epoch = cache_manager.get_kmeans_epoch()
    bundle = cache_manager.get_dashboard_bundle(version, epoch)
    if bundle is not None:
        return bundle, 'memory'
    try:
        row = DashboardSnapshot.objects.filter(pk=version).first()
    except Exception as exc:  # noqa: BLE001 - a missing/unreadable cache is not an error
        logger.info('Dashboard snapshot unreadable for v%s (%s); recomputing',
                    version, type(exc).__name__)
        return None, 'miss'
    if row is None or (row.clustering_run_id or None) != (run_id or None) \
            or not row.payload:
        return None, 'miss'
    bundle = row.payload
    cache_manager.set_dashboard_bundle(version, epoch, bundle)
    return bundle, 'snapshot'


def build(version=None, run_id=None):
    """Compute the bundle once, cache it (memory + durable row), and time it.

    Returns ``(bundle, timing)`` where `timing` records how long the aggregate
    query and the assembly took, so the API can report real numbers instead of
    an assumed ones.
    """
    started = time.perf_counter()
    bundle = queries.fetch_dashboard_bundle()
    bundle['total_customers'] = queries.fetch_total_customers()
    query_ms = round((time.perf_counter() - started) * 1000, 2)
    store(version, bundle, run_id)
    return bundle, {'source': 'query', 'query_ms': query_ms}


def store(version, bundle, run_id=None):
    """Publish the bundle into the in-process cache and the durable row."""
    if version is None or bundle is None:
        return None
    epoch = cache_manager.get_kmeans_epoch()
    cache_manager.set_dashboard_bundle(version, epoch, bundle)
    try:
        row, _created = DashboardSnapshot.objects.update_or_create(
            pk=version,
            defaults={'clustering_run_id': run_id,
                      'payload': bundle,
                      'computed_at': timezone.now()},
        )
    except Exception as exc:  # noqa: BLE001 - derived cache; a failed write is not fatal
        # The read path recomputes on a miss, so a snapshot this cache could not
        # hold simply costs the next reader one aggregate query. Reported, not
        # raised: nothing about the analysis itself is affected.
        logger.info('Dashboard snapshot not stored for v%s (%s)',
                    version, type(exc).__name__)
        return None
    return row


def invalidate(version=None):
    """Drop the durable snapshot (and the in-process copy) for a version.

    Called when a clustering run rewrites the persisted labels, so the next read
    re-aggregates instead of serving cluster counts built from the old mapping.
    `version=None` drops every row, which is only used when the caller does not
    know which version the clustering consumed.
    """
    queryset = (DashboardSnapshot.objects.all() if version is None
                else DashboardSnapshot.objects.filter(pk=version))
    try:
        deleted = queryset.delete()[0]
    except Exception as exc:  # noqa: BLE001 - derived cache; see `store`
        logger.info('Dashboard snapshot invalidation skipped (%s)', type(exc).__name__)
        deleted = 0
    # The in-process copy is keyed by the clustering epoch, which a completed
    # clustering has already bumped, making it unreachable; delete it too so an
    # invalidation can never be served from the same epoch's memory.
    cache_manager.delete_dashboard_bundle(version)
    return deleted


def warm(version, run_id=None):
    """Recompute and cache the bundle right after a run wrote new results.

    Never fails the run it belongs to: this is an optimisation, and the read
    path still recomputes if this silently did nothing.
    """
    if version is None:
        return None
    try:
        bundle, _timing = build(version=version, run_id=run_id)
    except Exception as exc:  # noqa: BLE001 - a warm-up failure must not break a run
        logger.info('Dashboard snapshot warm-up skipped for v%s (%s)',
                    version, type(exc).__name__)
        return None
    return bundle
