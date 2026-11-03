"""Live verification of the RFM performance work + cluster-based coupons.

Part A is read-only timing against the real Neon data. Part B runs the actual
production publish/visibility code inside a database transaction that is ALWAYS
rolled back, so no campaign, coupon assignment or term survives it: uncommitted
rows are invisible to every other session, so a real customer can never see what
this creates.

Run:  python live_verify.py
"""
import os
import time
from datetime import timedelta

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.conf import settings  # noqa: E402
from django.utils import timezone  # noqa: E402
from django.db import transaction  # noqa: E402
from rest_framework.exceptions import ValidationError  # noqa: E402

from rfm_analysis import (cache_manager, clustering, coupon_validation,  # noqa: E402
                          dashboard_cache, personalization, queries,
                          segment_store, views)
from rfm_analysis.cluster_targeting import available_clusters  # noqa: E402
from rfm_analysis.models import (Campaign, CampaignAudience,  # noqa: E402
                                 CampaignStatus, ClusteringRun,
                                 CustomerSegment, DashboardSnapshot)


class _Rollback(Exception):
    """Signals the deliberate rollback of the verification transaction."""


def ms(fn):
    started = time.perf_counter()
    result = fn()
    return round((time.perf_counter() - started) * 1000, 2), result


def line(label, value):
    print(f'{label:50s} {value}', flush=True)


def timed_summary(version, run_id):
    """The summary view's read path, minus HTTP and authentication."""
    bundle, source = dashboard_cache.load(version, run_id)
    query_ms = 0
    if bundle is None:
        started = time.perf_counter()
        bundle, _timing = dashboard_cache.build(version=version, run_id=run_id)
        query_ms = round((time.perf_counter() - started) * 1000, 2)
        source = 'query'
    totals = bundle['totals']
    buyer_count = totals['buyer_count'] or 0
    kmeans = clustering.summarize_clusters(bundle['kmeans_clusters'], total=buyer_count)
    return {'timing': {'bundle_source': source, 'query_ms': query_ms},
            'kmeans': views._kmeans_compact(kmeans), 'totals': totals}


def part_a():
    print('\n=== A. READ-ONLY TIMINGS (live Neon database) ===', flush=True)
    backend = settings.CACHES['default']['BACKEND'].rsplit('.', 2)[-2]
    print(f'cache backend: {backend}', flush=True)

    cache_manager.cache.clear()               # a genuinely cold process
    dashboard_cache.invalidate()

    population = CustomerSegment.objects.count()
    clustered = (CustomerSegment.objects
                 .exclude(kmeans_cluster_id__isnull=True).count())
    line('rows in rfm_customer_segments', population)
    line('buyers with a persisted cluster assignment', clustered)

    t_state, state = ms(lambda: segment_store.get_state())
    line(f'analysis state read (v{state.version if state else "-"})', f'{t_state} ms')
    if state is None:
        line('ABORT', 'no completed RFM analysis is stored')
        return None, None
    version = state.version
    t_memo, _ = ms(lambda: segment_store.get_cached_state())
    line('  same state from the memoized read', f'{t_memo} ms')

    t_rec, _ = ms(lambda: clustering.reconcile_stored_labels())
    line('reconcile_stored_labels() (cold: may read the state)', f'{t_rec} ms')
    t_rec2, _ = ms(lambda: clustering.reconcile_stored_labels())
    line('  second call (memoized, no query)', f'{t_rec2} ms')

    t_run, run_state = ms(lambda: clustering.get_run_state())
    line(f'clustering run read (run_id={run_state.get("run_id") if run_state else None})',
         f'{t_run} ms')
    t_hist, history = ms(lambda: clustering.ensure_run_history())
    line('ClusteringRun history rows after the derived read',
         f'{ClusteringRun.objects.count()} (took {t_hist} ms)')
    if history is not None:
        line('  that run: label -> cluster id',
             {row.get('category'): row.get('cluster_id') for row in (history.mapping or [])})

    t_bundle, bundle = ms(lambda: queries.fetch_dashboard_bundle())
    line('COLD dashboard aggregate (GROUPING SETS pass)', f'{t_bundle} ms')
    t_total, total_customers = ms(lambda: queries.fetch_total_customers())
    line(f'customers count ({total_customers:,})', f'{t_total} ms')
    bundle['total_customers'] = total_customers

    t_store, _ = ms(lambda: dashboard_cache.store(version, bundle,
                                                  run_id=(run_state or {}).get('run_id')))
    line('store the durable snapshot row', f'{t_store} ms')

    cache_manager.cache.clear()               # process restart, database kept
    t_load, loaded = ms(lambda: dashboard_cache.load(version,
                                                     (run_state or {}).get('run_id')))
    line('RESTARTED process read: durable snapshot row',
         f'{t_load} ms -> {"HIT" if loaded else "MISS"}')
    t_load2, _ = ms(lambda: dashboard_cache.load(version, (run_state or {}).get('run_id')))
    line('WARM read: in-process cache', f'{t_load2} ms')
    line('snapshot rows in rfm_dashboard_snapshot', DashboardSnapshot.objects.count())

    t_panel, panel = ms(lambda: available_clusters())
    line('campaign group panel payload (all four groups)', f'{t_panel} ms')
    for group in sorted(panel['clusters'], key=lambda g: g['cluster_id']):
        line(f"  #{group['cluster_id']} {group['category']}",
             f"eligible={group['customer_count']:,} "
             f"assigned={group['coupons_assigned']:,} "
             f"redeemed={group['coupons_redeemed']:,} "
             f"live_campaigns={group['live_campaigns']}")

    # K-Means is not part of any page read: prove it on the real code path.
    original = clustering.KMeans
    clustering.KMeans = None                  # any fit attempt would fail loudly
    try:
        t_sum, payload = ms(lambda: timed_summary(version,
                                                  (run_state or {}).get('run_id')))
    finally:
        clustering.KMeans = original
    timing = payload['timing']
    line('summary read with K-Means unavailable',
         f'{t_sum} ms (bundle_source={timing.get("bundle_source")}, '
         f'lookup_ms={timing.get("lookup_ms")}, assemble included)')
    line('  clusters served',
         [(c['category'], c['customer_count']) for c in payload['kmeans']['clusters']])
    return panel, run_state


def part_b(panel):
    print('\n=== B. COUPON VISIBILITY ON REAL DATA (rolled back) ===', flush=True)
    groups = sorted(panel['clusters'], key=lambda g: g['cluster_id'])
    if len(groups) < 2:
        line('ABORT: fewer than two clusters available', len(groups))
        return

    samples = {}
    for group in groups:
        samples[group['cluster_id']] = list(
            CustomerSegment.objects.filter(kmeans_cluster_id=group['cluster_id'])
            .order_by('customer_id').values_list('customer_id', flat=True)[:2])
    line('sample real customers per cluster', samples)

    now = timezone.now()
    try:
        with transaction.atomic():
            published = []
            for order, group in enumerate(groups):
                campaign = Campaign.objects.create(
                    name=f'LIVECHECK {group["category"]}',
                    coupon_code=f'LIVECHECK{group["cluster_id"]}',
                    offer_category='DISCOUNT',
                    discount_rule={'type': 'PERCENTAGE', 'percent': 10 + order},
                    discount_type='PERCENTAGE', discount_value=10 + order,
                    targeting_mode='KMEANS',
                    target_cluster_ids=[group['cluster_id']],
                    target_cluster_labels=[group['category']],
                    clustering_run_id=panel['run']['run_id'],
                    start_date=now - timedelta(hours=1),
                    end_date=now + timedelta(days=2),
                    min_order_amount=0, usage_type='UNLIMITED',
                    status=CampaignStatus.DRAFT,
                )
                blocker, audience = views.CampaignStatusView._publish_blocker(campaign)
                if blocker:
                    line('publish refused for', f'{campaign.coupon_code}: {blocker}')
                    continue
                campaign.status = CampaignStatus.PUBLISHED
                campaign.save(update_fields=['status'])
                published.append((campaign, audience, group))
                line(f'publish {campaign.coupon_code} -> {group["category"]}',
                     f'targeted={audience["targeted"]:,} '
                     f'newly_assigned={audience["newly_assigned"]:,} '
                     f'issued={audience["coupons_issued"]:,}')

            for campaign, audience, group in published:
                mine = samples[group['cluster_id']][0]
                code = campaign.coupon_code
                t_offers, offers = ms(
                    lambda c=mine: personalization.eligible_offers(c)['offers'])
                seen = [o['coupon_code'] for o in offers]
                cluster_codes = [c for c in seen if c.startswith('LIVECHECK')]
                legacy_codes = [c for c in seen if not c.startswith('LIVECHECK')]
                line(f'{group["category"][:20]:20s} customer {mine} sees',
                     f'own-cluster coupon: {cluster_codes} (expected [{code}], '
                     f'{t_offers} ms)')
                assert cluster_codes == [code], (mine, cluster_codes)
                if legacy_codes:
                    line('   ALSO visible (pre-existing legacy campaigns)',
                         f'{legacy_codes}')
                shown = offers[0]
                line('   what that customer is told',
                     f"summary={shown['offer_summary']!r} "
                     f"min_order={shown['min_order_amount']} "
                     f"valid_to={shown['end_date'][:10]} status={shown['status']}")

                other_group = groups[(groups.index(group) + 1) % len(groups)]
                other = samples[other_group['cluster_id']][0]
                t_check, reason = ms(lambda: _refused(other, code))
                line(f'   {other_group["category"][:18]:18s} customer trying {code}',
                     f'refused: {reason} ({t_check} ms)')
                t_seen, other_offers = ms(
                    lambda c=other: [o['coupon_code'] for o in
                                     personalization.eligible_offers(c)['offers']])
                assert code not in other_offers, (other, other_offers)

            # Re-issuing to the same campaign can never duplicate a coupon.
            first, _audience, group = published[0]
            before = CampaignAudience.objects.filter(campaign=first).count()
            views.CampaignStatusView._issue_coupons(first)
            views.CampaignStatusView._issue_coupons(first)
            after = CampaignAudience.objects.filter(campaign=first).count()
            distinct = (CampaignAudience.objects.filter(campaign=first)
                        .values_list('customer_id', flat=True).distinct().count())
            line('publishing again to one campaign',
                 f'{before} -> {after} rows, {distinct} distinct (no duplicates)')
            assert after == before == distinct
            raise _Rollback()
    except _Rollback:
        pass

    line('after rollback: LIVECHECK campaigns / assignments',
         f'{Campaign.objects.filter(coupon_code__startswith="LIVECHECK").count()}'
         f' / {CampaignAudience.objects.count()} (both must be 0)')


def _refused(customer_id, code):
    try:
        coupon_validation.validate_coupon(
            customer_id, code, 1000,
            cart_lines=[{'product_id': 'X', 'name': 'Kurti', 'category': 'Ethnic',
                         'quantity': 2, 'unit_price': 500.0}])
    except ValidationError as exc:
        detail = exc.detail
        return (str(next(iter(detail.values())) if isinstance(detail, dict) else detail))
    raise AssertionError(f'{customer_id} must NOT be able to use {code}')


if __name__ == '__main__':
    panel, _run_state = part_a()
    if panel:
        part_b(panel)
    print('\nDONE', flush=True)
