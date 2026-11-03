"""K-Means++ (k=4) clustering over the RFM values the pipeline already stored.

Why a separate module reading the persisted results (never a re-scan): the RFM
run has already computed, for every eligible buyer, Recency / Frequency /
Monetary in `rfm_customer_segments` (the exact definitions CLV reuses). This
module consumes *those* stored values as-is, so nothing is recalculated and the
business definition of each metric is untouched.

The pipeline is the textbook one, and it is the real algorithm doing the
grouping - no RFM percentile rule is used here:

1. Standardize Recency / Frequency / Monetary with `StandardScaler`
   (`z = (x - mean) / std`), fitted on the buyer population being clustered.
   Only these three features are scaled; CLV is never an input, and no log
   transform is applied (the existing pipeline never required one).
2. Run `KMeans(n_clusters=4, init='k-means++', n_init=10, random_state=42)` in
   that standardized space. K-Means++ spreads the four initial centroids
   (first one sampled from the data, each next one with probability proportional
   to the squared distance to the closest already-chosen centroid), then Lloyd
   iterations re-assign every buyer to the nearest centroid by Euclidean
   distance and move each centroid to the mean of its members until convergence.
3. Profile every cluster from the ORIGINAL (unscaled) RFM means plus the stored
   purchase history (tenure, share of one-time buyers) and map the four numeric
   clusters onto the four business categories through an optimal one-to-one
   assignment (Hungarian algorithm) - the mapping is derived from the actual
   profiles, never hardcoded to a cluster id.
4. Grade each mapped label against the same unscaled profiles. A label the data
   does not actually support is reported with the numbers that contradict it
   instead of being presented silently as a finding.
5. Persist `kmeans_cluster_id` + `kmeans_category` back onto each buyer's
   existing row (one set-based UPDATE through a temporary table), leaving the
   original RFM values and the rule-based `segment` - and therefore every CLV
   and campaign dependency - untouched. The run itself (which RFM version was
   clustered, when, the mapping and the scaler statistics) is stored once in
   `rfm_kmeans_run_state`.

Re-running overwrites the same rows' two clustering columns, so it never
creates duplicate customers or duplicate segmentation entries. Buyers whose
original RFM values are unchanged between runs keep landing in the same cluster
(the algorithm is seeded), so a rerun is stable.
"""

import logging
import time

import numpy as np
from scipy.optimize import linear_sum_assignment
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

from . import utils
from .models import ClusteringRun, CustomerSegment, KmeansRunState

logger = logging.getLogger(__name__)

# Buyers are clustered in one pass (~100k compact rows). The non-PostgreSQL
# write path chunks its `WHERE customer_id IN (...)` updates so no statement
# grows unbounded; PostgreSQL writes the whole labelling set-based in one pass.
UPDATE_BATCH_SIZE = 2000
# Rows per multi-row INSERT of the temporary label table (3 parameters each).
LABEL_INSERT_BATCH = 2000

# Business prototypes in the normalized [0,1] profile space
# (recency_highness, frequency_highness, monetary_highness). `recency_highness`
# is 1 for the cluster with the LARGEST Recency in days (least recent) and 0 for
# the most recent one, so "low Recency" maps to a value near 0 here. These are
# interpretation anchors only; the four clusters are matched to them by distance,
# so the outcome always depends on the real data, never on a fixed cluster id.
#   High Spending     - the top-Monetary group, still reasonably recent
#   Frequent Buyers   - the top-Frequency group, recent repeat purchasers
#   At Risk           - the least recent (most dormant) group
#   Moderate Spending - the middle residual on all three dimensions
CATEGORY_PROTOTYPES = {
    utils.KMEANS_CATEGORY_HIGH_SPENDING: (0.25, 0.55, 1.00),
    utils.KMEANS_CATEGORY_FREQUENT_BUYERS: (0.10, 1.00, 0.55),
    utils.KMEANS_CATEGORY_AT_RISK: (0.95, 0.40, 0.45),
    utils.KMEANS_CATEGORY_MODERATE_SPENDING: (0.40, 0.40, 0.35),
}

# Business meaning of the frequency gates used to *verify* a mapped label (they
# never assign a cluster): a "frequent buyer" group must show a genuine repeat
# habit, so a cluster whose average order count is at or below one purchase
# cannot honestly carry that label.
SINGLE_ORDER_FREQUENCY = 1
LOW_ORDER_FREQUENCY = 2
REPEAT_HABIT_FREQUENCY = 2


# ---------------------------------------------------------------------------
# Loading the clustering input
# ---------------------------------------------------------------------------
def load_dataset():
    """(customer_ids, features, tenure_days) for every persisted buyer.

    Only buyers with all three RFM metrics present are eligible (a completed RFM
    run always stores all three, so this simply skips not-yet-analyzed rows).
    `features` is an N x 3 float array of [recency, frequency, monetary] in their
    ORIGINAL units - nothing here is scaled or rewritten. `tenure_days` is the
    observed purchase span (last - first purchase) per buyer, NaN when the run
    did not store the dates; it is used only to *interpret* a cluster.
    """
    rows = list(
        CustomerSegment.objects
        .exclude(recency__isnull=True)
        .exclude(frequency__isnull=True)
        .exclude(monetary__isnull=True)
        .values_list('customer_id', 'recency', 'frequency', 'monetary',
                     'first_purchase_date', 'last_purchase_date')
    )
    if not rows:
        return [], np.empty((0, 3), dtype='float64'), np.empty((0,), dtype='float64')

    customer_ids = [r[0] for r in rows]
    features = np.array(
        [[float(r[1]), float(r[2]), float(r[3])] for r in rows],
        dtype='float64',
    )
    tenure = np.array([_tenure_days(r[4], r[5]) for r in rows], dtype='float64')
    return customer_ids, features, tenure


def load_rfm_dataset():
    """Backwards-compatible (customer_ids, features) view of `load_dataset`."""
    customer_ids, features, _tenure = load_dataset()
    return customer_ids, features


def _tenure_days(first, last):
    if first is None or last is None:
        return float('nan')
    return float((last - first).days)


# ---------------------------------------------------------------------------
# Cluster profiles (always from the ORIGINAL, unscaled values)
# ---------------------------------------------------------------------------
def _cluster_profiles(features, tenure, labels, k, cluster_means, cluster_sizes):
    """Per-cluster descriptive profile used for mapping and for the audit trail.

    Every number is computed on the unscaled Recency / Frequency / Monetary and
    the stored purchase dates, because the business meaning of a cluster is
    defined in those units - the standardized values are an algorithm detail.
    """
    profiles = []
    for idx in range(k):
        mask = labels == idx
        size = int(cluster_sizes[idx])
        rec = features[mask, 0] if size else np.empty(0)
        freq = features[mask, 1] if size else np.empty(0)
        mon = features[mask, 2] if size else np.empty(0)
        t = tenure[mask & ~np.isnan(tenure)] if size else np.empty(0)
        profiles.append({
            'cluster_id': int(idx),
            'customer_count': size,
            'avg_recency': _mean(cluster_means[idx][0], size),
            'avg_frequency': _mean(cluster_means[idx][1], size),
            'avg_monetary': _mean(cluster_means[idx][2], size),
            'median_recency': _round_or_none(np.median(rec)) if size else None,
            'median_frequency': _round_or_none(np.median(freq)) if size else None,
            'median_monetary': _round_or_none(np.median(mon)) if size else None,
            'share_single_order': _share(freq, SINGLE_ORDER_FREQUENCY, size),
            'share_low_order': _share(freq, LOW_ORDER_FREQUENCY, size),
            'avg_tenure_days': (_round_or_none(t.mean()) if t.size else None),
        })
    return profiles


def _mean(value, size):
    return round(float(value), 2) if size else None


def _round_or_none(value):
    return round(float(value), 2) if value is not None and not np.isnan(value) else None


def _share(values, threshold, size):
    """Share (0-1) of the cluster whose Frequency is at or below a threshold."""
    if not size:
        return None
    return round(float((values <= threshold).mean()), 4)


def _population_baselines(features, tenure):
    """Reference points of the whole clustered population for the label check."""
    freq = features[:, 1]
    rec = features[:, 0]
    mon = features[:, 2]
    known_tenure = tenure[~np.isnan(tenure)]
    return {
        'buyers': int(features.shape[0]),
        'median_frequency': _round_or_none(np.median(freq)),
        'mean_frequency': _round_or_none(freq.mean()),
        'mean_recency': _round_or_none(rec.mean()),
        'min_recency': _round_or_none(rec.min()),
        'mean_monetary': _round_or_none(mon.mean()),
        'median_tenure_days': (_round_or_none(np.median(known_tenure))
                               if known_tenure.size else None),
        'share_single_order': (round(float((freq <= SINGLE_ORDER_FREQUENCY).mean()), 4)
                               if freq.size else None),
    }


# ---------------------------------------------------------------------------
# Mapping: numeric cluster -> business category
# ---------------------------------------------------------------------------
def _normalize_profile(means):
    """Min-max normalize the per-cluster mean matrix along each dimension.

    `means` is K x 3 (mean recency, frequency, monetary per cluster) in the
    original units. Returns a K x 3 array in [0,1]; a dimension with no spread
    across clusters becomes 0.5 (nothing to distinguish it by).
    """
    lo = means.min(axis=0)
    hi = means.max(axis=0)
    span = hi - lo
    norm = np.full_like(means, 0.5)
    for col in range(means.shape[1]):
        if span[col] > 0:
            norm[:, col] = (means[:, col] - lo[col]) / span[col]
    return norm


def map_clusters_to_categories(cluster_means, cluster_sizes):
    """Assign each present cluster a distinct business category, from profiles.

    `cluster_means` is a K x 3 array of each cluster's ORIGINAL RFM means;
    `cluster_sizes` the matching member counts. Returns
    ({cluster_index: {'category', 'confidence'}}, [unsupported_categories]).

    The mapping is a global optimal one-to-one assignment (Hungarian algorithm)
    minimizing the total profile distance, so it never depends on a cluster's
    numeric id. When fewer than four clusters actually have members, some
    categories genuinely have no cluster to map onto and are reported instead of
    being forced onto the wrong group.
    """
    categories = list(utils.KMEANS_CATEGORIES)
    present = [idx for idx, size in enumerate(cluster_sizes) if size > 0]
    if not present:
        return {}, list(categories)

    norm = _normalize_profile(cluster_means)
    prototypes = np.array([CATEGORY_PROTOTYPES[c] for c in categories])

    # cost[i][j] = euclidean distance of present cluster i to category j.
    cost = np.linalg.norm(
        norm[present][:, None, :] - prototypes[None, :, :], axis=2)

    row_ind, col_ind = linear_sum_assignment(cost)

    mapping = {}
    assigned_categories = set()
    for r, c in zip(row_ind, col_ind):
        cluster_idx = present[r]
        category = categories[c]
        assigned_categories.add(category)
        # Confidence from the decision margin: how much closer the chosen
        # category is than the runner-up for this cluster (relative to scale).
        row = np.sort(cost[r])
        margin = float(row[1] - row[0]) if len(row) > 1 else float(row[0])
        if margin >= 0.35:
            confidence = 'high'
        elif margin >= 0.15:
            confidence = 'medium'
        else:
            confidence = 'low'
        mapping[cluster_idx] = {'category': category, 'confidence': confidence}

    unsupported = [c for c in categories if c not in assigned_categories]
    return mapping, unsupported


# ---------------------------------------------------------------------------
# Verification: does the mapped label actually match the cluster's profile?
# ---------------------------------------------------------------------------
# The assignment above answers "which label is closest to this cluster". This
# second pass answers the different, honest question "does the cluster profile
# support that label", using the unscaled Frequency, Monetary, Recency and the
# stored purchase history (tenure). It never moves a buyer: a failed check
# produces a caution with the contradicting numbers, which the page reports, so
# a misleading label is never presented silently as a finding.
def grade_mapping(mapping, profiles, baselines):
    """Attach `supported` + `cautions` to each mapped entry; list ambiguities.

    Each label is checked against concrete, unscaled numbers so the same
    persisted profiles always yield the same verdict:
      * High Spending    - must be the top-average-Monetary cluster and above
        the population mean spend.
      * Frequent Buyers  - must be the top-average-Frequency cluster and show a
        real repeat habit (average orders at or above the gate).
      * At Risk          - must be the least recent (most dormant) cluster and
        actually dormant relative to the population mean Recency.
      * Moderate Spending- the middle residual: flagged only when it is in fact
        the extreme on spend, frequency or dormancy (i.e. another label fits).

    Returns (mapping_with_grades, [ambiguity_messages]).
    """
    by_cluster = {p['cluster_id']: p for p in profiles}
    sized = [p for p in profiles if p['customer_count']]
    max_monetary_idx = _argmax_cluster(sized, 'avg_monetary')
    max_frequency_idx = _argmax_cluster(sized, 'avg_frequency')
    max_recency_idx = _argmax_cluster(sized, 'avg_recency')

    graded = {}
    for cluster_idx, info in mapping.items():
        profile = by_cluster.get(cluster_idx, {})
        cautions = _category_cautions(
            info['category'], profile, baselines,
            this_idx=cluster_idx,
            max_monetary_idx=max_monetary_idx,
            max_frequency_idx=max_frequency_idx,
            max_recency_idx=max_recency_idx,
        )
        graded[cluster_idx] = dict(info,
                                   supported=not cautions,
                                   cautions=cautions)

    ambiguities = [
        f"{info['category']} (cluster {cluster_idx}): {caution}"
        for cluster_idx, info in sorted(graded.items())
        for caution in info['cautions']
    ]
    return graded, ambiguities


def _argmax_cluster(sized, key):
    """The cluster id with the largest value of `key` (None when no data)."""
    values = [(p[key], p['cluster_id']) for p in sized if p.get(key) is not None]
    if not values:
        return None
    return max(values)[1]


def _category_cautions(category, profile, baselines, this_idx,
                       max_monetary_idx, max_frequency_idx, max_recency_idx):
    """Concrete, number-backed reasons why a label may not fit its cluster."""
    cautions = []
    avg_recency = profile.get('avg_recency')
    avg_frequency = profile.get('avg_frequency')
    median_frequency = profile.get('median_frequency')
    avg_monetary = profile.get('avg_monetary')

    if avg_frequency is None:
        return [f'{category} has no measured profile to check.']

    if category == utils.KMEANS_CATEGORY_HIGH_SPENDING:
        if this_idx != max_monetary_idx:
            cautions.append(
                f'another cluster carries more average Monetary value than this '
                f'one (this cluster averages {avg_monetary}), so "High Spending" '
                f'is a relative label only.')
        if avg_monetary is not None and avg_monetary < baselines['mean_monetary']:
            cautions.append(
                f'these buyers average {avg_monetary} in Monetary, below the '
                f'population mean {baselines["mean_monetary"]}, which does not '
                f'read as high spending.')

    elif category == utils.KMEANS_CATEGORY_FREQUENT_BUYERS:
        if this_idx != max_frequency_idx:
            cautions.append(
                f'another cluster purchases more often than this one (this '
                f'cluster averages {avg_frequency} orders), so "Frequent Buyers" '
                f'is a relative label only.')
        if avg_frequency < REPEAT_HABIT_FREQUENCY:
            cautions.append(
                f'these buyers average only {avg_frequency} orders (median '
                f'{median_frequency}), so there is no repeat-purchase habit to '
                f'call them frequent buyers.')

    elif category == utils.KMEANS_CATEGORY_AT_RISK:
        if this_idx != max_recency_idx:
            cautions.append(
                f'this cluster is not the least recent one (mean Recency '
                f'{avg_recency} days, population mean {baselines["mean_recency"]} '
                f'days), so "At Risk" is a relative label only.')
        elif avg_recency is not None and avg_recency <= baselines['mean_recency']:
            cautions.append(
                f'these buyers are not dormant yet (mean Recency {avg_recency} '
                f'days vs population mean {baselines["mean_recency"]} days).')

    elif category == utils.KMEANS_CATEGORY_MODERATE_SPENDING:
        if this_idx == max_monetary_idx:
            cautions.append(
                f'this cluster actually carries the highest average Monetary '
                f'({avg_monetary}), so it is better described as High Spending.')
        if this_idx == max_frequency_idx:
            cautions.append(
                f'this cluster actually purchases the most often (mean '
                f'{avg_frequency} orders), so it is better described as Frequent '
                f'Buyers.')
        if this_idx == max_recency_idx:
            cautions.append(
                f'this is the least recent cluster (mean Recency {avg_recency} '
                f'days), so it is better described as At Risk.')
    return cautions


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------
def _chunks(seq, size):
    for start in range(0, len(seq), size):
        yield seq[start:start + size]


def _persist_labels(customer_ids, labels, mapping):
    """Write each buyer's cluster id + category onto their existing row.

    PostgreSQL (production) does it set-based: the (customer_id, cluster,
    category) pairs go into a transaction-local temp table and one joined UPDATE
    relabels the whole population, using the primary key. Buyers the clustering
    did not cover are explicitly cleared, so the stored table always equals the
    latest run - the distribution counts and the customer lists can never drift
    apart, and a rerun never duplicates a row or leaves a stale label behind.
    Other backends (the SQLite used by unit tests) get the same result through
    chunked ORM updates. Either way only the two clustering columns move: the
    original Recency / Frequency / Monetary and the rule-based `segment` are not
    touched, so no CLV or campaign input changes.
    """
    from django.db import connection, transaction

    labels = np.asarray(labels)
    pairs = []
    for cluster_idx, info in mapping.items():
        category = info['category']
        for i in np.flatnonzero(labels == cluster_idx):
            pairs.append((customer_ids[int(i)], cluster_idx, category))

    with transaction.atomic():
        if connection.vendor == 'postgresql':
            _persist_postgres(connection, pairs)
        else:
            _persist_orm(pairs)


def _persist_postgres(connection, pairs):
    """Temp table + one joined UPDATE, then clear anyone the run did not cover.

    The label pairs are inserted in multi-row statements (the same batching the
    RFM result store uses), so the ~100k assignments cost a handful of remote
    round trips instead of one query per buyer.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            'CREATE TEMP TABLE _kmeans_labels ('
            ' customer_id varchar(255) NOT NULL PRIMARY KEY,'
            ' cluster_id integer NOT NULL,'
            ' category varchar(40) NOT NULL) ON COMMIT DROP')

        row_ph = '(%s,%s,%s)'
        for start in range(0, len(pairs), LABEL_INSERT_BATCH):
            batch = pairs[start:start + LABEL_INSERT_BATCH]
            values = ','.join([row_ph] * len(batch))
            params = [value for row in batch for value in row]
            cursor.execute(
                f'INSERT INTO _kmeans_labels (customer_id, cluster_id, category) '
                f'VALUES {values}', params)

        cursor.execute(
            'UPDATE rfm_customer_segments s '
            'SET kmeans_cluster_id = t.cluster_id, kmeans_category = t.category '
            'FROM _kmeans_labels t WHERE s.customer_id = t.customer_id')
        cursor.execute(
            'UPDATE rfm_customer_segments s '
            'SET kmeans_cluster_id = NULL, kmeans_category = \'\' '
            'WHERE (s.kmeans_cluster_id IS NOT NULL OR s.kmeans_category <> \'\') '
            'AND NOT EXISTS (SELECT 1 FROM _kmeans_labels t '
            'WHERE t.customer_id = s.customer_id)')


def _persist_orm(pairs):
    """Backend-agnostic write path: chunked update per (cluster, category)."""
    by_cluster = {}
    for customer_id, cluster_idx, category in pairs:
        by_cluster.setdefault((cluster_idx, category), []).append(customer_id)
    for (cluster_idx, category), ids in by_cluster.items():
        for chunk in _chunks(ids, UPDATE_BATCH_SIZE):
            CustomerSegment.objects.filter(customer_id__in=chunk).update(
                kmeans_cluster_id=cluster_idx, kmeans_category=category)

    clustered = {cid for cid, _c, _cat in pairs}
    labelled = (CustomerSegment.objects
                .exclude(kmeans_cluster_id__isnull=True)
                .values_list('customer_id', flat=True))
    stale = [cid for cid in labelled if cid not in clustered]
    for chunk in _chunks(stale, UPDATE_BATCH_SIZE):
        CustomerSegment.objects.filter(customer_id__in=chunk).update(
            kmeans_cluster_id=None, kmeans_category='')


def _store_run_state(result, started_at):
    """Persist (and memoize) the single row describing this clustering run.

    Also appends a `ClusteringRun` history row for the same run. The singleton
    is always overwritten by the next clustering, so a campaign that referenced
    it would silently change audience meaning as soon as K-Means is re-run;
    campaigns reference the immutable history row instead.
    """
    from . import cache_manager, segment_store

    clusters = result['clusters']
    run = ClusteringRun.objects.create(
        algorithm=result['algorithm'],
        rfm_version=result['rfm_version'],
        n_clusters=result['effective_clusters'],
        clustered=result['clustered'],
        mapping=clusters,
        started_at=started_at,
        completed_at=utils.utcnow(),
    )
    state = KmeansRunState.objects.update_or_create(
        id=KmeansRunState.SINGLETON_ID,
        defaults={
            'algorithm': result['algorithm'],
            'rfm_version': result['rfm_version'],
            'n_clusters': result['effective_clusters'],
            'clustered': result['clustered'],
            'mapping': clusters,
            'unsupported_categories': result['unsupported_categories'],
            'scaler': result.get('scaler') or {},
            'run': run,
            'started_at': started_at,
            'completed_at': run.completed_at,
        })[0]
    cache_manager.set_kmeans_state_memo(_state_payload(state))
    cache_manager.bump_kmeans_epoch()
    # The dashboard bundle carries the cluster counts, so a completed clustering
    # also refreshes it: the next RFM page open reads the aggregate this run just
    # produced from cache instead of running it again for the first visitor.
    from . import dashboard_cache
    dashboard_cache.warm(state.rfm_version, run_id=run.run_id)
    return state


def _state_payload(state):
    return {
        'algorithm': state.algorithm,
        # The history row of the run this state describes (None for a run that
        # predates campaign cluster targeting; the singleton itself still holds
        # every value needed to explain the labels).
        'run_id': state.run_id,
        'rfm_version': state.rfm_version,
        'n_clusters': state.n_clusters,
        'clustered': state.clustered,
        'mapping': state.mapping or [],
        'unsupported_categories': state.unsupported_categories or [],
        'scaler': state.scaler or {},
        'started_at': state.started_at.isoformat() if state.started_at else None,
        'completed_at': (state.completed_at.isoformat()
                         if state.completed_at else None),
    }


def get_run_state():
    """Latest clustering run description, memoized (no DB on a warm read)."""
    from . import cache_manager
    memo = cache_manager.get_kmeans_state_memo()
    if isinstance(memo, dict) and 'rfm_version' in memo:
        return memo
    state = (KmeansRunState.objects
             .filter(pk=KmeansRunState.SINGLETON_ID).first())
    if state is None:
        return None
    payload = _state_payload(state)
    cache_manager.set_kmeans_state_memo(payload)
    return payload


def latest_run():
    """The newest completed `ClusteringRun` history row, or None.

    This is the run a *new* campaign must be aimed at: it carries the cluster
    ids and the business labels exactly as the persisted buyer assignments were
    written, and it never changes once written. Campaigns store a reference to
    this row, so a later clustering run creates a new row instead of moving the
    ground under a published campaign.
    """
    return ClusteringRun.objects.order_by('-run_id').first()


def ensure_run_history():
    """The newest history row, derived from the stored state when none exists.

    A clustering run persisted before campaign cluster targeting only wrote the
    singleton row. That singleton describes the run completely - the same stored
    mapping, the same RFM version and timestamps - so one history row is
    derived from it, which lets a campaign created now still name the run its
    audience came from. Nothing is re-clustered, no buyer moves, and the call is
    idempotent.
    """
    from . import cache_manager

    run = latest_run()
    if run is not None:
        return run
    state = KmeansRunState.objects.filter(pk=KmeansRunState.SINGLETON_ID).first()
    if state is None:
        return None
    run = ClusteringRun.objects.create(
        algorithm=state.algorithm,
        rfm_version=state.rfm_version,
        n_clusters=state.n_clusters,
        clustered=state.clustered,
        mapping=state.mapping or [],
        started_at=state.started_at,
        completed_at=state.completed_at,
    )
    if state.run_id is None:
        state.run = run
        state.save(update_fields=['run'])
        cache_manager.set_kmeans_state_memo(_state_payload(state))
    return run


def run_view(run):
    """Serializable description of one clustering run (for campaign displays)."""
    if run is None:
        return None
    return {
        'run_id': run.run_id,
        'algorithm': run.algorithm,
        'rfm_version': run.rfm_version,
        'n_clusters': run.n_clusters,
        'clustered': run.clustered,
        'started_at': run.started_at.isoformat() if run.started_at else None,
        'completed_at': (run.completed_at.isoformat()
                         if run.completed_at else None),
    }


# ---------------------------------------------------------------------------
# The run
# ---------------------------------------------------------------------------
def run_clustering(save=True):
    """Cluster every persisted buyer and (optionally) store the result.

    Returns a summary dict: the four (or fewer) clusters with their id, mapped
    category, customer count, unscaled RFM profile, mapping confidence and the
    profile check for that label, plus the count of clustered buyers, any
    categories the data could not support and the ambiguity report.
    """
    from . import segment_store

    started_at = utils.utcnow()
    started = time.perf_counter()
    customer_ids, features, tenure = load_dataset()
    n = features.shape[0]
    requested = utils.KMEANS_N_CLUSTERS
    rfm_version = (segment_store.get_cached_state() or {}).get('version') or 0

    if n == 0:
        return {'available': False, 'clustered': 0, 'clusters': [],
                'requested_clusters': requested, 'effective_clusters': 0,
                'rfm_version': rfm_version, 'total': 0,
                'unsupported_categories': list(utils.KMEANS_CATEGORIES),
                'ambiguities': [], 'message': 'No persisted RFM results to cluster yet.'}

    # K-Means cannot ask for more clusters than data points; a real buyer
    # population (~100k) always supports the full four.
    k = min(requested, n)

    scaler = StandardScaler()
    scaled = scaler.fit_transform(features)  # z = (x - mean) / std, per feature

    model = KMeans(
        n_clusters=k,
        init='k-means++',
        n_init=utils.KMEANS_N_INIT,
        random_state=utils.KMEANS_RANDOM_STATE,
    )
    labels = model.fit_predict(scaled)

    # Cluster profiles from the ORIGINAL (unscaled) RFM values, exactly as the
    # task requires for the business interpretation.
    cluster_means = np.zeros((k, 3), dtype='float64')
    cluster_sizes = np.zeros(k, dtype='int64')
    for idx in range(k):
        mask = labels == idx
        cluster_sizes[idx] = int(mask.sum())
        if cluster_sizes[idx]:
            cluster_means[idx] = features[mask].mean(axis=0)

    mapping, unsupported = map_clusters_to_categories(cluster_means, cluster_sizes)
    profiles = _cluster_profiles(features, tenure, labels, k,
                                 cluster_means, cluster_sizes)
    baselines = _population_baselines(features, tenure)
    graded, ambiguities = grade_mapping(mapping, profiles, baselines)

    if save and graded:
        _persist_labels(customer_ids, labels, graded)
        _store_run_state({'algorithm': 'KMeans(k-means++)',
                          'rfm_version': rfm_version,
                          'effective_clusters': k,
                          'clustered': int(n),
                          'clusters': [dict(p, **graded[p['cluster_id']])
                                       for p in profiles if p['cluster_id'] in graded],
                          'unsupported_categories': unsupported,
                          'scaler': _scaler_stats(scaler)}, started_at)

    clusters = [
        describe_cluster(p, graded.get(p['cluster_id']), n)
        for p in profiles if p['cluster_id'] in graded
    ]
    clusters.sort(key=lambda c: c['cluster_id'])

    return {
        'available': True,
        'algorithm': 'KMeans(k-means++)',
        'features_scaled': ['recency', 'frequency', 'monetary'],
        'clustered': int(n),
        'total': int(n),
        'requested_clusters': requested,
        'effective_clusters': k,
        'rfm_version': rfm_version,
        'population': baselines,
        'scaler': _scaler_stats(scaler),
        'clusters': clusters,
        'unsupported_categories': unsupported,
        'ambiguities': ambiguities,
        'compute_ms': round((time.perf_counter() - started) * 1000, 2),
    }


def _scaler_stats(scaler):
    return {
        'mean': [round(float(v), 4) for v in scaler.mean_],
        'scale': [round(float(v), 4) for v in scaler.scale_],
    }


def describe_cluster(profile, assignment, total):
    """One cluster row of the API payload (profile + label + share of total)."""
    count = profile['customer_count']
    row = dict(profile)
    row.update({
        'category': assignment['category'],
        'confidence': assignment['confidence'],
        'supported': assignment['supported'],
        'cautions': assignment['cautions'],
        'percent': round(count / total * 100, 1) if total else 0,
    })
    return row


# ---------------------------------------------------------------------------
# Reading the stored result back (never a recompute)
# ---------------------------------------------------------------------------
# Distinguishes "load the stored run state" from "there is no run state": an
# explicit None means the caller already knows no clustering has completed, so
# no cache or database read is needed for it.
_UNLOADED = object()


def summarize_clusters(clusters, state=_UNLOADED, total=None):
    """Build the response shape from a list of aggregated cluster rows.

    Each row needs `category` and `customer_count`; the four categories the data
    could not support are reported rather than forced onto a wrong cluster. Used
    by both this module's own query and the dashboard bundle (which aggregates
    in the shared single query), so the two never drift.

    `state` is the stored run state (its per-cluster confidence / profile check
    is merged by cluster id, so the cached aggregate query stays a simple
    GROUP BY); `total` is the denominator for the percentages - the clustered
    population, so the four shares add up to 100%.
    """
    state = get_run_state() if state is _UNLOADED else state
    by_cluster = {}
    if state:
        by_cluster = {row.get('cluster_id'): row for row in (state.get('mapping') or [])}

    enriched = []
    for row in clusters:
        extra = by_cluster.get(row.get('cluster_id')) or {}
        enriched.append({
            **row,
            'confidence': extra.get('confidence'),
            'supported': extra.get('supported', True),
            'cautions': extra.get('cautions') or [],
            'avg_recency': row.get('avg_recency') if row.get('avg_recency') is not None
            else extra.get('avg_recency'),
            'avg_frequency': row.get('avg_frequency') if row.get('avg_frequency') is not None
            else extra.get('avg_frequency'),
            'avg_monetary': row.get('avg_monetary') if row.get('avg_monetary') is not None
            else extra.get('avg_monetary'),
        })

    # Category order is the documented display order, biggest cluster first
    # inside a category is impossible (one cluster per category), so sort by
    # that fixed label order to keep the page stable across runs.
    order = {c: i for i, c in enumerate(utils.KMEANS_CATEGORIES)}
    enriched.sort(key=lambda c: (order.get(c['category'], len(order)),
                                 -(c['customer_count'] or 0)))

    denominator = total if total else sum(c['customer_count'] or 0 for c in enriched)
    for c in enriched:
        c['percent'] = (round((c['customer_count'] or 0) / denominator * 100, 1)
                        if denominator else 0)

    assigned = {c['category'] for c in enriched}
    unsupported = [c for c in utils.KMEANS_CATEGORIES if c not in assigned]
    if state:
        unsupported = list(dict.fromkeys(
            unsupported + list(state.get('unsupported_categories') or [])))
    ambiguities = [
        f"{c['category']} (cluster {c['cluster_id']}): {caution}"
        for c in enriched for caution in c['cautions']
    ]
    return {
        'available': bool(enriched),
        'clustered': sum(c['customer_count'] or 0 for c in enriched),
        'total': denominator,
        'clusters': enriched,
        'unsupported_categories': unsupported,
        'ambiguities': ambiguities,
        'state': _state_view(state, denominator),
    }


def _state_view(state, denominator):
    """Run bookkeeping + the staleness the page has to report honestly."""
    if not state:
        return None
    from . import segment_store
    current_version = (segment_store.get_cached_state() or {}).get('version')
    return {
        'algorithm': state.get('algorithm'),
        # Which stored clustering run these labels came from, so a page can name
        # it (and a campaign page can prove it aimed at the latest one).
        'run_id': state.get('run_id'),
        'rfm_version': state.get('rfm_version'),
        'current_rfm_version': current_version,
        'clustered': state.get('clustered'),
        'n_clusters': state.get('n_clusters'),
        'started_at': state.get('started_at'),
        'completed_at': state.get('completed_at'),
        'scaler': state.get('scaler') or {},
        # A newer RFM analysis (new buyers or moved metrics) means the stored
        # labels were computed on an older population.
        'stale': bool(current_version and state.get('rfm_version')
                      and current_version != state.get('rfm_version')),
        'total': denominator,
    }


def clustering_summary():
    """Current stored clustering, aggregated live from the persisted rows.

    Reads nothing but `rfm_customer_segments`, so it reflects the latest
    completed clustering even after a restart. The dashboard summary path does
    not call this - it folds the same aggregation into one cached bundle query -
    this is the standalone read for the `/clusters` endpoint.
    """
    from django.db.models import Avg, Count

    rows = (
        CustomerSegment.objects
        .exclude(kmeans_cluster_id__isnull=True)
        .values('kmeans_cluster_id', 'kmeans_category')
        .annotate(
            customer_count=Count('customer_id'),
            avg_recency=Avg('recency'),
            avg_frequency=Avg('frequency'),
            avg_monetary=Avg('monetary'),
        )
        .order_by('kmeans_cluster_id')
    )
    clusters = []
    for row in rows:
        clusters.append({
            'cluster_id': row['kmeans_cluster_id'],
            'category': row['kmeans_category'],
            'customer_count': row['customer_count'],
            'avg_recency': (round(float(row['avg_recency']), 2)
                            if row['avg_recency'] is not None else None),
            'avg_frequency': (round(float(row['avg_frequency']), 2)
                              if row['avg_frequency'] is not None else None),
            'avg_monetary': (round(float(row['avg_monetary']), 2)
                             if row['avg_monetary'] is not None else None),
        })
    return summarize_clusters(clusters)


# ---------------------------------------------------------------------------
# Re-interpreting a persisted run's business labels (never a K-Means rerun)
# ---------------------------------------------------------------------------
# A completed run writes two things: the per-buyer `kmeans_category` string and
# the run-state `mapping`. If the label vocabulary later changes, those persisted
# strings are the OLD names even though the buyer -> cluster assignment and every
# cluster's unscaled RFM profile are still exactly right. The business label is
# derived *purely from the stored cluster profiles*, so it can be recomputed from
# them without reloading the ~100k-row population or re-fitting K-Means: the
# numeric `kmeans_cluster_id` (and therefore every buyer's group) never moves,
# only the label mapped onto each cluster is refreshed.
#
# The cluster means used here are the run's own persisted averages, so the same
# profiles plus the same interpretation criteria always produce the same labels.
def _recompute_mapping(profiles):
    """Re-derive category / confidence / profile-check from stored profiles.

    `profiles` are the run-state mapping rows (each carrying the cluster's
    ORIGINAL, unscaled avg Recency / Frequency / Monetary and customer count).
    Returns (graded_by_cluster_id, unsupported_categories, ambiguities).
    """
    sized = [p for p in profiles if p.get('customer_count')]
    if not sized:
        return {}, list(utils.KMEANS_CATEGORIES), []

    ids = [int(p['cluster_id']) for p in sized]
    means = np.array(
        [[float(p.get('avg_recency') or 0), float(p.get('avg_frequency') or 0),
          float(p.get('avg_monetary') or 0)] for p in sized], dtype='float64')
    sizes = np.array([int(p['customer_count']) for p in sized], dtype='int64')

    pos_map, unsupported = map_clusters_to_categories(means, sizes)
    mapping = {ids[pos]: info for pos, info in pos_map.items()}
    baselines = _weighted_baselines(sized)
    graded, ambiguities = grade_mapping(mapping, sized, baselines)
    return graded, unsupported, ambiguities


def _weighted_baselines(profiles):
    """Population reference points rebuilt from the per-cluster profiles.

    Weighted by each cluster's customer count, so the label checks compare a
    cluster against the same buyer population the run actually covered - from
    the persisted profiles alone, with no rescan of the order table.
    """
    total = sum(p['customer_count'] for p in profiles) or 1

    def wmean(key):
        num = sum((p.get(key) or 0) * p['customer_count'] for p in profiles)
        return round(num / total, 2)

    return {
        'buyers': total,
        'mean_recency': wmean('avg_recency'),
        'mean_frequency': wmean('avg_frequency'),
        'mean_monetary': wmean('avg_monetary'),
    }


def labels_are_current(state):
    """True when every persisted label is already one of the current four."""
    if not state:
        return False
    rows = state.get('mapping') or []
    if not rows:
        return False
    valid = set(utils.KMEANS_CATEGORIES)
    return all(row.get('category') in valid for row in rows)


def relabel_stored_run():
    """Refresh the persisted business labels from the run's stored profiles.

    Never re-fits K-Means and never changes a buyer's `kmeans_cluster_id`: only
    the `kmeans_category` string mapped onto each cluster is rewritten (a set of
    small UPDATEs by cluster id), together with the run-state mapping. The
    clustering epoch is then bumped so the cached dashboard bundle is rebuilt
    from the corrected labels. Returns a summary dict, or None when there is no
    completed run to relabel or it has no profiled clusters.
    """
    from django.db import transaction

    from . import cache_manager

    state = KmeansRunState.objects.filter(pk=KmeansRunState.SINGLETON_ID).first()
    if state is None:
        return None

    profiles = list(state.mapping or [])
    graded, unsupported, ambiguities = _recompute_mapping(profiles)
    if not graded:
        return None

    by_cluster = {int(p['cluster_id']): p for p in profiles}
    new_rows = [dict(by_cluster[cid], **info)
                for cid, info in sorted(graded.items())]

    with transaction.atomic():
        for cid, info in graded.items():
            CustomerSegment.objects.filter(kmeans_cluster_id=cid).update(
                kmeans_category=info['category'])
        state.mapping = new_rows
        state.unsupported_categories = unsupported
        state.save()
        # Keep the history row of this same run in step with the singleton, so
        # campaign authoring offers the refreshed labels for the run a new
        # campaign will be aimed at. Older history rows are never rewritten:
        # they document what each existing campaign was actually published on.
        run = state.run or ClusteringRun.objects.order_by('-run_id').first()
        if run is not None:
            run.mapping = new_rows
            run.save(update_fields=['mapping'])

    cache_manager.set_kmeans_state_memo(_state_payload(state))
    cache_manager.bump_kmeans_epoch()
    # The stored bundle was aggregated with the old label strings, and the
    # clustering run id has not changed, so it must be dropped: the next read
    # re-aggregates the same numbers under the corrected labels.
    from . import dashboard_cache
    dashboard_cache.invalidate(state.rfm_version)

    return {
        'relabelled': True,
        'clusters': new_rows,
        'unsupported_categories': unsupported,
        'ambiguities': ambiguities,
    }


def reconcile_stored_labels():
    """Self-heal a persisted run whose stored labels predate the current set.

    Called from the dashboard read paths. Cheap and idempotent: it inspects the
    memoized run state (the same read the page needs anyway, so no extra query)
    and only rewrites labels when they are not already the current four
    categories (i.e. a legacy run). It never re-runs K-Means and never touches a
    buyer's cluster assignment. Returns True when it changed something.
    """
    state = get_run_state()
    if state is None or labels_are_current(state):
        return False
    return bool(relabel_stored_run())
