"""Short-lived snapshot cache for RFM analyses (no permanent results table).

A completed run is stored as a versioned snapshot in the shared Django cache
(Redis when ``REDIS_URL`` is configured, otherwise LocMemCache), never in a
database table. A run computes into a new version and only publishes it by
flipping a small pointer key once the whole payload is present, so a dashboard
can never read a half-finished analysis.

The snapshot is split so the hot read paths stay cheap:

* ``snapshot:meta:{ver}``  - small aggregate summary (totals + segment counts).
  Read by the admin KPIs; deserialization is trivial.
* ``snapshot:records:{ver}`` - the full per-buyer list.

``get_index`` deserializes the records once per process per version and builds
an in-memory index (segment -> already-customer-sorted buckets, a Big Spender
tag bucket, and lazily cached per-field sort variants). Segment detail pages are
then served from that index instead of rescanning ~100k records on every
request, so the first page opens from cached memory in constant time and later
pages and default sorts never touch the database.

Keys:

* ``rfm:analysis:latest_version``   - the published version id (an integer).
* ``rfm:analysis:run_status``       - status of the most recent run request.
* ``rfm:analysis:run_lock``         - a short TTL lock preventing overlapping runs.
"""

import threading

from django.core.cache import cache

from . import utils

# Per-process memo of the deserialized + indexed records for the latest
# version. Only the newest version is retained; older ones are replaced.
_index_memo = {}
_index_lock = threading.Lock()

# The columns the customer drill-down table actually renders. Serving only
# these keeps the API payload small (the full record stays in the index and in
# the database; nothing is lost, the rest is simply not needed by the table).
TABLE_COLUMNS = (
    'customer_id', 'customer_name', 'segment', 'tags',
    'r_score', 'f_score', 'm_score',
)


def get_latest_version():
    version = cache.get(utils.RFM_SNAPSHOT_POINTER_KEY)
    return version if isinstance(version, int) and version >= utils.SNAPSHOT_VERSION_MIN else None


def get_meta(version=None):
    """Small aggregate summary for the admin KPI cards (no per-customer rows)."""
    version = version if version is not None else get_latest_version()
    if version is None:
        return None
    return cache.get(utils.snapshot_meta_key(version))


def _build_index(version, records, customer_ids):
    """Bucket records by segment (+ a Big Spender tag bucket).

    Records are stored sorted by customer_id at publish time, so every bucket is
    already ordered by customer_id ascending - the drill-down default sort - and
    its first page needs no sorting at all.
    """
    buckets = {}
    tagged = []
    for record in records:
        buckets.setdefault(record['segment'], []).append(record)
        if utils.TAG_BIG_SPENDER in (record.get('tags') or []):
            tagged.append(record)
    return {
        'version': version,
        'records': records,
        'customer_ids': customer_ids,
        'buckets': buckets,
        'tagged': tagged,
        # Lazily filled cache of non-default sort variants: {(sort, dir): list}.
        'sort_cache': {},
    }


def get_index(version=None):
    """Return the memoized index for a version, building it on first use."""
    version = version if version is not None else get_latest_version()
    if version is None:
        return None

    with _index_lock:
        memo = _index_memo.get('index')
        if memo and memo['version'] == version:
            return memo

    payload = cache.get(utils.snapshot_records_key(version))
    if not payload:
        return None

    index = _build_index(version, payload['records'], payload['customer_ids'])
    with _index_lock:
        _index_memo['index'] = index
    return index


def get_records(version=None):
    """Return (records, customer_ids) for a version, memoized per process."""
    index = get_index(version)
    if not index:
        return None, None
    return index['records'], index['customer_ids']


def get_segment_base(segment, sort='customer_id', direction='asc'):
    """Return (rows, version) for a segment, ordered as requested.

    The customer_id-ascending default is served directly from the prebuilt
    bucket (no sort, no copy). Any other sort field/direction is computed once
    and memoized in the per-version ``sort_cache``, so repeated paging and
    re-sorting requests hit cached memory instead of re-sorting ~thousands of
    rows on every call.
    """
    index = get_index()
    if not index:
        return None, None

    version = index['version']
    if segment == utils.TAG_BIG_SPENDER:
        bucket = index['tagged']
    else:
        bucket = index['buckets'].get(segment)
        if bucket is None:
            return [], version

    if sort == 'customer_id' and direction == 'asc':
        return bucket, version

    key = (sort, direction)
    cached = index['sort_cache'].get(key)
    if cached is None:
        rows = list(bucket)
        reverse = direction == 'desc'
        try:
            rows.sort(key=lambda r: (r.get(sort) is None, r.get(sort)), reverse=reverse)
        except TypeError:
            rows.sort(key=lambda r: str(r.get(sort)), reverse=reverse)
        cached = rows
        index['sort_cache'][key] = cached
    return cached, version


def project_row(record):
    """Reduce a full record to just the drill-down table columns."""
    return {column: record.get(column) for column in TABLE_COLUMNS}


def publish_snapshot(snapshot, version=None):
    """Write a new immutable version and atomically point 'latest' at it.

    `snapshot` is split into its small `meta` part and its large `records`
    part, stored under separate keys. The version pointer flips only after both
    are present, so readers never observe a partial analysis.

    `version` lets the caller keep versions monotonic across restarts (the
    durable per-customer segment store outlives this cache, so a run must not
    restart numbering at 1 and reuse an older offer-cache key).
    """
    previous = get_latest_version()
    new_version = version if version is not None else (previous or 0) + 1

    records = snapshot.pop('records', [])
    customer_ids = snapshot.pop('customer_ids', [])
    meta = dict(snapshot)
    meta['version'] = new_version
    meta['record_count'] = len(records)
    meta['computed_at'] = utils.utcnow().isoformat()

    cache.set(utils.snapshot_records_key(new_version),
              {'records': records, 'customer_ids': customer_ids},
              utils.SNAPSHOT_TTL_SECONDS)
    cache.set(utils.snapshot_meta_key(new_version), meta, utils.SNAPSHOT_TTL_SECONDS)
    # Pointer flips last: before this line no reader can see the new version.
    cache.set(utils.RFM_SNAPSHOT_POINTER_KEY, new_version, utils.SNAPSHOT_TTL_SECONDS)

    if previous is not None:
        _invalidate_for_version(previous)

    # Segmentation just changed, so every cached per-customer offer list is
    # stale by definition: bumping the analysis epoch makes those keys
    # unreachable instead of waiting out the short offer TTL.
    bump_analysis_epoch()

    # Prime this process's index so the very first dashboard/detail read is
    # already served from memory.
    index = _build_index(new_version, records, customer_ids)
    with _index_lock:
        _index_memo['index'] = index

    return new_version


def get_snapshot():
    """Full snapshot (meta + records) for callers that need both at once."""
    version = get_latest_version()
    if version is None:
        return None
    meta = get_meta(version)
    if not meta:
        return None
    records, customer_ids = get_records(version)
    if records is None:
        return None
    full = dict(meta)
    full['records'] = records
    full['customer_ids'] = customer_ids
    return full


def set_run_status(status, **extra):
    payload = {'status': status}
    payload.update(extra)
    cache.set(utils.RFM_RUN_STATUS_KEY, payload, utils.SNAPSHOT_TTL_SECONDS)
    return payload


def get_run_status():
    return cache.get(utils.RFM_RUN_STATUS_KEY) or {'status': 'never_run'}


def acquire_run_lock():
    """Return True and hold a short TTL lock, or False if a run is in progress.

    ``add`` only succeeds when the key is absent, giving an atomic test-and-set
    shared across workers on Redis. The lock expires on its own so a crashed run
    cannot wedge the dashboard forever.
    """
    return cache.add(utils.RFM_RUN_LOCK_KEY, 1, utils.RUN_LOCK_TTL_SECONDS)


def release_run_lock():
    cache.delete(utils.RFM_RUN_LOCK_KEY)


def try_freshness_nudge():
    """Return True once per cooldown window when a freshness check may be run.

    The dashboard read path must not turn every page open into a database state
    read plus a refresh decision; this rate limits the background nudge the same
    way the offer self-heal does, on its own key so it never blocks an explicit
    admin "recalculate" request.
    """
    return cache.add(utils.RFM_FRESHNESS_NUDGE_KEY,
                     1,
                     utils.RFM_FRESHNESS_NUDGE_SECONDS)


def get_campaign_epoch():
    """Monotonic counter identifying the current campaign configuration.

    Reading it is one cheap cache get; it never needs a database query.
    """
    epoch = cache.get(utils.RFM_CAMPAIGN_EPOCH_KEY)
    return epoch if isinstance(epoch, int) and epoch >= 0 else 0


def _bump_epoch(key):
    try:
        return cache.incr(key)
    except ValueError:
        # First bump after a restart: start from 1 and never expire the counter,
        # otherwise a plain cache expiry would silently reuse old offer keys.
        cache.set(key, 1, None)
        return 1


def bump_campaign_epoch():
    """Invalidate every cached per-customer offer list.

    Called by the admin campaign write endpoints and when a coupon is redeemed.
    Because the epoch is part of the offer key, old entries simply stop being
    addressed (and expire on their own short TTL), which works identically on
    LocMemCache and Redis - neither can enumerate keys by pattern.
    """
    return _bump_epoch(utils.RFM_CAMPAIGN_EPOCH_KEY)


def get_analysis_epoch():
    """Monotonic counter identifying the currently stored segmentation."""
    epoch = cache.get(utils.RFM_ANALYSIS_EPOCH_KEY)
    return epoch if isinstance(epoch, int) and epoch >= 0 else 0


def bump_analysis_epoch():
    """Invalidate cached customer offers because segment labels changed."""
    return _bump_epoch(utils.RFM_ANALYSIS_EPOCH_KEY)


def offer_cache_key(customer_id):
    """Key of one customer's cached offer list.

    Both epochs are in the key, so serving a cached list needs no database query
    at all: a campaign change or a newly completed analysis makes the key
    unreachable and the next request recomputes from live data.
    """
    return (f'rfm:offers:{get_campaign_epoch()}'
            f':{get_analysis_epoch()}:{customer_id}')


def try_offer_self_heal():
    """Return True once per cooldown window when a customer may start a run.

    The snapshot is cache-only, so a freshly started process legitimately has
    published campaigns and no analysis yet. Customer traffic may then ask for a
    background run, but only on this rate limit - the run lock alone would still
    allow a new full computation every time a previous one fails.
    """
    return cache.add(utils.RFM_OFFER_SELF_HEAL_KEY,
                     1,
                     utils.OFFER_SELF_HEAL_COOLDOWN_SECONDS)


def get_cached_offers(customer_id):
    return cache.get(offer_cache_key(customer_id))


def set_cached_offers(customer_id, offers):
    if not isinstance(offers, dict) or offers.get('version') is None:
        # Nothing was decided yet (no completed analysis at all). Caching that
        # would hide a customer's real offers until the TTL expired.
        return
    cache.set(offer_cache_key(customer_id), offers, utils.OFFER_CACHE_TTL_SECONDS)


def _invalidate_for_version(version):
    # Cached customer offer lists are keyed on the campaign and analysis epochs,
    # so they are already unreachable once a run publishes; these entries expire
    # on their own short TTL. Redis-backed deployments could add a pattern-delete
    # here; LocMemCache cannot enumerate keys.
    cache.delete(utils.snapshot_records_key(version))
    cache.delete(utils.snapshot_meta_key(version))
    cache.delete(never_purchased_key(version))


# The Never Purchased population is tiny (customers with no eligible purchase)
# but its lookup is a NOT-EXISTS anti-join over the whole order history, so it
# is fetched once per version and served from cache for every page/search.
def never_purchased_key(version):
    return f'rfm:never_purchased:{version}'


def get_never_purchased(version):
    if version is None:
        return None
    return cache.get(never_purchased_key(version))


def set_never_purchased(version, rows):
    if version is None:
        return
    cache.set(never_purchased_key(version), rows, utils.SNAPSHOT_TTL_SECONDS)


# Dashboard KPIs + segment distribution + K-Means clusters, derived by one SQL
# aggregation over the persisted result table (see `queries.fetch_dashboard_bundle`).
# Keyed by the analysis version AND the clustering epoch: a completed RFM refresh
# bumps the version, re-running clustering bumps the epoch, and either makes the
# previous aggregate unreachable so the next read recomputes from current data -
# never a stale segment mix or a stale clustering. A warm dashboard render is a
# pure cache read (zero database round trips), which is what removes the ~250 ms
# per-query remote-Neon latency from every page load once the bundle is cached.
# A further per-process memo of the bundle was deliberately NOT added: the epoch
# counter lives in this same cache and restarts at 1 after a clear, so an
# in-process copy could be matched to a reused epoch and served superseded
# numbers. One LocMem read of a small aggregate payload is microseconds, and the
# durable `dashboard_cache` snapshot covers the cold-process case instead.
def dashboard_bundle_key(version, kmeans_epoch):
    return f'rfm:dashboard_bundle:{version}:{kmeans_epoch}'


def get_dashboard_bundle(version, kmeans_epoch):
    if version is None:
        return None
    return cache.get(dashboard_bundle_key(version, kmeans_epoch))


def set_dashboard_bundle(version, kmeans_epoch, payload):
    if version is None:
        return
    cache.set(dashboard_bundle_key(version, kmeans_epoch), payload,
              utils.SNAPSHOT_TTL_SECONDS)


def delete_dashboard_bundle(version):
    """Drop this cache's copy of a version's bundle."""
    if version is None:
        # LocMemCache/Redis cannot enumerate keys by pattern; a clustering run
        # already made every old key unreachable by bumping the epoch.
        return
    cache.delete(dashboard_bundle_key(version, get_kmeans_epoch()))


# The single-row analysis state (version / dates / buyer_count) that every
# summary read needs to know *which* cached bundle to load and how old the
# analysis is. Reading it is normally one remote round trip; memoizing it turns
# the steady-state summary into a pure cache path. It is written fresh by a
# completed run and dropped whenever results are re-persisted, so it can never
# point a reader at a superseded version.
def get_state_memo():
    return cache.get(utils.RFM_ANALYSIS_STATE_MEMO_KEY)


def set_state_memo(payload):
    cache.set(utils.RFM_ANALYSIS_STATE_MEMO_KEY, payload,
              utils.SNAPSHOT_TTL_SECONDS)


def clear_state_memo():
    cache.delete(utils.RFM_ANALYSIS_STATE_MEMO_KEY)


# Bumped whenever a K-Means clustering run persists new labels. Part of the
# bundle cache key, so a rerun is visible on the next summary read without
# waiting for (or forcing) a full RFM recompute.
def get_kmeans_epoch():
    epoch = cache.get(utils.RFM_KMEANS_EPOCH_KEY)
    return epoch if isinstance(epoch, int) and epoch >= 0 else 0


def bump_kmeans_epoch():
    return _bump_epoch(utils.RFM_KMEANS_EPOCH_KEY)


# The single-row K-Means run state (which RFM version was clustered, when, and
# how each cluster was mapped) is memoized exactly like the analysis state memo:
# the dashboard needs it on every render, and one cached read replaces a remote
# round trip. Written fresh by a completed clustering run.
def get_kmeans_state_memo():
    return cache.get(utils.RFM_KMEANS_STATE_MEMO_KEY)


def set_kmeans_state_memo(payload):
    cache.set(utils.RFM_KMEANS_STATE_MEMO_KEY, payload, utils.SNAPSHOT_TTL_SECONDS)


def clear_kmeans_state_memo():
    cache.delete(utils.RFM_KMEANS_STATE_MEMO_KEY)


def acquire_kmeans_run_lock():
    """True when this caller may run clustering; False when one is in progress.

    Same atomic test-and-set as the analysis lock, on its own key so a
    clustering run and an analysis run never block each other.
    """
    return cache.add(utils.RFM_KMEANS_RUN_LOCK_KEY, 1,
                     utils.KMEANS_RUN_LOCK_TTL_SECONDS)


def release_kmeans_run_lock():
    cache.delete(utils.RFM_KMEANS_RUN_LOCK_KEY)
