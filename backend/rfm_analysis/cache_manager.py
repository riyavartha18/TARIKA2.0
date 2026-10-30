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


def publish_snapshot(snapshot):
    """Write a new immutable version and atomically point 'latest' at it.

    `snapshot` is split into its small `meta` part and its large `records`
    part, stored under separate keys. The version pointer flips only after both
    are present, so readers never observe a partial analysis.
    """
    previous = get_latest_version()
    new_version = (previous or 0) + 1

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


def offer_cache_key(version, customer_id):
    return f'rfm:offers:{version}:{customer_id}'


def get_cached_offers(version, customer_id):
    if version is None:
        return None
    return cache.get(offer_cache_key(version, customer_id))


def set_cached_offers(version, customer_id, offers):
    if version is None:
        return
    cache.set(offer_cache_key(version, customer_id), offers, utils.OFFER_CACHE_TTL_SECONDS)


def _invalidate_for_version(version):
    # Offer keys are version-scoped, so once the pointer moves they are never
    # requested again and expire on their own short TTL. Redis-backed
    # deployments could add a pattern-delete here; LocMemCache cannot enumerate.
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
