"""K-Means cluster targeting for personalized coupon campaigns.

Replaces the old rule-based segment targeting for every campaign the admin
creates from here on. The four customer groups offered to the admin are the
clusters of the *persisted* K-Means++ run - never a manual RFM threshold, and
never an id assumed to mean a fixed behaviour: each cluster's business label is
read from the mapping stored with the run it came from (see
`clustering.map_clusters_to_categories`), so a re-cluster that reshuffles labels
is reflected instead of being contradicted.

Three responsibilities, and nothing else:

1. Describe the selectable groups (`available_clusters`) with the number of
   buyers actually assigned to each, from the persisted
   `rfm_customer_segments.kmeans_cluster_id` - the same rows the RFM dashboard
   aggregates, so a bar's count and a campaign's audience can never disagree.
2. Freeze a published campaign's audience: `materialize_audience` writes one
   `CampaignAudience` row per targeted buyer (the coupon issued to them), using
   the cluster assignment of the run the campaign references. A future
   clustering run may move those buyers to another cluster; the campaign, its
   coupons and its redemption history do not follow, which is exactly what the
   requirement "published audiences must not silently change" asks for.
   The write is duplicate-proof by the unique constraint, so re-publishing or
   widening a campaign never hands the same customer two coupons.
3. Answer the eligibility question the old segment rule used to answer:
   `is_member(campaign, customer_id)` (one indexed lookup) and
   `member_campaign_ids(customer_id, campaign_ids)` (one query for a whole
   offer list).

Legacy rule-segment campaigns never reach any function here: they are still
evaluated from the customer's current segment, so nothing published before this
change is reinterpreted.
"""

from django.db import connection, transaction
from django.db.models import Count
from django.utils import timezone

from . import clustering
from .models import CampaignAudience, CustomerSegment

# Buyers per cluster are ~25k, so the assignment read is batched; the value is
# only one indexed column.
CUSTOMER_BATCH_SIZE = 5000


def selected_run():
    """The clustering run a new or rewritten audience is chosen from.

    Always the latest successfully completed run, referenced by its immutable
    history row so the campaign keeps naming that run for life.
    """
    return clustering.ensure_run_history()


def available_cluster_ids(state=None):
    """The cluster ids of the latest persisted clustering run (may be empty)."""
    state = clustering.get_run_state() if state is None else state
    if not state:
        return set()
    return {int(row['cluster_id']) for row in (state.get('mapping') or [])
            if row.get('cluster_id') is not None and row.get('customer_count')}


def normalize_cluster_ids(values):
    """Cluster ids as a sorted, de-duplicated list of ints ('' on bad input).

    Raises ValueError with an admin-readable message for anything that is not a
    cluster id, so the serializer can surface it as a field error.
    """
    ids = []
    for value in values or []:
        try:
            cluster_id = int(value)
        except (TypeError, ValueError):
            raise ValueError(f'Unknown cluster: {value!r}')
        if cluster_id < 0:
            raise ValueError(f'Unknown cluster: {value!r}')
        if cluster_id not in ids:
            ids.append(cluster_id)
    return sorted(ids)


def validate_cluster_ids(values, state=None):
    """Normalized cluster ids, each one belonging to the selected clustering run."""
    cluster_ids = normalize_cluster_ids(values)
    if not cluster_ids:
        raise ValueError('Choose at least one customer group - '
                         'campaigns never go to all customers.')
    selectable = available_cluster_ids(state)
    if not selectable:
        raise ValueError('No K-Means clustering has been persisted yet. '
                         'Run the clustering on the RFM analysis page first.')
    unknown = [cid for cid in cluster_ids if cid not in selectable]
    if unknown:
        raise ValueError(
            f'Cluster(s) {unknown} are not part of the stored clustering run.')
    return cluster_ids


def labels_for(cluster_ids, run=None):
    """Business labels of these cluster ids, in the given (or latest) run.

    Read from the run's stored mapping, never from a fixed id -> label table.
    Falls back to the label persisted on the buyers' rows for a cluster the run
    state does not describe, so nothing is ever invented.
    """
    if run is not None:
        mapping = run.mapping or []
    else:
        mapping = (clustering.get_run_state() or {}).get('mapping') or []
    by_cluster = {int(row['cluster_id']): (row.get('category') or '')
                  for row in mapping if row.get('cluster_id') is not None}
    if not by_cluster:
        rows = (CustomerSegment.objects
                .exclude(kmeans_cluster_id__isnull=True)
                .values('kmeans_cluster_id', 'kmeans_category'))
        by_cluster = {row['kmeans_cluster_id']: row['kmeans_category'] or ''
                      for row in rows}
    return [by_cluster.get(cid, '') for cid in cluster_ids]


def _live_counts():
    """{cluster_id: (label, customer_count)} from the persisted assignments."""
    rows = (CustomerSegment.objects
            .exclude(kmeans_cluster_id__isnull=True)
            .values('kmeans_cluster_id', 'kmeans_category')
            .annotate(customer_count=Count('customer_id'))
            .order_by('kmeans_cluster_id'))
    counts = {}
    for row in rows:
        counts[row['kmeans_cluster_id']] = (row['kmeans_category'] or '',
                                            row['customer_count'])
    return counts


def _count_by_cluster(sql, params):
    """Run one grouped count and return {cluster_id: count}."""
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        return {int(row[0]): int(row[1]) for row in cursor.fetchall()}


def _campaign_group_stats(run, cluster_ids):
    """Per cluster: coupons assigned, redeemed, and the campaigns covering it.

    Everything is counted for the campaigns of ONE clustering run, which is the
    only context in which a numeric cluster id means something: an assignment or
    a redemption can then be attributed to a group without mixing ids from
    different runs.

    Three bounded queries for the whole panel - the run's campaigns, the
    assignments grouped by cluster, and the redemptions joined to the assignment
    that granted the coupon - plus the campaign rows already in memory. Never a
    query per cluster or per campaign. The redemption join is exact because a
    redemption exists at most once per (campaign, customer), which is also the
    assignment key.
    """
    from django.utils import timezone

    from .models import Campaign, CampaignStatus, TargetingMode

    stats = {cid: {'coupons_assigned': 0, 'coupons_redeemed': 0,
                   'campaigns': [], 'live_campaigns': 0}
             for cid in cluster_ids}
    campaigns = list(
        Campaign.objects
        .filter(targeting_mode=TargetingMode.KMEANS, clustering_run=run)
        .order_by('-campaign_id'))
    if not campaigns:
        return stats

    campaign_ids = [c.campaign_id for c in campaigns]
    placeholders = ','.join(['%s'] * len(campaign_ids))
    cluster_placeholders = ','.join(['%s'] * len(cluster_ids))
    base_params = [*campaign_ids, *cluster_ids]

    # `%s` placeholders are translated by the backend's cursor wrapper, so the
    # same statement runs on PostgreSQL (production) and SQLite (unit tests).
    assigned_sql = (
        f'SELECT cluster_id, COUNT(*) FROM rfm_campaign_audience '
        f'WHERE campaign_id IN ({placeholders}) AND cluster_id IN ({cluster_placeholders}) '
        f'GROUP BY cluster_id')
    for cluster_id, count in _count_by_cluster(assigned_sql, base_params).items():
        if cluster_id in stats:
            stats[cluster_id]['coupons_assigned'] = count

    redeemed_sql = (
        f'SELECT a.cluster_id, COUNT(*) FROM rfm_campaign_audience a '
        f'JOIN rfm_campaign_redemptions r '
        f'ON r.campaign_id = a.campaign_id AND r.customer_id = a.customer_id '
        f'WHERE a.campaign_id IN ({placeholders}) AND a.cluster_id IN ({cluster_placeholders}) '
        f'GROUP BY a.cluster_id')
    for cluster_id, count in _count_by_cluster(redeemed_sql, base_params).items():
        if cluster_id in stats:
            stats[cluster_id]['coupons_redeemed'] = count

    now = timezone.now()
    by_cluster = {cid: [] for cid in cluster_ids}
    for campaign in campaigns:
        for cluster_id in set(normalize_cluster_ids(campaign.target_cluster_ids)):
            if cluster_id in by_cluster:
                by_cluster[cluster_id].append(campaign)

    for cluster_id, covered in by_cluster.items():
        entries = []
        live = 0
        for campaign in covered:
            is_live = (campaign.status == CampaignStatus.PUBLISHED
                       and campaign.start_date <= now <= campaign.end_date)
            if is_live:
                live += 1
            entries.append({
                'campaign_id': campaign.campaign_id,
                'name': campaign.name,
                'coupon_code': campaign.coupon_code,
                'status': campaign.status,
                'is_live': is_live,
                'start_date': campaign.start_date.isoformat(),
                'end_date': campaign.end_date.isoformat(),
            })
        stats[cluster_id]['campaigns'] = entries
        stats[cluster_id]['live_campaigns'] = live
    return stats


def available_clusters(include_campaign_stats=True):
    """The four customer groups an admin may target, with their real counts.

    Returns ``{'available', 'run', 'clusters', 'message'}``: `clusters` is one
    row per cluster of the stored run - its numeric id, the business label that
    run mapped onto it, how many buyers are actually assigned to it and the
    unscaled RFM profile the label was derived from. `run` identifies the
    clustering run those numbers come from, so the page can show (and a new
    campaign can store) exactly which run produced the audience.
    """
    from . import segment_store

    state = clustering.get_run_state()
    run = selected_run()
    if not state and run is None:
        return {'available': False, 'run': None, 'clusters': [],
                'message': 'No K-Means clustering has been persisted yet.'}

    counts = _live_counts()
    mapping = {}
    for row in ((run.mapping if run is not None else state.get('mapping')) or []):
        if row.get('cluster_id') is not None:
            mapping[int(row['cluster_id'])] = row
    # A cluster only exists for the admin if buyers are actually in it.
    cluster_ids = sorted(set(counts) | {
        cid for cid, row in mapping.items() if row.get('customer_count')})

    clusters = []
    group_stats = ({cid: {'coupons_assigned': 0, 'coupons_redeemed': 0,
                          'campaigns': [], 'live_campaigns': 0}
                    for cid in cluster_ids}
                   if not include_campaign_stats else {})
    if include_campaign_stats and run is not None and cluster_ids:
        group_stats = _campaign_group_stats(run, cluster_ids)
    for cluster_id in cluster_ids:
        stored = mapping.get(cluster_id) or {}
        label, count = counts.get(cluster_id, (stored.get('category') or '', 0))
        stats = group_stats.get(cluster_id, {})
        clusters.append({
            'cluster_id': cluster_id,
            'category': label or stored.get('category') or '',
            'customer_count': count,
            'run_customer_count': stored.get('customer_count', count),
            'confidence': stored.get('confidence'),
            'supported': stored.get('supported', True),
            'avg_recency': stored.get('avg_recency'),
            'avg_frequency': stored.get('avg_frequency'),
            'avg_monetary': stored.get('avg_monetary'),
            # What the Campaign page shows for the group as a whole, counted from
            # the issued coupon assignments and the redemption audit of this run.
            'coupons_assigned': stats.get('coupons_assigned', 0),
            'coupons_redeemed': stats.get('coupons_redeemed', 0),
            'live_campaigns': stats.get('live_campaigns', 0),
            'campaigns': stats.get('campaigns', []),
        })
    current_version = (segment_store.get_cached_state() or {}).get('version')
    return {
        'available': bool(clusters),
        'run': clustering.run_view(run or None),
        'run_state': {
            'rfm_version': (state or {}).get('rfm_version'),
            'current_rfm_version': current_version,
            'clustered': (state or {}).get('clustered'),
            'completed_at': (state or {}).get('completed_at'),
            # A newer RFM analysis than the clustered one: the stored groups still
            # cover every previously clustered buyer, but the page should say so.
            'stale': bool(current_version and (state or {}).get('rfm_version')
                           and current_version != (state or {}).get('rfm_version')),
        },
        'clusters': clusters,
        'message': None if clusters else 'No buyer has a stored cluster assignment yet.',
    }


def audience_size(cluster_ids):
    """How many customers the persisted assignment puts in these clusters."""
    cluster_ids = normalize_cluster_ids(cluster_ids)
    if not cluster_ids:
        return 0
    return (CustomerSegment.objects
            .exclude(kmeans_cluster_id__isnull=True)
            .filter(kmeans_cluster_id__in=cluster_ids)
            .count())


def per_cluster_counts(cluster_ids):
    """{cluster_id: customer_count} for these clusters, from live assignments."""
    cluster_ids = normalize_cluster_ids(cluster_ids)
    if not cluster_ids:
        return {}
    rows = (CustomerSegment.objects
            .exclude(kmeans_cluster_id__isnull=True)
            .filter(kmeans_cluster_id__in=cluster_ids)
            .values('kmeans_cluster_id')
            .annotate(customer_count=Count('customer_id')))
    return {row['kmeans_cluster_id']: row['customer_count'] for row in rows}


def _cluster_customers(cluster_id):
    """Customer ids persisted in one cluster, in stable (primary-key) order."""
    ordered = (CustomerSegment.objects
               .exclude(kmeans_cluster_id__isnull=True)
               .filter(kmeans_cluster_id=cluster_id)
               .order_by('customer_id')
               .values_list('customer_id', flat=True))
    return list(ordered)


def _assign_postgres(campaign_id, cluster_id, label, now):
    """Set-based coupon assignment: one INSERT ... SELECT per cluster.

    ~25k buyers per cluster are materialized without ever shipping their ids to
    the application, and `ON CONFLICT DO NOTHING` makes the unique constraint
    the thing that prevents a duplicate coupon rather than a check-then-insert
    race.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            'INSERT INTO rfm_campaign_audience '
            '(campaign_id, customer_id, cluster_id, cluster_label, assigned_at) '
            'SELECT %s, s.customer_id, s.kmeans_cluster_id, %s, %s '
            'FROM rfm_customer_segments s '
            'WHERE s.kmeans_cluster_id = %s '
            'ON CONFLICT DO NOTHING',
            [campaign_id, label, now, cluster_id])
        return cursor.rowcount or 0


def _assign_orm(campaign, cluster_id, label, now):
    """Backend-agnostic assignment path (the SQLite used by unit tests)."""
    customer_ids = _cluster_customers(cluster_id)
    rows = [
        CampaignAudience(campaign=campaign, customer_id=customer_id,
                         cluster_id=cluster_id, cluster_label=label,
                         assigned_at=now)
        for customer_id in customer_ids
    ]
    if not rows:
        return 0
    CampaignAudience.objects.bulk_create(
        rows, batch_size=CUSTOMER_BATCH_SIZE, ignore_conflicts=True)
    return len(rows)


def materialize_audience(campaign):
    """Issue this campaign's coupon to every customer of its selected clusters.

    Uses the customer-to-cluster assignment persisted by the clustering run the
    campaign references (falling back to the latest stored run when an older
    draft row has no reference yet). Idempotent and additive:

    * a buyer already holding a coupon for this campaign is never given a
      second one (unique constraint / ON CONFLICT DO NOTHING);
    * customers of clusters that were not selected are never inserted;
    * rows of previously issued coupons are never deleted, so narrowing a live
      campaign cannot revoke a coupon a customer already holds.

    Returns ``{'targeted', 'newly_assigned', 'coupons_issued', 'clusters'}`` -
    the numbers the admin is shown after publishing.
    """
    cluster_ids = normalize_cluster_ids(campaign.target_cluster_ids)
    labels = labels_for(cluster_ids, campaign.clustering_run)
    label_by_cluster = dict(zip(cluster_ids, labels))
    now = timezone.now()

    issued_before = CampaignAudience.objects.filter(campaign=campaign).count()
    with transaction.atomic():
        for cluster_id in cluster_ids:
            label = label_by_cluster.get(cluster_id) or ''
            if connection.vendor == 'postgresql':
                _assign_postgres(campaign.campaign_id, cluster_id, label, now)
            else:
                _assign_orm(campaign, cluster_id, label, now)
        issued_after = CampaignAudience.objects.filter(
            campaign=campaign).count()
    live = per_cluster_counts(cluster_ids)

    return {
        # The audience the campaign was aimed at, and what the existing coupon
        # infrastructure actually handed out - the two numbers the admin asked
        # to see after publishing.
        'targeted': sum(live.values()),
        'newly_assigned': max(issued_after - issued_before, 0),
        'coupons_issued': issued_after,
        'clusters': [{'cluster_id': cluster_id,
                      'category': label_by_cluster.get(cluster_id) or '',
                      'eligible_customers': live.get(cluster_id, 0)}
                     for cluster_id in cluster_ids],
    }


def cluster_breakdown(campaign):
    """Per selected cluster: label, live eligible count and coupons issued.

    What the campaign page lists as the audience of one campaign: the business
    label of each selected cluster, how many customers the stored assignment
    puts in it, and how many of them this campaign actually issued a coupon to.
    """
    cluster_ids = normalize_cluster_ids(campaign.target_cluster_ids)
    if not cluster_ids:
        return []
    live = per_cluster_counts(cluster_ids)
    labels = dict(zip(cluster_ids, labels_for(cluster_ids, campaign.clustering_run)))
    issued = (CampaignAudience.objects
              .filter(campaign_id=campaign.campaign_id, cluster_id__in=cluster_ids)
              .values('cluster_id')
              .annotate(customer_count=Count('customer_id')))
    issued_by_cluster = {row['cluster_id']: row['customer_count'] for row in issued}
    return [{'cluster_id': cluster_id,
             'category': labels.get(cluster_id) or '',
             'eligible_customers': live.get(cluster_id, 0),
             'coupons_issued': issued_by_cluster.get(cluster_id, 0)}
            for cluster_id in cluster_ids]


def has_audience(campaign):
    """Has this campaign already issued coupons to a materialized audience?"""
    return CampaignAudience.objects.filter(campaign=campaign).exists()


def audience_stats(campaign):
    """The audience numbers a view returns without re-resolving anything."""
    issued = CampaignAudience.objects.filter(campaign=campaign).count()
    return {
        'targeted': audience_size(campaign.target_cluster_ids),
        'newly_assigned': 0,
        'coupons_issued': issued,
        'clusters': cluster_breakdown(campaign),
    }


def is_member(campaign, customer_id):
    """Was a coupon of this campaign issued to this customer?"""
    if not customer_id:
        return False
    return CampaignAudience.objects.filter(
        campaign=campaign, customer_id=customer_id).exists()


def member_campaign_ids(customer_id, campaign_ids):
    """The subset of `campaign_ids` this customer holds a coupon for.

    One indexed query for a whole offer list, so adding a campaign never adds a
    round trip per campaign to a customer request.
    """
    campaign_ids = list(campaign_ids)
    if not customer_id or not campaign_ids:
        return set()
    return set(CampaignAudience.objects
               .filter(customer_id=customer_id,
                       campaign_id__in=campaign_ids)
               .values_list('campaign_id', flat=True))


def coupons_issued(campaign_ids):
    """{campaign_id: coupons issued} for a page of campaigns in one query."""
    campaign_ids = list(campaign_ids)
    if not campaign_ids:
        return {}
    rows = (CampaignAudience.objects
            .filter(campaign_id__in=campaign_ids)
            .values('campaign_id')
            .annotate(count=Count('assignment_id')))
    return {row['campaign_id']: row['count'] for row in rows}
