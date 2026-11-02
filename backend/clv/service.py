"""CLV state orchestration: on-demand build, snapshot cache, background runs.

The state is computed from live source data every time (never persisted):
one grouped aggregate over `public.orders` plus the reusable customer-level
metrics the RFM analysis already stored (Monetary + segment). The built state
is published to the shared Django cache as an immutable versioned snapshot -
the same pattern the RFM module uses - so dashboard reads are pure cache/
memory hits and the heavy scan runs at most once per invalidation.

A snapshot stays addressable while its RFM analysis version matches; a new
completed RFM run or a POST /api/clv/recalculate makes it unreachable (old
entries expire on their own TTL - neither cache backend can delete by pattern).
"""

import logging
import threading

from django.core.cache import cache
from django.db import close_old_connections

from rfm_analysis import utils as rfm_utils

from . import calc, queries, utils

logger = logging.getLogger(__name__)

# Per-process memo of the deserialized records + sort variants for the current
# token only, so paginated table reads never deserialize ~100k records twice.
_memo = {}
_memo_lock = threading.Lock()


def get_build_epoch():
    epoch = cache.get(utils.CLV_BUILD_EPOCH_KEY)
    return epoch if isinstance(epoch, int) and epoch >= 0 else 0


def bump_build_epoch():
    try:
        return cache.incr(utils.CLV_BUILD_EPOCH_KEY)
    except ValueError:
        cache.set(utils.CLV_BUILD_EPOCH_KEY, 1, None)
        return 1


def _current_token():
    """(token, rfm_version) of the snapshot the pointer addresses, if any."""
    pointer = cache.get(utils.CLV_STATE_POINTER_KEY)
    if isinstance(pointer, dict) and pointer.get('token'):
        return pointer['token'], pointer.get('rfm_version')
    return None, None


def _stored_rfm_version():
    """Latest persisted RFM version, memoized for one request burst.

    Every warm CLV read otherwise pays a remote Neon round trip for this
    single-row state query. The memo is short-lived and is dropped explicitly
    whenever an RFM run persists new results (`segment_store.store_records`
    deletes the cache key), so freshness rules are unchanged in practice.
    """
    from rfm_analysis import segment_store
    memo = cache.get(utils.CLV_STORED_RFM_VERSION_KEY)
    if isinstance(memo, dict) and 'version' in memo:
        return memo['version']
    version = segment_store.latest_version()
    cache.set(utils.CLV_STORED_RFM_VERSION_KEY, {'version': version},
              utils.STORED_RFM_VERSION_TTL_SECONDS)
    return version


def state_is_current():
    """True when the published snapshot matches the stored RFM analysis."""
    token, rfm_version = _current_token()
    if token is None:
        return False
    stored = _stored_rfm_version()
    if rfm_version != stored:
        return False
    return cache.get(utils.state_meta_key(token)) is not None


def get_meta():
    token, _ = _current_token()
    if token is None:
        return None
    return cache.get(utils.state_meta_key(token))


def get_records():
    token, _ = _current_token()
    if token is None:
        return None
    with _memo_lock:
        memo = _memo.get('records')
        if memo and memo['token'] == token:
            return memo['records']
    payload = cache.get(utils.state_records_key(token))
    if not payload:
        return None
    records = payload['records']
    with _memo_lock:
        _memo['records'] = {'token': token, 'records': records}
    return records


def build_state():
    """Compute the CLV dashboard state with SQL aggregation - no 100k-row load.

    Summary, value tiers, segment analysis and the population Future-CLV
    averages are database-side aggregates over the persisted RFM result table
    (`queries.fetch_clv_aggregates`, `fetch_tier_counts`,
    `fetch_segment_analysis`); the only data that genuinely needs the orders
    table is cohort survival, computed as one server-side aggregate into a tiny
    monthly histogram. Nothing streams the ~100k buyers into Python, which is
    what took ~65 s over the remote connection before. The compact meta is
    published as an immutable version-keyed snapshot, so dashboard reads are
    pure cache hits and the aggregation runs at most once per RFM version. The
    customer list and detail are served per page straight from the table by the
    views, so no page request ever loads the population either.

    Raises on database failure.
    """
    import time
    started = time.perf_counter()

    from rfm_analysis import segment_store
    state = segment_store.get_state()
    cutoff = state.analysis_date if state else None
    cutoff_iso = cutoff.isoformat() if cutoff else None
    rfm_version = state.version if state else None

    # Cohort survival first: its pooled curve feeds the Future-CLV SQL
    # expression used by every aggregate below.
    matrix = queries.fetch_cohort_matrix()
    if matrix and matrix.get('cells'):
        retention = calc.retention_report(matrix, cutoff)
    else:
        retention = _empty_retention(cutoff)
    future_expr = calc.future_clv_sql(retention)

    agg = queries.fetch_clv_aggregates(future_sql=future_expr)
    if agg is None:
        # No persisted RFM results to aggregate (or a backend without them):
        # fall back to the per-buyer order build so CLV still produces results.
        return _build_from_orders()

    queries.set_tier_boundaries(agg['high_value'], agg['medium_value'])

    tier_counts = queries.fetch_tier_counts(agg['high_value'], agg['medium_value']) \
        or {tier: 0 for tier in utils.VALUE_TIERS}
    tiers = [{'tier': tier, 'count': tier_counts.get(tier, 0)}
             for tier in utils.VALUE_TIERS]
    high_value_count = tier_counts.get(utils.TIER_HIGH, 0)
    buyer_count = agg['buyer_count'] or 1
    segments = queries.fetch_segment_analysis(future_sql=future_expr) or []

    snapshot = {
        'status': 'completed',
        'computed_at': utils.utcnow().isoformat(),
        'cutoff_date': cutoff_iso,
        'rfm_version': rfm_version,
        'monetary_source': 'rfm_stored',
        'buyer_count': agg['buyer_count'],
        'totals': {
            'total_historical_revenue': agg['total_revenue'],
            'avg_historical_clv': agg['avg_historical_clv'],
            'high_value_count': high_value_count,
            'high_value_pct': round(100.0 * high_value_count / buyer_count, 1),
            'avg_future_clv': agg.get('avg_future_clv'),
            'avg_total_clv': agg.get('avg_total_clv'),
            'future_clv_eligible_count': agg.get('future_supported_count', 0),
        },
        'tiers': tiers,
        'at_risk_count': agg['at_risk_count'],
        'segments': segments,
        'tier_boundaries': {'high': agg['high_value'], 'medium': agg['medium_value']},
        'cohorts': retention,
        'future_clv_status': retention['status'],
        'future_clv_message': retention.get('message'),
        'assumptions': {
            'min_tenure_days': round(utils.MIN_TENURE_YEARS * utils.DAYS_PER_YEAR),
            'high_percentile': utils.CLV_HIGH_PERCENTILE,
            'medium_percentile': utils.CLV_MEDIUM_PERCENTILE,
            'min_mature_retention_ages': utils.MIN_MATURE_RETENTION_AGES,
            'retention_period': 'calendar months from first to last valid purchase',
            'lifespan_model': ('discrete right-truncated survival over the pooled '
                               'monthly cohort curve; remaining lifespan is a '
                               'conditional approximation, never extrapolated '
                               'past the observed horizon'),
        },
        'compute_ms': round((time.perf_counter() - started) * 1000, 2),
    }
    return publish(snapshot)


def _iso(value):
    return value.isoformat() if hasattr(value, 'isoformat') else value


def _finalize(buyers, retention, rfm_version, cutoff_iso, fallback_count, started):
    """Shared tail of the build: tiers, future CLV, aggregates, publish."""
    import time
    future_supported = retention['status'] == utils.STATUS_OK

    # --- Stage 3: percentile value tiers + future CLV ------------------------
    high_value, medium_value = calc.tier_boundaries(
        [b['historical_clv'] for b in buyers])

    for buyer in buyers:
        buyer['clv_tier'] = calc.classify_tier(
            buyer['historical_clv'], high_value, medium_value)
        remaining, future, total = calc.future_for_customer(
            historical_clv=buyer['historical_clv'], aov=buyer['aov'],
            order_count=buyer['order_count'],
            first_purchase_date=buyer.get('first_purchase_date'),
            retention=retention)
        buyer['remaining_lifespan_years'] = remaining
        buyer['future_clv'] = future
        buyer['total_clv'] = total

    buyers.sort(key=lambda b: b['customer_id'])

    # --- Stage 4: aggregates -------------------------------------------------
    totals = _aggregate_totals(buyers, future_supported)
    tiers = _tier_distribution(buyers)
    at_risk_count = sum(1 for b in buyers
                        if b['rfm_segment'] == rfm_utils.SEGMENT_AT_RISK)
    segments = _rfm_segment_analysis(buyers, future_supported)

    snapshot = {
        'status': 'completed',
        'computed_at': utils.utcnow().isoformat(),
        'cutoff_date': cutoff_iso,
        'rfm_version': rfm_version,
        'monetary_source': _monetary_source_label(len(buyers), fallback_count),
        'buyer_count': len(buyers),
        'totals': totals,
        'tiers': tiers,
        'at_risk_count': at_risk_count,
        'segments': segments,
        'tier_boundaries': {'high': high_value, 'medium': medium_value},
        'cohorts': retention,
        'future_clv_status': retention['status'],
        'future_clv_message': retention.get('message'),
        'assumptions': {
            'min_tenure_days': round(utils.MIN_TENURE_YEARS * utils.DAYS_PER_YEAR),
            'high_percentile': utils.CLV_HIGH_PERCENTILE,
            'medium_percentile': utils.CLV_MEDIUM_PERCENTILE,
            'min_mature_retention_ages': utils.MIN_MATURE_RETENTION_AGES,
            'retention_period': 'calendar months from first to last valid purchase',
            'lifespan_model': ('discrete right-truncated survival over the pooled '
                               'monthly cohort curve; remaining lifespan is a '
                               'conditional approximation, never extrapolated '
                               'past the observed horizon'),
        },
        'compute_ms': None,
    }
    snapshot['compute_ms'] = round((time.perf_counter() - started) * 1000, 2)
    return publish(snapshot, buyers)


def _empty_retention(cutoff):
    """A valid no-cohort-data survival report (insufficient, never invented)."""
    return {
        'cutoff_date': cutoff.isoformat() if cutoff else None,
        'observation_horizon': None,
        'horizon_period': None,
        'unit': 'month',
        'rows': [],
        'mature_ages': [],
        'retention_probabilities': {0: 1.0},
        'status': utils.STATUS_INSUFFICIENT_DATA,
        'message': utils.INSUFFICIENT_DATA_MESSAGE,
    }


def _cohort_matrix_from_orders(buyers):
    """SQLite fallback: build the cohort matrix from per-buyer order years.

    Only used on a backend without the live `public.orders` table for the server-
    side aggregate; reads the same eligibility aggregate the RFM run uses.
    """
    rows, _ = queries.fetch_buyer_clv_rows()
    return calc.build_cohort_matrix(rows)


def _build_from_orders():
    """Original full-scan build: used only before any RFM result exists."""
    import time
    started = time.perf_counter()
    rows, cutoff_iso = queries.fetch_buyer_clv_rows()
    rfm_version, stored = queries.fetch_stored_rfm_metrics()
    if not rows:
        return publish(_empty_snapshot(rfm_version))
    cutoff = calc.parse_iso_date(cutoff_iso)
    buyers = []
    fallback_count = 0
    for row in rows:
        stored_row = stored.get(row['customer_id']) or {}
        history = calc.derive_history(
            order_count=row['order_count'],
            revenue=row['revenue'],
            stored_monetary=stored_row.get('monetary'),
            first_date=calc.parse_iso_date(row['first_purchase_date']),
            last_date=calc.parse_iso_date(row['last_purchase_date']),
            cutoff=cutoff,
        )
        if history['revenue_source'] != 'rfm_monetary':
            fallback_count += 1
        history.update({
            'customer_id': row['customer_id'],
            'customer_name': row.get('customer_name'),
            'first_purchase_date': row['first_purchase_date'],
            'last_purchase_date': row['last_purchase_date'],
            'rfm_segment': stored_row.get('segment'),
        })
        buyers.append(history)
    matrix = calc.build_cohort_matrix(rows)
    retention = calc.retention_report(matrix, cutoff)
    return _finalize(buyers, retention, rfm_version, cutoff_iso, fallback_count, started)


def _monetary_source_label(buyer_count, fallback_count):
    """Audit label for how much of Historical CLV came from stored RFM data."""
    if buyer_count == 0 or fallback_count == buyer_count:
        return 'orders_aggregate'
    if fallback_count == 0:
        return 'rfm_stored'
    return 'mixed_orders_fallback'


def _empty_snapshot(rfm_version):
    return {
        'status': 'completed',
        'computed_at': utils.utcnow().isoformat(),
        'cutoff_date': None,
        'rfm_version': rfm_version,
        'monetary_source': None,
        'buyer_count': 0,
        'totals': {'total_historical_revenue': 0, 'avg_historical_clv': 0,
                   'high_value_count': 0, 'high_value_pct': 0,
                   'avg_future_clv': None, 'avg_total_clv': None,
                   'future_clv_eligible_count': 0},
        'tiers': [{'tier': t, 'count': 0} for t in utils.VALUE_TIERS],
        'at_risk_count': 0,
        'segments': [],
        'tier_boundaries': {'high': None, 'medium': None},
        'cohorts': None,
        'future_clv_status': utils.STATUS_INSUFFICIENT_DATA,
        'future_clv_message': utils.INSUFFICIENT_DATA_MESSAGE,
        'assumptions': {},
        'compute_ms': 0,
    }


def _aggregate_totals(buyers, future_supported):
    count = len(buyers) or 1
    historical = [b['historical_clv'] for b in buyers]
    total_revenue = round(sum(historical), 2)
    future_values = [b['future_clv'] for b in buyers] if future_supported else []
    future_values = [v for v in future_values if v is not None]
    return {
        'total_historical_revenue': total_revenue,
        'avg_historical_clv': round(total_revenue / count, 2),
        'high_value_count': sum(1 for b in buyers if b['clv_tier'] == utils.TIER_HIGH),
        'high_value_pct': round(100.0 * sum(
            1 for b in buyers if b['clv_tier'] == utils.TIER_HIGH) / count, 1),
        'avg_future_clv': (round(sum(future_values) / len(future_values), 2)
                           if future_values else None),
        'avg_total_clv': (round(
            sum(b['total_clv'] for b in buyers if b['total_clv'] is not None)
            / max(len([b for b in buyers if b['total_clv'] is not None]), 1), 2)
            if future_values else None),
    }


def _tier_distribution(buyers):
    counts = {tier: 0 for tier in utils.VALUE_TIERS}
    for buyer in buyers:
        if buyer['clv_tier'] in counts:
            counts[buyer['clv_tier']] += 1
    return [{'tier': tier, 'count': counts[tier]} for tier in utils.VALUE_TIERS]


def _rfm_segment_analysis(buyers, future_supported):
    """Per RFM-segment customer value analysis (labels from the stored RFM run).

    Documented limitation: segment analysis attributes each buyer to their
    CURRENT RFM segment; no historical segment snapshots exist, so this is
    not a historical segment-retention analysis.
    """
    buckets = {}
    for buyer in buyers:
        key = buyer['rfm_segment'] or 'Unsegmented'
        entry = buckets.setdefault(key, {'count': 0, 'historical': 0.0,
                                         'future': [], 'orders': 0})
        entry['count'] += 1
        entry['historical'] += buyer['historical_clv']
        entry['orders'] += buyer['order_count']
        if future_supported and buyer['future_clv'] is not None:
            entry['future'].append(buyer['future_clv'])

    rows = []
    for segment, entry in buckets.items():
        count = entry['count'] or 1
        rows.append({
            'segment': segment,
            'customer_count': entry['count'],
            'avg_historical_clv': round(entry['historical'] / count, 2),
            'total_historical_clv': round(entry['historical'], 2),
            'avg_orders': round(entry['orders'] / count, 2),
            'avg_future_clv': (round(sum(entry['future']) / len(entry['future']), 2)
                               if entry['future'] else None),
        })
    rows.sort(key=lambda r: -r['total_historical_clv'])
    return rows


def publish(snapshot, buyers=None):
    """Store the meta (+ records) parts under one token and flip the pointer."""
    token = f'{get_build_epoch()}-{utils.utcnow().strftime("%Y%m%d%H%M%S")}'
    records = []
    if buyers is not None:
        for buyer in buyers:
            records.append({column: buyer.get(column) for column in utils.RECORD_PROJECTION})

    cache.set(utils.state_records_key(token),
              {'records': records}, utils.STATE_TTL_SECONDS)
    meta = dict(snapshot)
    meta['token'] = token
    cache.set(utils.state_meta_key(token), meta, utils.STATE_TTL_SECONDS)
    # Pointer flips last: readers can never observe a half-published state.
    cache.set(utils.CLV_STATE_POINTER_KEY,
              {'token': token, 'rfm_version': snapshot.get('rfm_version')},
              utils.STATE_TTL_SECONDS)

    with _memo_lock:
        _memo['records'] = {'token': token, 'records': records}
    return meta


# ---------------------------------------------------------------------------
# Background build + status (mirrors the RFM run protocol)
# ---------------------------------------------------------------------------
def set_run_status(status, **extra):
    payload = {'status': status}
    payload.update(extra)
    cache.set(utils.CLV_RUN_STATUS_KEY, payload, utils.STATE_TTL_SECONDS)
    return payload


def get_run_status():
    return cache.get(utils.CLV_RUN_STATUS_KEY) or {'status': 'never_run'}


def acquire_run_lock():
    return cache.add(utils.CLV_RUN_LOCK_KEY, 1, utils.RUN_LOCK_TTL_SECONDS)


def release_run_lock():
    cache.delete(utils.CLV_RUN_LOCK_KEY)


def run_build():
    """Build and publish synchronously, recording status (raises on failure)."""
    set_run_status('running', started_at=utils.utcnow().isoformat())
    try:
        meta = build_state()
        set_run_status('completed', finished_at=utils.utcnow().isoformat(),
                       compute_ms=meta.get('compute_ms'))
        return meta
    except Exception as exc:  # noqa: BLE001 - a background build must record it
        logger.exception('CLV state build failed')
        set_run_status('failed', error_type=type(exc).__name__)
        raise
    finally:
        release_run_lock()


def start_background_build(force=False):
    """Kick off a build on a worker thread. Returns (accepted, status).

    `force` (the recalculate endpoint) first makes the current snapshot
    unreachable by bumping the build epoch, so the rebuild recomputes from the
    current source data instead of being skipped as already fresh.
    """
    if force:
        if get_run_status().get('status') not in ('queued', 'running'):
            bump_build_epoch()
    elif state_is_current():
        return False, {'status': 'up_to_date'}

    if not acquire_run_lock():
        return False, get_run_status()

    set_run_status('queued', started_at=utils.utcnow().isoformat())

    def _worker():
        # A background thread owns its DB connection; Django only reaps them
        # between requests on the main thread.
        close_old_connections()
        try:
            run_build()
        except Exception:  # noqa: BLE001 - status already recorded as failed
            logger.warning('Background CLV build ended in failure')
        finally:
            close_old_connections()

    threading.Thread(target=_worker, name='clv-build', daemon=True).start()
    return True, {'status': 'queued'}


def ensure_state():
    """Serve the current snapshot; schedule a background build when absent.

    Called by every CLV GET endpoint. It never blocks on the ~100k-buyer
    computation and never serves a partial result: with no usable snapshot the
    caller reports available=False while the first build runs.
    """
    if state_is_current():
        return {'available': True, 'refreshing': False,
                'run_status': get_run_status()}
    accepted, run_status = start_background_build()
    if state_is_current():
        # A previous snapshot is still readable while the new one builds.
        return {'available': True, 'refreshing': accepted, 'run_status': run_status}
    return {'available': False, 'refreshing': accepted, 'run_status': run_status}
