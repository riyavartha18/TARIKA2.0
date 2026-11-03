"""Automated tests for the RFM segmentation and personalization system.

Pure logic (scoring, segmentation) is tested directly; the cache, personalization
and coupon layers run against the SQLite test database (the managed campaign
tables exist there) with the PostgreSQL aggregation mocked, since `public.orders`
is a pre-existing dataset table that has no counterpart under test settings.

Run:  python manage.py test rfm_analysis --settings=test_settings
"""

from datetime import date, timedelta
from decimal import Decimal
import json
from unittest import mock

from django.test import TestCase
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.serializers import ValidationError as DRFValidationError
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import Role

from . import (benefits, cache_manager, campaign_audience, campaign_engine,
               campaign_publishing, cluster_targeting, clustering,
               coupon_validation, engine, personalization, queries, rfm_scoring,
               segment_store, segmentation, utils, views)
from .models import (
    Campaign, CampaignAudience, CampaignRedemption, CampaignStatus,
    ClusteringRun, CustomerSegment, DashboardSnapshot, DiscountType,
    KmeansRunState, OfferCategory, RfmAnalysisState, TargetingMode, UsageType,
)
from .serializers import CampaignSerializer


def _role_user(role):
    """An authenticated, active user stub with one of the project's roles."""
    user = mock.Mock()
    user.is_authenticated = True
    user.is_active = True
    user.role = role
    return user


def _admin_user():
    return _role_user(Role.ADMIN)


def _customer_user():
    return _role_user(Role.CUSTOMER)


def allow_legacy_campaigns(case):
    """Turn the legacy-segment visibility gate on for one test case.

    Personalised coupons come from the K-Means clusters now, and the shipped
    default hides the older rule-segment campaigns from customers (a segment a
    campaign names is not the customer's cluster). The suites that exist to
    prove the *legacy* machinery still work - segment matching, secondary tags,
    the customer-facing title strip - opt in explicitly, so the default itself is
    covered by `LegacyAudienceGateTests` instead of being silently assumed.
    """
    patcher = mock.patch.object(utils, 'LEGACY_CAMPAIGNS_VISIBLE_TO_CUSTOMERS', True)
    patcher.start()
    case.addCleanup(patcher.stop)


def _score(recency, frequency, monetary):
    """Score a single-buyer-free population and return one record's percentiles."""
    metrics = [dict(recency_days=recency, frequency=frequency, monetary=monetary)]
    return metrics


def _percentiles(record):
    return record['r_percentile'], record['f_percentile'], record['m_percentile']


class ScoringTests(TestCase):
    def test_empty_population_is_safe(self):
        self.assertEqual(rfm_scoring.score_metrics([]), [])

    def test_single_buyer_no_division_by_zero(self):
        metrics = [{'customer_id': 'A', 'recency_days': 5, 'frequency': 2, 'monetary': 100}]
        rfm_scoring.score_metrics(metrics)
        self.assertEqual(metrics[0]['r_percentile'], 100.0)
        self.assertEqual(metrics[0]['m_score'], 5)

    def test_percentile_directions(self):
        # Low recency + high frequency + high monetary must rank top on all three.
        rows = [
            {'customer_id': 'best', 'recency_days': 1, 'frequency': 10, 'monetary': 9000},
            {'customer_id': 'mid', 'recency_days': 50, 'frequency': 5, 'monetary': 4000},
            {'customer_id': 'worst', 'recency_days': 300, 'frequency': 1, 'monetary': 100},
        ]
        rfm_scoring.score_metrics(rows)
        best, _mid, worst = rows
        self.assertEqual((_percentiles(best)), (100.0, 100.0, 100.0))
        self.assertEqual((_percentiles(worst)), (0.0, 0.0, 0.0))

    def test_average_rank_ties_are_shared(self):
        # Three buyers where two share the top monetary value: the tied pair
        # must get the same percentile (average rank), not be split.
        rows = [
            {'customer_id': 'a', 'recency_days': 1, 'frequency': 3, 'monetary': 500},
            {'customer_id': 'b', 'recency_days': 2, 'frequency': 2, 'monetary': 500},
            {'customer_id': 'c', 'recency_days': 3, 'frequency': 1, 'monetary': 100},
        ]
        rfm_scoring.score_metrics(rows)
        self.assertEqual(rows[0]['m_percentile'], rows[1]['m_percentile'])
        self.assertGreater(rows[0]['m_percentile'], rows[2]['m_percentile'])

    def test_score_boundaries_are_inclusive(self):
        # A percentile of exactly 20 scores 1; just above 20 scores 2.
        self.assertEqual(rfm_scoring._score_from_percentile(20.0), 1)
        self.assertEqual(rfm_scoring._score_from_percentile(20.01), 2)
        self.assertEqual(rfm_scoring._score_from_percentile(80.0), 4)
        self.assertEqual(rfm_scoring._score_from_percentile(100.0), 5)


class SegmentationTests(TestCase):
    def test_champions(self):
        seg, tags = segmentation.classify(85, 90, 95)
        self.assertEqual(seg, utils.SEGMENT_CHAMPIONS)
        self.assertIn(utils.TAG_BIG_SPENDER, tags)

    def test_loyal_ignores_monetary(self):
        # Loyal: R>=60, F>=80, M any. A low M still lands Loyal, not Others.
        seg, _ = segmentation.classify(65, 85, 5)
        self.assertEqual(seg, utils.SEGMENT_LOYAL)

    def test_potential_loyalists(self):
        seg, _ = segmentation.classify(85, 40, 10)
        self.assertEqual(seg, utils.SEGMENT_POTENTIAL_LOYALISTS)

    def test_new_customers(self):
        seg, _ = segmentation.classify(85, 15, 40)
        self.assertEqual(seg, utils.SEGMENT_NEW)

    def test_at_risk_ignores_monetary(self):
        seg, _ = segmentation.classify(20, 70, 99)
        self.assertEqual(seg, utils.SEGMENT_AT_RISK)

    def test_hibernating(self):
        seg, _ = segmentation.classify(10, 20, 30)
        self.assertEqual(seg, utils.SEGMENT_HIBERNATING)

    def test_residual_recent_frequency_dominant_is_loyal(self):
        # Matches no primary rule; recent + frequency-dominant -> Loyal.
        seg, _ = segmentation.classify(55, 70, 60)
        self.assertEqual(seg, utils.SEGMENT_LOYAL)

    def test_residual_recent_low_frequency_is_new(self):
        seg, _ = segmentation.classify(85, 10, 70)
        self.assertEqual(seg, utils.SEGMENT_NEW)

    def test_residual_recent_mid_is_potential_loyalist(self):
        seg, _ = segmentation.classify(50, 50, 50)
        self.assertEqual(seg, utils.SEGMENT_POTENTIAL_LOYALISTS)

    def test_residual_dormant_valuable_is_at_risk(self):
        seg, _ = segmentation.classify(30, 55, 20)
        self.assertEqual(seg, utils.SEGMENT_AT_RISK)

    def test_residual_dormant_low_everything_is_hibernating(self):
        seg, _ = segmentation.classify(30, 20, 20)
        self.assertEqual(seg, utils.SEGMENT_HIBERNATING)

    def test_no_eligible_buyer_is_unclassified(self):
        # Exhaustiveness: across a percentile grid every buyer lands in one of
        # the six primary segments - there is no "Others" outcome anywhere.
        grid = range(0, 101, 5)
        for r in grid:
            for f in grid:
                for m in grid:
                    seg, _tags = segmentation.classify(r, f, m)
                    self.assertIn(seg, utils.PRIMARY_SEGMENTS)
                    self.assertNotEqual(seg, 'Others')

    def test_fallback_preserves_big_spender_tag(self):
        # A residual buyer with M>=90 is still tagged Big Spender (secondary)
        # while landing a primary segment.
        seg, tags = segmentation.classify(30, 20, 95)
        self.assertEqual(seg, utils.SEGMENT_AT_RISK)
        self.assertIn(utils.TAG_BIG_SPENDER, tags)

    def test_priority_champion_over_loyal(self):
        # R80/F80/M80 satisfies both Champions and Loyal; Champions wins first.
        seg, _ = segmentation.classify(80, 80, 80)
        self.assertEqual(seg, utils.SEGMENT_CHAMPIONS)

    def test_big_spender_is_a_tag_not_a_segment(self):
        # M>=90 with weak R/F: the residual is mapped to a real primary segment
        # and Big Spender stays an independent secondary tag (never its own
        # primary segment).
        seg, tags = segmentation.classify(30, 30, 95)
        self.assertNotEqual(seg, 'Big Spenders')
        self.assertNotEqual(seg, 'Others')
        self.assertIn(seg, utils.PRIMARY_SEGMENTS)
        self.assertIn(utils.TAG_BIG_SPENDER, tags)

    def test_full_population_fully_classified_no_others(self):
        # Score + segment a whole buyer population and assert the counts add up
        # to exactly the number of buyers, spread across only the six segments
        # (proving the snapshot/summary backend can never emit an "Others").
        from . import rfm_scoring
        rows = []
        for i in range(500):
            rows.append({
                'customer_id': f'U{i}',
                'recency_days': (i * 37) % 300,
                'frequency': (i * 13) % 40,
                'monetary': (i * 991) % 5000,
            })
        rfm_scoring.score_metrics(rows)
        segmentation.apply_segments(rows)
        counts, _big = segmentation.segment_counts(rows)
        self.assertEqual(sum(counts.values()), len(rows))
        self.assertNotIn('Others', counts)
        self.assertEqual(set(counts), set(utils.PRIMARY_SEGMENTS))
        self.assertTrue(all(r['segment'] in utils.PRIMARY_SEGMENTS for r in rows))

    def test_big_spender_boundary(self):
        self.assertEqual(segmentation.classify(50, 50, 89.99)[1], [])
        self.assertIn(utils.TAG_BIG_SPENDER, segmentation.classify(50, 50, 90)[1])


class CacheSnapshotTests(TestCase):
    def setUp(self):
        cache = cache_manager.cache  # the LocMemCache under test settings
        cache.clear()
        cache_manager._index_memo.clear()

    def _snapshot(self, n=3):
        records = [
            {'customer_id': f'U{i}', 'customer_name': f'Name{i}', 'segment': utils.SEGMENT_POTENTIAL_LOYALISTS,
             'tags': [], 'recency_days': i, 'frequency': i, 'monetary': i * 10,
             'r_percentile': 50, 'f_percentile': 50, 'm_percentile': 50,
             'r_score': 3, 'f_score': 3, 'm_score': 3}
            for i in range(n)
        ]
        return {
            'status': 'completed', 'analysis_date': '2026-01-01',
            'totals': {'total_customers': n, 'never_purchased_customers': 0},
            'segment_counts': {s: 0 for s in utils.PRIMARY_SEGMENTS},
            'big_spender_count': 0, 'buyer_count': n,
            'customer_ids': sorted(r['customer_id'] for r in records),
            'records': records, 'compute_ms': 1.0,
        }

    def test_version_increments_and_pointer_flips(self):
        v1 = cache_manager.publish_snapshot(self._snapshot())
        v2 = cache_manager.publish_snapshot(self._snapshot())
        self.assertEqual((v1, v2), (1, 2))
        self.assertEqual(cache_manager.get_latest_version(), 2)

    def test_meta_and_records_are_split(self):
        version = cache_manager.publish_snapshot(self._snapshot(5))
        meta = cache_manager.get_meta(version)
        records, ids = cache_manager.get_records(version)
        self.assertNotIn('records', meta)      # summary stays small
        self.assertEqual(len(records), 5)
        self.assertEqual(len(ids), 5)

    def test_no_partial_analysis_visible(self):
        # Before any publish, the pointer is absent and nothing is readable.
        self.assertIsNone(cache_manager.get_latest_version())
        self.assertIsNone(cache_manager.get_meta())
        self.assertIsNone(cache_manager.get_records()[0])

    def test_run_lock_is_exclusive(self):
        self.assertTrue(cache_manager.acquire_run_lock())
        self.assertFalse(cache_manager.acquire_run_lock())
        cache_manager.release_run_lock()
        self.assertTrue(cache_manager.acquire_run_lock())

    def _mixed_snapshot(self):
        def rec(cid, name, segment, tags, r_score):
            return {'customer_id': cid, 'customer_name': name, 'segment': segment,
                    'tags': tags, 'recency_days': 5, 'frequency': 3, 'monetary': 100,
                    'r_percentile': 90, 'f_percentile': 50, 'm_percentile': 95,
                    'r_score': r_score, 'f_score': 3, 'm_score': 5}
        records = [rec('U1', 'Ava', utils.SEGMENT_CHAMPIONS, [utils.TAG_BIG_SPENDER], 5),
                   rec('U2', 'Ben', utils.SEGMENT_CHAMPIONS, [], 3),
                   rec('U3', 'Cal', utils.SEGMENT_AT_RISK, [], 4)]
        return {'status': 'completed', 'analysis_date': '2026-01-01',
                'totals': {'total_customers': 3, 'never_purchased_customers': 0},
                'segment_counts': {s: 0 for s in utils.PRIMARY_SEGMENTS},
                'big_spender_count': 1, 'buyer_count': 3,
                'customer_ids': ['U1', 'U2', 'U3'], 'records': records, 'compute_ms': 1.0}

    def test_segment_buckets_serve_default_order(self):
        cache_manager.publish_snapshot(self._mixed_snapshot())
        champs, _v = cache_manager.get_segment_base(utils.SEGMENT_CHAMPIONS)
        self.assertEqual([r['customer_id'] for r in champs], ['U1', 'U2'])

    def test_big_spender_tag_bucket(self):
        cache_manager.publish_snapshot(self._mixed_snapshot())
        tagged, _v = cache_manager.get_segment_base(utils.TAG_BIG_SPENDER)
        self.assertEqual([r['customer_id'] for r in tagged], ['U1'])

    def test_non_default_sort_is_returned_sorted(self):
        cache_manager.publish_snapshot(self._mixed_snapshot())
        rows, _v = cache_manager.get_segment_base(utils.SEGMENT_CHAMPIONS, sort='r_score', direction='desc')
        self.assertEqual([r['r_score'] for r in rows], [5, 3])

    def test_unknown_segment_bucket_is_empty(self):
        cache_manager.publish_snapshot(self._mixed_snapshot())
        rows, _v = cache_manager.get_segment_base('Does Not Exist')
        self.assertEqual(rows, [])

    def test_project_row_keeps_only_table_columns(self):
        cache_manager.publish_snapshot(self._mixed_snapshot())
        row, _v = cache_manager.get_segment_base(utils.SEGMENT_CHAMPIONS)
        projected = cache_manager.project_row(row[0])
        self.assertEqual(set(projected), set(cache_manager.TABLE_COLUMNS))
        # Raw metrics/percentiles are not part of the table projection.
        self.assertNotIn('monetary', projected)
        self.assertNotIn('r_percentile', projected)


class PersonalizationTests(TestCase):
    def setUp(self):
        allow_legacy_campaigns(self)
        cache_manager.cache.clear()
        cache_manager._index_memo.clear()
        self.now = timezone.now()
        self._publish_one('C001', utils.SEGMENT_CHAMPIONS, [utils.TAG_BIG_SPENDER])

    def _publish_one(self, customer_id, segment, tags):
        rec = {
            'customer_id': customer_id, 'customer_name': 'Champ', 'segment': segment,
            'tags': tags, 'recency_days': 1, 'frequency': 9, 'monetary': 900,
            'r_percentile': 95, 'f_percentile': 95, 'm_percentile': 95,
            'r_score': 5, 'f_score': 5, 'm_score': 5,
        }
        snapshot = {
            'status': 'completed', 'analysis_date': self.now.date().isoformat(),
            'totals': {}, 'segment_counts': {}, 'big_spender_count': 0, 'buyer_count': 1,
            'customer_ids': [customer_id], 'records': [rec], 'compute_ms': 1.0,
        }
        cache_manager.publish_snapshot(snapshot)

    def _campaign(self, **overrides):
        base = dict(
            name='Champ VIP', coupon_code='CHAMP20',
            discount_type=DiscountType.PERCENTAGE, discount_value=20,
            target_segments=[utils.SEGMENT_CHAMPIONS], target_tags=[],
            start_date=self.now - timedelta(days=1), end_date=self.now + timedelta(days=1),
            min_order_amount=0, usage_type=UsageType.UNLIMITED,
            status=CampaignStatus.PUBLISHED,
        )
        base.update(overrides)
        return Campaign.objects.create(**base)

    def test_no_analysis_means_no_offers(self):
        cache_manager.cache.clear()
        cache_manager._index_memo.clear()
        # The self-heal path must not start a real analysis thread here.
        with mock.patch('rfm_analysis.engine.ensure_latest'):
            result = personalization.eligible_offers('C001')
        self.assertEqual(result['offers'], [])

    def test_champion_sees_champion_campaign(self):
        self._campaign()
        result = personalization.eligible_offers('C001')
        self.assertEqual(len(result['offers']), 1)
        self.assertEqual(result['offers'][0]['coupon_code'], 'CHAMP20')

    def test_expired_campaign_hidden(self):
        self._campaign(end_date=self.now - timedelta(hours=1))
        self.assertEqual(personalization.eligible_offers('C001')['offers'], [])

    def test_draft_campaign_hidden(self):
        self._campaign(status=CampaignStatus.DRAFT)
        self.assertEqual(personalization.eligible_offers('C001')['offers'], [])

    def test_paused_campaign_hidden(self):
        self._campaign(status=CampaignStatus.PAUSED)
        self.assertEqual(personalization.eligible_offers('C001')['offers'], [])

    def test_secondary_tag_required(self):
        # Requires Big Spender tag; the champion carries it, so it matches.
        self._campaign(target_tags=[utils.TAG_BIG_SPENDER])
        self.assertEqual(len(personalization.eligible_offers('C001')['offers']), 1)

    def test_segment_without_required_tag_is_hidden(self):
        # Requires a tag the customer does not have.
        self._campaign(target_tags=['Some Other Tag'])
        self.assertEqual(personalization.eligible_offers('C001')['offers'], [])

    def test_segment_change_after_new_analysis(self):
        # Re-run flips the champion to At-Risk: their campaign disappears.
        self._campaign()
        self.assertEqual(len(personalization.eligible_offers('C001')['offers']), 1)
        self._publish_one('C001', utils.SEGMENT_AT_RISK, [])
        self.assertEqual(personalization.eligible_offers('C001')['offers'], [])

    def test_offer_title_has_no_segment_prefix_for_any_segment(self):
        # Campaigns are authored as "<Segment>: <Offer>", but the label is an
        # internal targeting detail: every one of the six buyer segments must
        # get the plain offer title back, with eligibility still segment-driven.
        for segment in utils.PRIMARY_SEGMENTS:
            with self.subTest(segment=segment):
                cache_manager.cache.clear()
                cache_manager._index_memo.clear()
                self._publish_one('C001', segment, [])
                self._campaign(
                    name=f'{segment}: VIP 15% OFF',
                    coupon_code=f'CODE_{segment.upper().replace(" ", "_").replace("-", "_")}',
                    target_segments=[segment],
                )
                offers = personalization.eligible_offers('C001')['offers']
                self.assertEqual(len(offers), 1)
                self.assertEqual(offers[0]['name'], 'VIP 15% OFF')
                # Segment data stays on the payload for targeting/eligibility.
                self.assertEqual(offers[0]['target_segments'], [segment])

    def test_other_segments_campaign_is_hidden_even_after_stripping(self):
        # Same stripped title, different segment: still never visible.
        self._campaign(name='At-Risk: Comeback Combo', coupon_code='RISK_COME',
                       target_segments=[utils.SEGMENT_AT_RISK])
        self.assertEqual(personalization.eligible_offers('C001')['offers'], [])

    def test_cold_cache_starts_a_run_instead_of_claiming_no_offers(self):
        # The snapshot lives in the cache only, so a restarted server has real
        # published campaigns and no analysis yet. That must never be presented
        # as "you have no offers": a run is requested and the caller is told.
        self._campaign()
        cache_manager.cache.clear()
        cache_manager._index_memo.clear()
        with mock.patch('rfm_analysis.engine.ensure_latest') as ensure_latest:
            result = personalization.eligible_offers('C001')
            # Sustained traffic must not launch a run per request.
            personalization.eligible_offers('C002')
        ensure_latest.assert_called_once()
        self.assertEqual(result['offers'], [])
        self.assertTrue(result['syncing'])

    def test_customer_without_a_segment_is_not_reported_as_syncing(self):
        # A completed analysis exists; this buyer simply is not in it (never
        # purchased), which is a real empty state, not a pending one.
        self._campaign()
        result = personalization.eligible_offers('C999')
        self.assertEqual(result['offers'], [])
        self.assertFalse(result['syncing'])

    def test_offers_are_ordered_newest_campaign_first(self):
        self._campaign(name='Champions: Older Offer', coupon_code='CH_OLD',
                       start_date=self.now - timedelta(days=5),
                       end_date=self.now + timedelta(days=5))
        self._campaign(name='Champions: Newest Offer', coupon_code='CH_NEW',
                       start_date=self.now - timedelta(hours=1))
        names = [offer['name']
                 for offer in personalization.eligible_offers('C001')['offers']]
        self.assertEqual(names, ['Newest Offer', 'Older Offer'])

    def test_redeemed_offer_stays_visible_marked_used(self):
        campaign = self._campaign(name='Champions: VIP 15% OFF', coupon_code='CH_VIP15')
        offers = personalization.eligible_offers('C001')['offers']
        self.assertEqual(offers[0]['status'], personalization.STATUS_AVAILABLE)

        coupon_validation.redeem(campaign.campaign_id, 'C001', 'ORD1', 150)

        offers = personalization.eligible_offers('C001')['offers']
        self.assertEqual([o['status'] for o in offers], [personalization.STATUS_USED])
        self.assertEqual(offers[0]['coupon_code'], 'CH_VIP15')
        self.assertEqual(offers[0]['used_on_order'], 'ORD1')
        self.assertIsNotNone(offers[0]['used_at'])

    def test_used_offer_survives_the_campaign_being_paused(self):
        campaign = self._campaign(name='Champions: Exclusive Gift', coupon_code='CH_GIFT')
        coupon_validation.redeem(campaign.campaign_id, 'C001', 'ORD1', 0)

        campaign.status = CampaignStatus.PAUSED
        campaign.save(update_fields=['status'])

        # A paused offer nobody used disappears; this one is part of the
        # customer's history and must remain visible, permanently Used.
        offers = personalization.eligible_offers('C001')['offers']
        self.assertEqual([o['coupon_code'] for o in offers], ['CH_GIFT'])
        self.assertEqual(offers[0]['status'], personalization.STATUS_USED)

    def test_available_offers_come_before_used_ones(self):
        used = self._campaign(name='Champions: Older Offer', coupon_code='CH_OLD',
                              start_date=self.now - timedelta(days=5),
                              end_date=self.now + timedelta(days=5))
        self._campaign(name='Champions: Newest Offer', coupon_code='CH_NEW',
                       start_date=self.now - timedelta(hours=1))
        coupon_validation.redeem(used.campaign_id, 'C001', 'ORD1', 100)

        offers = personalization.eligible_offers('C001')['offers']
        self.assertEqual([o['name'] for o in offers], ['Newest Offer', 'Older Offer'])
        self.assertEqual([o['status'] for o in offers],
                         [personalization.STATUS_AVAILABLE, personalization.STATUS_USED])

    def test_lapsed_unused_campaign_is_not_shown(self):
        self._campaign(name='Champions: Ended Offer', coupon_code='CH_END',
                       start_date=self.now - timedelta(days=5),
                       end_date=self.now - timedelta(hours=1))
        self.assertEqual(personalization.eligible_offers('C001')['offers'], [])


class SegmentStoreTests(TestCase):
    """The durable per-customer segment store behind the customer offer path."""

    def setUp(self):
        allow_legacy_campaigns(self)
        cache_manager.cache.clear()
        cache_manager._index_memo.clear()
        CustomerSegment.objects.all().delete()
        RfmAnalysisState.objects.all().delete()
        self.now = timezone.now()

    def _records(self, customers):
        return [{'customer_id': cid, 'segment': segment, 'tags': tags}
                for cid, segment, tags in customers]

    def _campaign(self, **overrides):
        base = dict(
            name='Champions: VIP 15% OFF', coupon_code='CHAMP20',
            discount_type=DiscountType.PERCENTAGE, discount_value=15,
            target_segments=[utils.SEGMENT_CHAMPIONS], target_tags=[],
            start_date=self.now - timedelta(days=1), end_date=self.now + timedelta(days=1),
            min_order_amount=0, usage_type=UsageType.UNLIMITED,
            status=CampaignStatus.PUBLISHED,
        )
        base.update(overrides)
        return Campaign.objects.create(**base)

    def test_offers_come_from_stored_segments_with_no_snapshot_at_all(self):
        self._campaign()
        segment_store.store_records(
            self._records([('C001', utils.SEGMENT_CHAMPIONS, [utils.TAG_BIG_SPENDER])]), 7)

        # Nothing in the cache: this is exactly the state of a restarted server.
        self.assertIsNone(cache_manager.get_latest_version())
        with mock.patch('rfm_analysis.engine.ensure_latest') as ensure_latest:
            result = personalization.eligible_offers('C001')

        ensure_latest.assert_not_called()
        self.assertEqual(result['version'], 7)
        self.assertEqual(result['segment'], utils.SEGMENT_CHAMPIONS)
        self.assertEqual([offer['name'] for offer in result['offers']], ['VIP 15% OFF'])

    def test_buyer_missing_from_the_stored_analysis_gets_no_offers_and_no_rerun(self):
        segment_store.store_records(self._records([('C001', utils.SEGMENT_CHAMPIONS, [])]), 3)

        with mock.patch('rfm_analysis.engine.ensure_latest') as ensure_latest:
            result = personalization.eligible_offers('C555')

        ensure_latest.assert_not_called()
        self.assertEqual(result['offers'], [])
        self.assertFalse(result['syncing'])

    def test_a_new_run_replaces_stale_segment_rows(self):
        segment_store.store_records(self._records([
            ('C001', utils.SEGMENT_CHAMPIONS, []),
            ('C002', utils.SEGMENT_LOYAL, []),
        ]), 1)

        segment_store.store_records(self._records([
            ('C001', utils.SEGMENT_AT_RISK, []),
        ]), 2)

        row = segment_store.get('C001')
        self.assertEqual(row.segment, utils.SEGMENT_AT_RISK)
        self.assertEqual(row.version, 2)
        self.assertIsNone(segment_store.get('C002'))
        state = segment_store.get_state()
        self.assertEqual((state.version, state.buyer_count), (2, 1))

    def test_lapsed_campaigns_are_filtered_in_the_query(self):
        self._campaign()
        self._campaign(name='Champions: Ended', coupon_code='ENDED1',
                       start_date=self.now - timedelta(days=10),
                       end_date=self.now - timedelta(days=1))
        live = campaign_engine.fetch_published_campaigns()
        self.assertEqual([c.coupon_code for c in live], ['CHAMP20'])


class OfferCacheTests(TestCase):
    """A campaign edit must reach customers immediately, not after a TTL."""

    def setUp(self):
        cache_manager.cache.clear()

    def test_campaign_epoch_invalidates_cached_customer_offers(self):
        epoch_before = cache_manager.get_campaign_epoch()
        cache_manager.set_cached_offers('C001', {'version': 1, 'offers': ['live']})
        self.assertEqual(len(cache_manager.get_cached_offers('C001')['offers']), 1)

        cache_manager.bump_campaign_epoch()

        self.assertEqual(cache_manager.get_campaign_epoch(), epoch_before + 1)
        self.assertIsNone(cache_manager.get_cached_offers('C001'))

    def test_a_new_analysis_invalidates_cached_customer_offers(self):
        cache_manager.set_cached_offers('C001', {'version': 1, 'offers': ['live']})

        # Publishing a completed run changes who belongs to which segment, so
        # nothing a customer was shown before may be reused.
        cache_manager.publish_snapshot({
            'status': 'completed', 'analysis_date': '2026-01-01', 'totals': {},
            'segment_counts': {}, 'big_spender_count': 0, 'buyer_count': 0,
            'customer_ids': [], 'records': [], 'compute_ms': 1.0,
        })

        self.assertIsNone(cache_manager.get_cached_offers('C001'))

    def test_a_redemption_also_invalidates_the_cached_status_list(self):
        cache_manager.set_cached_offers('C001', {'version': 1, 'offers': ['live']})
        cache_manager.bump_campaign_epoch()   # what coupon_validation.redeem does
        self.assertIsNone(cache_manager.get_cached_offers('C001'))

    def test_undecided_offers_are_never_cached(self):
        # A response with no analysis behind it must not be parked in the cache,
        # or the customer would keep seeing "no offers" after the run completes.
        cache_manager.set_cached_offers('C001', {'version': None, 'offers': []})
        self.assertIsNone(cache_manager.get_cached_offers('C001'))


class CouponValidationTests(TestCase):
    def setUp(self):
        allow_legacy_campaigns(self)
        cache_manager.cache.clear()
        cache_manager._index_memo.clear()
        self.now = timezone.now()
        self._publish_one('C001', utils.SEGMENT_CHAMPIONS, [utils.TAG_BIG_SPENDER])

    def _publish_one(self, customer_id, segment, tags):
        rec = {'customer_id': customer_id, 'customer_name': 'Champ', 'segment': segment,
               'tags': tags, 'recency_days': 1, 'frequency': 9, 'monetary': 900,
               'r_percentile': 95, 'f_percentile': 95, 'm_percentile': 95,
               'r_score': 5, 'f_score': 5, 'm_score': 5}
        cache_manager.publish_snapshot({
            'status': 'completed', 'analysis_date': self.now.date().isoformat(),
            'totals': {}, 'segment_counts': {}, 'big_spender_count': 0, 'buyer_count': 1,
            'customer_ids': [customer_id], 'records': [rec], 'compute_ms': 1.0,
        })

    def _campaign(self, **overrides):
        base = dict(
            name='Champ 20', coupon_code='CHAMP20',
            discount_type=DiscountType.PERCENTAGE, discount_value=20,
            target_segments=[utils.SEGMENT_CHAMPIONS], target_tags=[],
            start_date=self.now - timedelta(days=1), end_date=self.now + timedelta(days=1),
            min_order_amount=0, usage_type=UsageType.UNLIMITED,
            status=CampaignStatus.PUBLISHED,
        )
        base.update(overrides)
        return Campaign.objects.create(**base)

    def test_unknown_coupon_rejected(self):
        with self.assertRaises(ValidationError):
            coupon_validation.validate_coupon('C001', 'NOPE', 1000)

    def test_percentage_discount_recomputed_server_side(self):
        self._campaign()
        result = coupon_validation.validate_coupon('C001', 'champ20', 2000)
        self.assertEqual(result['discount'], 400.0)   # 20% of 2000
        self.assertEqual(result['payable'], 1600.0)

    def test_max_discount_caps_percentage(self):
        self._campaign(max_discount=300)
        self.assertEqual(coupon_validation.validate_coupon('C001', 'CHAMP20', 2000)['discount'], 300.0)

    def test_minimum_order_enforced(self):
        self._campaign(min_order_amount=1500)
        with self.assertRaises(ValidationError):
            coupon_validation.validate_coupon('C001', 'CHAMP20', 1000)

    def test_unlimited_usage_repeated(self):
        self._campaign()
        for _ in range(3):
            self.assertEqual(
                coupon_validation.validate_coupon('C001', 'CHAMP20', 1000)['discount'], 200.0)

    def test_once_per_customer_limit(self):
        campaign = self._campaign(usage_type=UsageType.ONCE)
        first = coupon_validation.validate_coupon('C001', 'CHAMP20', 1000)
        coupon_validation.redeem(campaign.campaign_id, 'C001', 'ORD1', first['discount'])
        with self.assertRaises(ValidationError):
            coupon_validation.validate_coupon('C001', 'CHAMP20', 1000)

    def test_limited_per_customer_count(self):
        # The business rule is one redemption per customer per coupon, so a
        # higher per-customer limit can never allow a second use: the second
        # booking is refused and the coupon stops being offerable.
        campaign = self._campaign(usage_type=UsageType.LIMITED, per_customer_limit=2)
        first = coupon_validation.validate_coupon('C001', 'CHAMP20', 1000)
        self.assertTrue(coupon_validation.redeem(campaign.campaign_id, 'C001', 'ORD0',
                                                 first['discount']))
        self.assertFalse(coupon_validation.redeem(campaign.campaign_id, 'C001', 'ORD1',
                                                 first['discount']))
        self.assertEqual(CampaignRedemption.objects.count(), 1)
        with self.assertRaises(ValidationError) as ctx:
            coupon_validation.validate_coupon('C001', 'CHAMP20', 1000)
        self.assertIn('already used', str(ctx.exception).lower())

    def test_one_use_per_customer_even_for_unlimited(self):
        campaign = self._campaign(usage_type=UsageType.UNLIMITED)
        first = coupon_validation.validate_coupon('C001', 'CHAMP20', 1000)
        coupon_validation.redeem(campaign.campaign_id, 'C001', 'ORD1', first['discount'])

        # A brand new cart, a different order id: still refused.
        with self.assertRaises(ValidationError) as ctx:
            coupon_validation.validate_coupon('C001', 'CHAMP20', 3000)
        self.assertIn('already used this coupon', str(ctx.exception).lower())

    def test_another_customer_can_still_use_the_same_coupon(self):
        # The limit is per customer, not global: C002 is a champion too.
        campaign = self._campaign()
        self._publish_two_champions()
        first = coupon_validation.validate_coupon('C001', 'CHAMP20', 1000)
        coupon_validation.redeem(campaign.campaign_id, 'C001', 'ORD1', first['discount'])

        second = coupon_validation.validate_coupon('C002', 'CHAMP20', 1000)
        self.assertEqual(second['discount'], 200.0)
        self.assertTrue(coupon_validation.redeem(campaign.campaign_id, 'C002', 'ORD2',
                                                 second['discount']))
        self.assertEqual(CampaignRedemption.objects.count(), 2)

    def test_database_blocks_a_duplicate_redemption_row(self):
        campaign = self._campaign()
        coupon_validation.redeem(campaign.campaign_id, 'C001', 'ORD1', 200)
        from django.db import transaction as db_transaction
        from django.db.utils import IntegrityError
        with db_transaction.atomic():
            with self.assertRaises(IntegrityError):
                CampaignRedemption.objects.create(campaign=campaign, customer_id='C001',
                                                  order_id='ORD2', discount_applied=200)

    def _publish_two_champions(self):
        records, ids = [], []
        for customer_id in ('C001', 'C002'):
            ids.append(customer_id)
            records.append({
                'customer_id': customer_id, 'customer_name': customer_id,
                'segment': utils.SEGMENT_CHAMPIONS, 'tags': [],
                'recency_days': 1, 'frequency': 9, 'monetary': 900,
                'r_percentile': 95, 'f_percentile': 95, 'm_percentile': 95,
                'r_score': 5, 'f_score': 5, 'm_score': 5,
            })
        cache_manager.publish_snapshot({
            'status': 'completed', 'analysis_date': self.now.date().isoformat(),
            'totals': {}, 'segment_counts': {}, 'big_spender_count': 0,
            'buyer_count': 2, 'customer_ids': ids, 'records': records, 'compute_ms': 1.0,
        })

    def test_global_usage_limit(self):
        self._campaign(global_usage_limit=1)
        coupon_validation.validate_coupon('C001', 'CHAMP20', 1000)  # no redemption yet
        # Book one redemption from another customer, then the global cap bites.
        campaign = Campaign.objects.get(coupon_code='CHAMP20')
        coupon_validation.redeem(campaign.campaign_id, 'C999', 'ORDX', 200)
        with self.assertRaises(ValidationError):
            coupon_validation.validate_coupon('C001', 'CHAMP20', 1000)

    def test_duplicate_order_protection(self):
        campaign = self._campaign()
        self.assertTrue(coupon_validation.redeem(campaign.campaign_id, 'C001', 'ORD1', 200))
        # Same coupon on the same order a second time is refused, not double-booked.
        self.assertFalse(coupon_validation.redeem(campaign.campaign_id, 'C001', 'ORD1', 200))
        self.assertEqual(CampaignRedemption.objects.filter(order_id='ORD1').count(), 1)

    def test_segment_change_blocks_coupon(self):
        self._campaign()
        self._publish_one('C001', utils.SEGMENT_AT_RISK, [])  # segment moved
        with self.assertRaises(ValidationError):
            coupon_validation.validate_coupon('C001', 'CHAMP20', 1000)


def _line(product_id, price, qty=1, category=''):
    return {'product_id': product_id, 'name': product_id, 'category': category,
            'quantity': qty, 'unit_price': price}


class BenefitsComputationTests(TestCase):
    """Pure offer maths for every discount and Buy & Get rule type."""

    def _campaign(self, **overrides):
        base = dict(
            name='B', coupon_code='BEN1',
            target_segments=[utils.SEGMENT_CHAMPIONS],
            start_date=timezone.now() - timedelta(days=1),
            end_date=timezone.now() + timedelta(days=1),
            discount_value=0, offer_category=OfferCategory.DISCOUNT,
        )
        base.update(overrides)
        return Campaign(**base)  # unsaved: computation touches no database

    def test_percentage_with_cap(self):
        c = self._campaign(discount_rule={'type': 'PERCENTAGE', 'percent': 15},
                           max_discount=100)
        result = benefits.compute_benefits(c, [_line('p1', 5000)], 5000)
        self.assertEqual(result['discount'], 100.0)

    def test_spend_based_requires_threshold(self):
        c = self._campaign(discount_rule={'type': 'SPEND_BASED',
                                          'spend_threshold': 3000,
                                          'spend_discount': 300})
        self.assertEqual(benefits.compute_benefits(c, [], 2999)['discount'], 0.0)
        self.assertEqual(benefits.compute_benefits(c, [], 3000)['discount'], 300.0)

    def test_buy_more_save_more_best_tier(self):
        c = self._campaign(discount_rule={
            'type': 'BUY_MORE_SAVE_MORE',
            'tiers': [{'buy': 2, 'percent': 10}, {'buy': 3, 'percent': 20}]})
        lines = [_line('p1', 1000, qty=3)]
        result = benefits.compute_benefits(c, lines, 3000)
        self.assertEqual(result['discount'], 600.0)  # 3 units -> 20% tier

    def test_cashback_never_reduces_payable(self):
        c = self._campaign(discount_rule={'type': 'CASHBACK', 'cashback': 200})
        result = benefits.compute_benefits(c, [_line('p1', 1000)], 1000)
        self.assertEqual(result['discount'], 0.0)
        self.assertEqual(result['cashback'], 200.0)
        self.assertTrue(result['benefit_applied'])

    def test_free_shipping_flags_only(self):
        c = self._campaign(discount_rule={'type': 'FREE_SHIPPING'})
        result = benefits.compute_benefits(c, [_line('p1', 500)], 500)
        self.assertTrue(result['free_shipping'])
        self.assertEqual(result['discount'], 0.0)

    def test_buy_2_get_1_free_cheapest_unit_free(self):
        c = self._campaign(offer_category=OfferCategory.BUY_GET,
                           buy_get_rule={'type': 'BUY_X_GET_Y_FREE',
                                         'buy_qty': 2, 'get_qty': 1})
        lines = [_line('p1', 500), _line('p2', 400), _line('p3', 300)]
        result = benefits.compute_benefits(c, lines, 1200)
        self.assertEqual(result['discount'], 300.0)   # cheapest of the trio

    def test_bogo_free_unit(self):
        c = self._campaign(offer_category=OfferCategory.BUY_GET,
                           buy_get_rule={'type': 'BOGO'})
        lines = [_line('p1', 500), _line('p2', 400)]
        result = benefits.compute_benefits(c, lines, 900)
        self.assertEqual(result['discount'], 400.0)

    def test_buy_2_get_1_at_percent_off(self):
        c = self._campaign(offer_category=OfferCategory.BUY_GET,
                           buy_get_rule={'type': 'BUY_X_GET_Y_DISCOUNT', 'buy_qty': 1,
                                         'get_qty': 1, 'discount_percent': 50})
        lines = [_line('p1', 1000), _line('p2', 500)]
        result = benefits.compute_benefits(c, lines, 1500)
        self.assertEqual(result['discount'], 250.0)   # 50% of the cheaper unit

    def test_bundle_reprices_only_complete_sets(self):
        rule = {'type': 'BUNDLE', 'bundle_price': 999, 'product_ids': ['p1', 'p2', 'p3']}
        c = self._campaign(offer_category=OfferCategory.BUY_GET, buy_get_rule=rule)
        complete = [_line('p1', 500), _line('p2', 400), _line('p3', 300)]
        self.assertEqual(benefits.compute_benefits(c, complete, 1200)['discount'], 201.0)
        partial = [_line('p1', 500), _line('p2', 400)]
        self.assertEqual(benefits.compute_benefits(c, partial, 900)['discount'], 0.0)

    def test_free_gift_above_minimum(self):
        c = self._campaign(offer_category=OfferCategory.BUY_GET,
                           buy_get_rule={'type': 'FREE_GIFT', 'gift_name': 'Scarf',
                                         'gift_value': 499, 'min_order_amount': 2000})
        self.assertIsNone(benefits.compute_benefits(c, [], 1999)['gift'])
        result = benefits.compute_benefits(c, [], 2000)
        self.assertEqual(result['gift']['name'], 'Scarf')
        self.assertTrue(result['benefit_applied'])

    def test_product_discount_respects_scope(self):
        c = self._campaign(offer_category=OfferCategory.BUY_GET,
                           buy_get_rule={'type': 'PRODUCT_DISCOUNT', 'discount_percent': 25},
                           scope={'mode': 'PRODUCTS', 'product_ids': ['p2']})
        lines = [_line('p1', 1000), _line('p2', 400)]
        result = benefits.compute_benefits(c, lines, 1400)
        self.assertEqual(result['discount'], 100.0)   # 25% of the scoped item only

    def test_combined_stacks_only_when_allowed(self):
        kwargs = dict(
            offer_category=OfferCategory.COMBINED,
            discount_rule={'type': 'PERCENTAGE', 'percent': 15},
            buy_get_rule={'type': 'BUY_X_GET_Y_FREE', 'buy_qty': 2, 'get_qty': 1},
        )
        lines = [_line('p1', 500), _line('p2', 400), _line('p3', 300)]
        stacked = benefits.compute_benefits(self._campaign(benefits_combinable=True, **kwargs),
                                            lines, 1200)
        self.assertEqual(stacked['discount'], 180.0 + 300.0)  # both halves
        best_of = benefits.compute_benefits(self._campaign(benefits_combinable=False, **kwargs),
                                            lines, 1200)
        self.assertEqual(best_of['discount'], 300.0)          # better half only

    def test_legacy_campaigns_still_price(self):
        c = self._campaign(discount_type=DiscountType.PERCENTAGE, discount_value=20)
        result = benefits.compute_benefits(c, [_line('p1', 2000)], 2000)
        self.assertEqual(result['discount'], 400.0)

    def test_discount_never_exceeds_cart(self):
        c = self._campaign(discount_rule={'type': 'FLAT', 'flat': 5000})
        result = benefits.compute_benefits(c, [_line('p1', 800)], 800)
        self.assertEqual(result['discount'], 800.0)


class CampaignSerializerRulesTests(TestCase):
    """Authoring guards for the historical segment path (opt-in legacy mode).

    Production authors K-Means cluster campaigns only, so this class enables the
    legacy switch to keep the segmentation-wide rules under test.
    """

    def setUp(self):
        allow_legacy_campaigns(self)

    def _payload(self, **overrides):
        base = dict(
            name='Champions VIP', coupon_code='VIP15',
            offer_category=OfferCategory.DISCOUNT,
            discount_rule={'type': 'PERCENTAGE', 'percent': 15},
            target_segments=[utils.SEGMENT_CHAMPIONS], target_tags=[],
            start_date=timezone.now() - timedelta(hours=1),
            end_date=timezone.now() + timedelta(days=7),
            min_order_amount=0, usage_type=UsageType.UNLIMITED,
        )
        base.update(overrides)
        return base

    def _errors(self, payload):
        serializer = CampaignSerializer(data=payload)
        with self.assertRaises(DRFValidationError):
            serializer.is_valid(raise_exception=True)
        return serializer.errors

    def test_valid_discount_campaign(self):
        serializer = CampaignSerializer(data=self._payload())
        self.assertTrue(serializer.is_valid(), serializer.errors)
        campaign = serializer.save()
        self.assertEqual(campaign.discount_value, 15)      # mirrored headline
        self.assertEqual(campaign.discount_type, DiscountType.PERCENTAGE)
        self.assertIn('15% OFF', benefits.offer_summary(campaign))

    def test_empty_segments_rejected(self):
        self.assertIn('target_segments', self._errors(self._payload(target_segments=[])))

    def test_never_purchased_rejected_as_audience(self):
        errors = self._errors(self._payload(target_segments=[utils.SEGMENT_NEVER_PURCHASED]))
        self.assertIn('target_segments', errors)

    def test_unknown_tag_rejected(self):
        errors = self._errors(self._payload(target_tags=['Champion League']))
        self.assertIn('target_tags', errors)

    def test_buy_get_without_rule_rejected(self):
        errors = self._errors(self._payload(offer_category=OfferCategory.BUY_GET,
                                            discount_rule={}))
        self.assertIn('buy_get_rule', errors)

    def test_combined_requires_both_rules(self):
        errors = self._errors(self._payload(offer_category=OfferCategory.COMBINED,
                                            discount_rule={}))
        self.assertIn('discount_rule', errors)
        errors = self._errors(self._payload(offer_category=OfferCategory.COMBINED,
                                            buy_get_rule={}))
        self.assertIn('buy_get_rule', errors)

    def test_combined_with_both_rules_is_valid(self):
        serializer = CampaignSerializer(data=self._payload(
            offer_category=OfferCategory.COMBINED,
            buy_get_rule={'type': 'BUY_X_GET_Y_FREE', 'buy_qty': 2, 'get_qty': 1},
            scope={'mode': 'PRODUCTS', 'product_ids': ['p1', 'p2']},
        ))
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_bad_percentage_rejected(self):
        errors = self._errors(self._payload(
            discount_rule={'type': 'PERCENTAGE', 'percent': 150}))
        self.assertIn('discount_rule', errors)

    def test_scope_products_must_list_ids(self):
        errors = self._errors(self._payload(
            offer_category=OfferCategory.BUY_GET,
            discount_rule={},
            buy_get_rule={'type': 'BOGO'},
            scope={'mode': 'PRODUCTS', 'product_ids': []}))
        self.assertIn('scope', errors)

    def test_legacy_simple_discount_still_accepted(self):
        payload = self._payload(discount_rule={}, discount_type=DiscountType.FIXED,
                                discount_value=200)
        serializer = CampaignSerializer(data=payload)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_legacy_zero_discount_rejected(self):
        payload = self._payload(discount_rule={}, discount_value=0)
        self.assertIn('discount_value', self._errors(payload))


class CampaignAudienceTests(TestCase):
    def setUp(self):
        cache_manager.cache.clear()
        cache_manager._index_memo.clear()

    def test_no_analysis_means_no_audience(self):
        from . import campaign_audience
        self.assertIsNone(
            campaign_audience.audience_count([utils.SEGMENT_CHAMPIONS], []))

    def test_audience_from_latest_snapshot(self):
        from . import campaign_audience
        now = timezone.now()
        records = [
            {'customer_id': 'C001', 'segment': utils.SEGMENT_CHAMPIONS, 'tags': ['Big Spender']},
            {'customer_id': 'C002', 'segment': utils.SEGMENT_CHAMPIONS, 'tags': []},
            {'customer_id': 'C003', 'segment': utils.SEGMENT_AT_RISK, 'tags': ['Big Spender']},
        ]
        cache_manager.publish_snapshot({
            'status': 'completed', 'analysis_date': now.date().isoformat(),
            'totals': {}, 'big_spender_count': 2, 'buyer_count': 3, 'compute_ms': 1.0,
            'segment_counts': {utils.SEGMENT_CHAMPIONS: 2, utils.SEGMENT_AT_RISK: 1},
            'customer_ids': sorted(r['customer_id'] for r in records), 'records': records,
        })
        self.assertEqual(
            campaign_audience.audience_count([utils.SEGMENT_CHAMPIONS], []), 2)
        self.assertEqual(
            campaign_audience.audience_count([utils.SEGMENT_CHAMPIONS, utils.SEGMENT_AT_RISK], []), 3)
        self.assertEqual(
            campaign_audience.audience_count([utils.SEGMENT_CHAMPIONS], ['Big Spender']), 1)


def _full_record(cid, segment, monetary, recency=10, freq=3,
                 scores=(4, 3, 5), tags=None, first='2024-01-01',
                 last='2026-01-01'):
    r, f, m = scores
    return {
        'customer_id': cid, 'segment': segment, 'tags': tags or [],
        'monetary': monetary, 'recency_days': recency, 'frequency': freq,
        'r_score': r, 'f_score': f, 'm_score': m,
        'first_purchase_date': first, 'last_purchase_date': last,
    }


class FullRfmResultStoreTests(TestCase):
    """The dedicated latest-RFM-result table synchronizes every completed run.

    Runs on the SQLite test backend, which exercises the ORM upsert path; the
    PostgreSQL conditional-skip (Case D) is a production-only behaviour covered
    by the same field-mapping contract.
    """

    def setUp(self):
        cache_manager.cache.clear()
        CustomerSegment.objects.all().delete()
        RfmAnalysisState.objects.all().delete()

    def test_full_result_fields_and_state_are_persisted(self):
        segment_store.store_records(
            [_full_record('A', utils.SEGMENT_CHAMPIONS, 500.0)],
            version=5, analysis_date=date(2026, 11, 1),
            source_fingerprint='10|3|2026-01-01')
        row = CustomerSegment.objects.get(pk='A')
        self.assertEqual(row.monetary, Decimal('500.00'))
        self.assertEqual(row.recency, 10)
        self.assertEqual(row.frequency, 3)
        self.assertEqual((row.r_score, row.f_score, row.m_score), (4, 3, 5))
        self.assertEqual(row.rfm_score, '435')
        self.assertEqual(row.first_purchase_date, date(2024, 1, 1))
        self.assertEqual(row.last_purchase_date, date(2026, 1, 1))
        self.assertEqual(row.version, 5)
        self.assertIsNotNone(row.updated_at)
        state = RfmAnalysisState.objects.get(pk=RfmAnalysisState.SINGLETON_ID)
        self.assertEqual(state.source_fingerprint, '10|3|2026-01-01')
        self.assertEqual(state.buyer_count, 1)

    def test_changed_segment_and_monetary_replace_previous_values(self):
        segment_store.store_records(
            [_full_record('A', utils.SEGMENT_POTENTIAL_LOYALISTS, 100.0)], version=1)
        segment_store.store_records(
            [_full_record('A', utils.SEGMENT_CHAMPIONS, 300.0)], version=2)
        row = CustomerSegment.objects.get(pk='A')
        self.assertEqual(row.segment, utils.SEGMENT_CHAMPIONS)
        self.assertEqual(row.monetary, Decimal('300.00'))
        self.assertEqual(row.version, 2)

    def test_new_customer_inserted_and_existing_updated(self):
        segment_store.store_records(
            [_full_record('A', utils.SEGMENT_LOYAL, 100.0)], version=1)
        stats = segment_store.store_records(
            [_full_record('A', utils.SEGMENT_LOYAL, 120.0),
             _full_record('B', utils.SEGMENT_NEW, 50.0)],
            version=2, return_stats=True)
        self.assertTrue(CustomerSegment.objects.filter(pk='B').exists())
        self.assertEqual(CustomerSegment.objects.get(pk='A').monetary,
                         Decimal('120.00'))
        self.assertEqual(stats['buyers'], 2)

    def test_full_refresh_removes_buyers_no_longer_eligible(self):
        segment_store.store_records(
            [_full_record('A', utils.SEGMENT_LOYAL, 100.0),
             _full_record('B', utils.SEGMENT_LOYAL, 50.0)], version=1)
        segment_store.store_records(
            [_full_record('A', utils.SEGMENT_LOYAL, 100.0)], version=2)
        self.assertTrue(CustomerSegment.objects.filter(pk='A').exists())
        self.assertFalse(CustomerSegment.objects.filter(pk='B').exists())

    def test_incremental_refresh_keeps_absent_rows(self):
        # Case F: a partial (incremental) batch must not delete buyers simply
        # because they were absent from it (no eligibility re-check here).
        segment_store.store_records(
            [_full_record('A', utils.SEGMENT_LOYAL, 100.0),
             _full_record('B', utils.SEGMENT_LOYAL, 50.0)], version=1)
        segment_store.store_records(
            [_full_record('A', utils.SEGMENT_LOYAL, 130.0)], version=2, full=False)
        self.assertTrue(CustomerSegment.objects.filter(pk='B').exists())


class RfmResultsEndpointTests(TestCase):
    """GET /api/analytics/rfm/results serves the persisted table, paginated."""

    def setUp(self):
        cache_manager.cache.clear()
        CustomerSegment.objects.all().delete()
        RfmAnalysisState.objects.all().delete()

    def _admin(self):
        user = mock.Mock()
        user.is_authenticated = True
        user.is_active = True
        user.role = Role.ADMIN
        return user

    def _get(self, params, user):
        request = APIRequestFactory().get('/api/analytics/rfm/results', params)
        force_authenticate(request, user=user)
        response = views.RfmResultsView.as_view()(request)
        response.render()
        return response

    def test_returns_latest_result_per_customer(self):
        segment_store.store_records(
            [_full_record('A', utils.SEGMENT_CHAMPIONS, 500.0)], version=4)
        response = self._get({}, self._admin())
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['available'])
        self.assertEqual(response.data['version'], 4)
        self.assertEqual(response.data['count'], 1)
        row = response.data['results'][0]
        self.assertEqual(row['customer_id'], 'A')
        self.assertEqual(row['monetary'], 500.0)
        self.assertEqual(row['rfm_score'], '435')
        self.assertEqual(row['calculation_version'], 4)

    def test_pagination_and_segment_filter(self):
        segment_store.store_records(
            [_full_record(f'C{i:03d}', utils.SEGMENT_CHAMPIONS if i % 2 else
                          utils.SEGMENT_AT_RISK, 100.0 + i)
             for i in range(10)], version=1)
        response = self._get({'page': 1, 'page_size': 3}, self._admin())
        self.assertEqual(len(response.data['results']), 3)
        self.assertEqual(response.data['total_pages'], 4)

        response = self._get({'segment': utils.SEGMENT_AT_RISK}, self._admin())
        self.assertEqual(response.data['count'], 5)

    def test_endpoint_is_admin_only(self):
        customer = mock.Mock()
        customer.is_authenticated = True
        customer.is_active = True
        customer.role = Role.CUSTOMER
        response = self._get({}, customer)
        self.assertEqual(response.status_code, 403)


class RfmRefreshEndpointTests(TestCase):
    """POST recalculate (full) and incremental-refresh drive the engine."""

    def _admin(self):
        user = mock.Mock()
        user.is_authenticated = True
        user.is_active = True
        user.role = Role.ADMIN
        return user

    def _post(self, view_cls):
        request = APIRequestFactory().post('/api/analytics/rfm/x')
        force_authenticate(request, user=self._admin())
        response = view_cls.as_view()(request)
        response.render()
        return response

    def test_recalculate_starts_full_background_run(self):
        with mock.patch.object(engine, 'start_background_run',
                               return_value=(True, {'status': 'queued'})) as starter:
            response = self._post(views.RfmRecalculateView)
        self.assertEqual(response.status_code, 202)
        starter.assert_called_once_with(full=True)

    def test_incremental_noop_when_source_unchanged(self):
        with mock.patch.object(engine, 'source_changed_since_last_run',
                               return_value=False):
            response = self._post(views.RfmIncrementalRefreshView)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], 'up_to_date')

    def test_incremental_starts_refresh_when_source_changed(self):
        with mock.patch.object(engine, 'source_changed_since_last_run',
                               return_value=True), \
             mock.patch.object(engine, 'start_background_run',
                               return_value=(True, {'status': 'queued'})) as starter:
            response = self._post(views.RfmIncrementalRefreshView)
        self.assertEqual(response.status_code, 202)
        starter.assert_called_once_with(full=False)

    def test_recalculate_conflict_when_already_running(self):
        with mock.patch.object(engine, 'start_background_run',
                               return_value=(False, {'status': 'running'})):
            response = self._post(views.RfmRecalculateView)
        self.assertEqual(response.status_code, 409)


class KMeansClusteringTests(TestCase):
    """K-Means++ (k=4) over the persisted RFM values, without touching CLV's
    inputs. Runs on the SQLite test backend against `rfm_customer_segments`."""

    def setUp(self):
        cache_manager.cache.clear()
        CustomerSegment.objects.all().delete()
        RfmAnalysisState.objects.all().delete()
        KmeansRunState.objects.all().delete()
        self.admin = _admin_user()
        self.customer = _customer_user()
        self._seed_four_groups()

    def _seed_four_groups(self):
        # Four well-separated RFM groups so K-Means genuinely finds four
        # clusters and the profile mapping has a clear, mutually-exclusive
        # answer for each spending / frequency / dormancy label:
        #   High      - by far the highest Monetary (top average spend)
        #   Frequent  - by far the highest Frequency (repeat buyers)
        #   Moderate  - the middle residual on all three dimensions
        #   At Risk   - the least recent (most dormant) group
        groups = {
            'high': dict(recency=10, freq=8, money=9000),
            'frequent': dict(recency=8, freq=25, money=3000),
            'moderate': dict(recency=20, freq=5, money=1500),
            'atrisk': dict(recency=320, freq=4, money=1800),
        }
        records = []
        counter = 0
        for name, g in groups.items():
            for i in range(60):
                counter += 1
                records.append({
                    'customer_id': f'C{counter:04d}',
                    # A rule-based segment (irrelevant to clustering) so the
                    # stored row looks like a real completed RFM result.
                    'segment': utils.SEGMENT_LOYAL,
                    'tags': [],
                    'monetary': g['money'] + (i % 7) * (g['money'] * 0.01),
                    'recency_days': g['recency'] + (i % 5),
                    'frequency': g['freq'] + (i % 3),
                    'r_score': 3, 'f_score': 3, 'm_score': 3,
                    'first_purchase_date': '2024-01-01',
                    'last_purchase_date': '2026-01-01',
                })
        segment_store.store_records(records, version=1)

    def _original_metrics(self):
        return {r.customer_id: (r.recency, r.frequency, r.monetary)
                for r in CustomerSegment.objects.all()}

    def test_four_clusters_requested_and_all_buyers_assigned(self):
        result = clustering.run_clustering(save=True)
        self.assertTrue(result['available'])
        self.assertEqual(result['requested_clusters'], 4)
        self.assertEqual(result['effective_clusters'], 4)
        self.assertEqual(len(result['clusters']), 4)

        total = sum(c['customer_count'] for c in result['clusters'])
        self.assertEqual(total, CustomerSegment.objects.count())
        # Every buyer has both a cluster id and a mapped category.
        self.assertEqual(
            CustomerSegment.objects.filter(
                kmeans_cluster_id__isnull=True).count(), 0)
        self.assertEqual(
            CustomerSegment.objects.exclude(
                kmeans_category='').count(), CustomerSegment.objects.count())

    def test_scaler_only_touches_rfm_and_originals_are_preserved(self):
        before = self._original_metrics()
        clustering.run_clustering(save=True)
        after = self._original_metrics()
        # Original Recency / Frequency / Monetary are byte-for-byte unchanged.
        self.assertEqual(before, after)
        # Scaling used exactly the three RFM features (never CLV).
        self.assertEqual(len(clustering.load_rfm_dataset()[1][0]), 3)

    def test_mapping_is_from_profiles_not_cluster_id(self):
        result = clustering.run_clustering(save=True)
        by_cat = {c['category']: c for c in result['clusters']}
        self.assertEqual(set(by_cat), set(utils.KMEANS_CATEGORIES))
        # Business interpretation holds regardless of which numeric id K-Means
        # happened to hand out: At Risk is the most dormant, High Spending the
        # top-spending and Frequent Buyers the most frequent group, and the
        # frequent cluster is genuinely recent compared with the dormant one.
        self.assertEqual(
            by_cat[utils.KMEANS_CATEGORY_AT_RISK]['avg_recency'],
            max(c['avg_recency'] for c in result['clusters']))
        self.assertEqual(
            by_cat[utils.KMEANS_CATEGORY_HIGH_SPENDING]['avg_monetary'],
            max(c['avg_monetary'] for c in result['clusters']))
        self.assertEqual(
            by_cat[utils.KMEANS_CATEGORY_FREQUENT_BUYERS]['avg_frequency'],
            max(c['avg_frequency'] for c in result['clusters']))
        self.assertLess(
            by_cat[utils.KMEANS_CATEGORY_FREQUENT_BUYERS]['avg_recency'],
            by_cat[utils.KMEANS_CATEGORY_AT_RISK]['avg_recency'])

    def test_rerun_updates_rows_without_duplicates(self):
        clustering.run_clustering(save=True)
        count_first = CustomerSegment.objects.count()
        first = {r.customer_id: (r.kmeans_cluster_id, r.kmeans_category)
                 for r in CustomerSegment.objects.all()}

        clustering.run_clustering(save=True)   # same seeded algorithm
        count_second = CustomerSegment.objects.count()
        second = {r.customer_id: (r.kmeans_cluster_id, r.kmeans_category)
                  for r in CustomerSegment.objects.all()}

        self.assertEqual(count_first, count_second)   # no duplicate customers
        self.assertEqual(first, second)               # stable, seeded result

    def test_rule_based_segment_and_rfm_store_are_untouched(self):
        # Clustering must not disturb the six-way segment CLV depends on.
        clustering.run_clustering(save=True)
        for row in CustomerSegment.objects.all():
            self.assertEqual(row.segment, utils.SEGMENT_LOYAL)
            self.assertIsNotNone(row.monetary)

    def test_dry_run_persists_nothing(self):
        result = clustering.run_clustering(save=False)
        self.assertTrue(result['available'])
        self.assertEqual(
            CustomerSegment.objects.filter(
                kmeans_cluster_id__isnull=True).count(),
            CustomerSegment.objects.count())

    def test_empty_population_is_handled(self):
        CustomerSegment.objects.all().delete()
        result = clustering.run_clustering(save=True)
        self.assertFalse(result['available'])
        self.assertEqual(result['clustered'], 0)

    def test_summary_reads_stored_state_after_restart(self):
        clustering.run_clustering(save=True)
        summary = clustering.clustering_summary()
        self.assertTrue(summary['available'])
        self.assertEqual(len(summary['clusters']), 4)
        self.assertEqual(
            sum(c['customer_count'] for c in summary['clusters']),
            CustomerSegment.objects.count())

    def test_clusters_endpoint_is_admin_only_and_serves_summary(self):
        clustering.run_clustering(save=True)

        def _get(user):
            request = APIRequestFactory().get('/api/analytics/rfm/clusters')
            force_authenticate(request, user=user)
            response = views.RfmClustersView.as_view()(request)
            response.render()
            return response

        customer = mock.Mock()
        customer.is_authenticated = True
        customer.is_active = True
        customer.role = Role.CUSTOMER
        self.assertEqual(_get(customer).status_code, 403)

        admin = mock.Mock()
        admin.is_authenticated = True
        admin.is_active = True
        admin.role = Role.ADMIN
        response = _get(admin)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['available'])
        self.assertEqual(len(response.data['clusters']), 4)

    # ---- run state, percentages and the cluster customer list ----

    def _admin_get(self, view, params):
        request = APIRequestFactory().get('/api/analytics/rfm/clusters/customers', params)
        force_authenticate(request, user=self.admin)
        response = view.as_view()(request)
        response.render()
        return response

    def test_run_state_records_the_latest_clustering_run(self):
        clustering.run_clustering(save=True)
        state = KmeansRunState.objects.get(pk=KmeansRunState.SINGLETON_ID)
        # Which RFM version was clustered, when, and how each cluster was mapped.
        self.assertEqual(state.rfm_version, 1)
        self.assertIsNotNone(state.completed_at)
        self.assertEqual(state.n_clusters, 4)
        self.assertEqual(state.clustered, CustomerSegment.objects.count())
        self.assertEqual({row['category'] for row in state.mapping},
                         set(utils.KMEANS_CATEGORIES))
        # The standardized values are bookkeeping only - never written per buyer.
        self.assertEqual(set(state.scaler), {'mean', 'scale'})
        self.assertEqual(len(state.scaler['mean']), 3)

    def test_dry_run_stores_no_run_state(self):
        clustering.run_clustering(save=False)
        self.assertFalse(KmeansRunState.objects.exists())

    def test_percentages_are_of_the_clustered_population(self):
        clustering.run_clustering(save=True)
        summary = clustering.clustering_summary()
        self.assertEqual(summary['total'], summary['clustered'])
        self.assertEqual(summary['clustered'], CustomerSegment.objects.count())
        # Four categories that add up to ~100% (rounding aside), because the
        # denominator is exactly the population that was clustered.
        self.assertAlmostEqual(sum(c['percent'] for c in summary['clusters']),
                               100, delta=1)
        self.assertEqual(summary['ambiguities'], [])
        self.assertTrue(all(c['supported'] for c in summary['clusters']))

    def test_unsupported_label_is_reported_instead_of_forced(self):
        # A population of pure one-time buyers: no cluster has any repeat habit,
        # so "Frequent Buyers" cannot be supported by any of them and must be
        # reported with the contradicting numbers rather than silently applied.
        # Clusters are separated by Recency and Monetary only (Frequency fixed).
        CustomerSegment.objects.all().delete()
        groups = {
            'a': dict(recency=4, money=9000),
            'b': dict(recency=15, money=4000),
            'c': dict(recency=80, money=1800),
            'd': dict(recency=300, money=500),
        }
        records = []
        counter = 0
        for _name, g in groups.items():
            for i in range(60):
                counter += 1
                records.append({
                    'customer_id': f'N{counter:04d}',
                    'segment': utils.SEGMENT_AT_RISK,
                    'tags': [],
                    'monetary': g['money'] + (i % 7) * 10,
                    'recency_days': g['recency'] + (i % 5),
                    'frequency': 1,  # every buyer is a one-time purchaser
                    'r_score': 2, 'f_score': 4, 'm_score': 4,
                    'first_purchase_date': '2023-01-01',
                    'last_purchase_date': '2024-06-01',
                })
        segment_store.store_records(records, version=2)

        result = clustering.run_clustering(save=True)
        by_cat = {c['category']: c for c in result['clusters']}
        frequent = by_cat[utils.KMEANS_CATEGORY_FREQUENT_BUYERS]
        self.assertFalse(frequent['supported'])
        self.assertTrue(frequent['cautions'])
        self.assertTrue(any(utils.KMEANS_CATEGORY_FREQUENT_BUYERS in text
                            for text in result['ambiguities']))
        # The label is still carried by a real cluster (the buyer is never
        # uncounted); only its trustworthiness is reported.
        self.assertEqual(sum(c['customer_count'] for c in result['clusters']),
                         len(records))

    def test_cluster_customers_endpoint_returns_that_cluster_members(self):
        result = clustering.run_clustering(save=True)
        for cluster in result['clusters']:
            with self.subTest(category=cluster['category']):
                response = self._admin_get(views.RfmClusterCustomersView, {
                    'category': cluster['category'],
                    'cluster_id': cluster['cluster_id'],
                    'page_size': 5,
                })
                self.assertEqual(response.status_code, 200)
                # The list agrees with the bar exactly: same category, same
                # numeric cluster, same total.
                self.assertEqual(response.data['count'], cluster['customer_count'])
                self.assertEqual(response.data['cluster_id'], cluster['cluster_id'])
                self.assertEqual(len(response.data['results']), 5)
                for row in response.data['results']:
                    self.assertEqual(row['category'], cluster['category'])
                    self.assertEqual(row['cluster_id'], cluster['cluster_id'])
                    self.assertTrue(row['customer_id'])
                    # The displayed R/F/M are that exact buyer's ORIGINAL,
                    # unscaled persisted values - never another cluster's.
                    source = CustomerSegment.objects.get(
                        customer_id=row['customer_id'])
                    self.assertEqual(
                        (source.kmeans_cluster_id, source.kmeans_category),
                        (cluster['cluster_id'], cluster['category']))
                    self.assertEqual(row['recency'], source.recency)
                    self.assertEqual(row['frequency'], source.frequency)
                    self.assertEqual(
                        row['monetary'], float(source.monetary))

    def test_cluster_pages_never_repeat_or_skip_a_customer(self):
        result = clustering.run_clustering(save=True)
        cluster = result['clusters'][0]
        size = 7
        seen = []
        pages = (cluster['customer_count'] + size - 1) // size
        for page in range(1, pages + 1):
            response = self._admin_get(views.RfmClusterCustomersView, {
                'category': cluster['category'],
                'cluster_id': cluster['cluster_id'],
                'page': page, 'page_size': size,
            })
            self.assertEqual(response.data['total_pages'], pages)
            seen += [r['customer_id'] for r in response.data['results']]
        self.assertEqual(len(seen), len(set(seen)))
        self.assertEqual(
            set(seen),
            set(CustomerSegment.objects.filter(
                kmeans_category=cluster['category'],
                kmeans_cluster_id=cluster['cluster_id'],
            ).values_list('customer_id', flat=True)))

    def test_cluster_customer_search_and_unknown_category(self):
        result = clustering.run_clustering(save=True)
        cluster = result['clusters'][0]
        first = self._admin_get(views.RfmClusterCustomersView, {
            'category': cluster['category'], 'cluster_id': cluster['cluster_id'],
        })
        wanted = first.data['results'][0]['customer_id']
        found = self._admin_get(views.RfmClusterCustomersView, {
            'category': cluster['category'], 'search': wanted,
        })
        self.assertEqual(found.data['count'], 1)
        self.assertEqual(found.data['results'][0]['customer_id'], wanted)

        missing = self._admin_get(views.RfmClusterCustomersView, {'category': 'Champions'})
        self.assertEqual(missing.status_code, 404)
        bad = self._admin_get(views.RfmClusterCustomersView, {
            'category': utils.KMEANS_CATEGORY_HIGH_SPENDING, 'cluster_id': 'not-an-int'})
        self.assertEqual(bad.status_code, 404)

    def test_cluster_customers_are_admin_only(self):
        clustering.run_clustering(save=True)
        request = APIRequestFactory().get('/api/analytics/rfm/clusters/customers',
                                          {'category': utils.KMEANS_CATEGORY_HIGH_SPENDING})
        force_authenticate(request, user=self.customer)
        response = views.RfmClusterCustomersView.as_view()(request)
        self.assertEqual(response.status_code, 403)

    def test_rerun_relabels_in_place_and_the_list_follows(self):
        clustering.run_clustering(save=True)
        rows_before = CustomerSegment.objects.count()
        result = clustering.run_clustering(save=True)
        self.assertEqual(CustomerSegment.objects.count(), rows_before)
        self.assertEqual(KmeansRunState.objects.count(), 1)

        summary = clustering.clustering_summary()
        by_cat = {c['category']: c for c in summary['clusters']}
        for cluster in result['clusters']:
            response = self._admin_get(views.RfmClusterCustomersView, {
                'category': cluster['category'],
                'cluster_id': cluster['cluster_id'],
                'page_size': 1,
            })
            self.assertEqual(response.data['count'],
                             by_cat[cluster['category']]['customer_count'])

    def test_rerun_after_a_new_buyer_is_added_relabels_without_duplicates(self):
        clustering.run_clustering(save=True)
        # A later RFM run adds a buyer; re-clustering must cover them too and
        # still hold exactly one row per customer.
        segment_store.store_records([{
            'customer_id': 'ZZ9999', 'segment': utils.SEGMENT_NEW, 'tags': [],
            'monetary': 250, 'recency_days': 6, 'frequency': 1,
            'r_score': 5, 'f_score': 1, 'm_score': 1,
            'first_purchase_date': '2026-01-01', 'last_purchase_date': '2026-01-01',
        }], version=2)
        self.assertEqual(
            CustomerSegment.objects.filter(kmeans_cluster_id__isnull=True).count(), 1)

        result = clustering.run_clustering(save=True)
        self.assertEqual(result['clustered'], CustomerSegment.objects.count())
        self.assertEqual(
            CustomerSegment.objects.filter(kmeans_cluster_id__isnull=True).count(), 0)
        self.assertEqual(
            sum(c['customer_count'] for c in clustering.clustering_summary()['clusters']),
            CustomerSegment.objects.count())

    def test_summary_payload_only_carries_the_kmeans_segmentation(self):
        # The RFM page is segmented by K-Means only: the payload that feeds it
        # reports the four clusters and no old six-category distribution.
        clustering.run_clustering(save=True)
        payload = clustering.clustering_summary()
        self.assertEqual({c['category'] for c in payload['clusters']},
                         set(utils.KMEANS_CATEGORIES))
        self.assertNotIn('segments', payload)

    def _corrupt_to_legacy_labels(self):
        # Simulate a run persisted before the current four-category vocabulary:
        # rewrite every stored label to a legacy name in BOTH the buyer rows and
        # the run-state mapping, leaving the numeric cluster ids untouched.
        CustomerSegment.objects.exclude(kmeans_cluster_id__isnull=True).update(
            kmeans_category='Loyal Customer')
        state = KmeansRunState.objects.get(pk=KmeansRunState.SINGLETON_ID)
        state.mapping = [dict(row, category='Loyal Customer')
                         for row in state.mapping]
        state.unsupported_categories = []
        state.save()
        cache_manager.cache.clear()   # drop the memo so reads see the legacy run

    def test_relabel_refreshes_legacy_labels_without_a_rerun(self):
        clustering.run_clustering(save=True)
        fresh = {r.customer_id: (r.kmeans_cluster_id, r.kmeans_category)
                 for r in CustomerSegment.objects.all()}
        self._corrupt_to_legacy_labels()
        self.assertFalse(clustering.labels_are_current(clustering.get_run_state()))

        result = clustering.relabel_stored_run()
        self.assertIsNotNone(result)
        self.assertTrue(clustering.labels_are_current(clustering.get_run_state()))

        after = {r.customer_id: (r.kmeans_cluster_id, r.kmeans_category)
                 for r in CustomerSegment.objects.all()}
        # No buyer moved cluster (ids identical) and the refreshed labels equal
        # what the fresh clustering run produced.
        self.assertEqual({cid: v[0] for cid, v in after.items()},
                         {cid: v[0] for cid, v in fresh.items()})
        self.assertEqual({cid: v[1] for cid, v in after.items()},
                         {cid: v[1] for cid, v in fresh.items()})
        # Same population, same four categories, counts preserved.
        summary = clustering.clustering_summary()
        self.assertEqual(sum(c['customer_count'] for c in summary['clusters']),
                         len(fresh))
        self.assertEqual({c['category'] for c in summary['clusters']},
                         set(utils.KMEANS_CATEGORIES))

    def test_reconcile_heals_a_legacy_run_once_then_is_a_noop(self):
        clustering.run_clustering(save=True)
        self._corrupt_to_legacy_labels()
        # The read-path guard heals the legacy persisted labels ...
        self.assertTrue(clustering.reconcile_stored_labels())
        # ... and a second call (already current) changes nothing.
        self.assertFalse(clustering.reconcile_stored_labels())
        self.assertTrue(clustering.labels_are_current(clustering.get_run_state()))


class CampaignClusterTargetingTests(TestCase):
    """Personalized coupon campaigns aimed at the four K-Means clusters.

    Covers the whole flow the Campaign page drives: choosing groups from the
    persisted clustering, publishing (which materializes the coupon assignments),
    customer visibility, checkout eligibility and redemption, and the guarantee
    that neither an older published campaign nor a future clustering run is
    disturbed.
    """

    def setUp(self):
        cache_manager.cache.clear()
        cache_manager._index_memo.clear()
        CampaignAudience.objects.all().delete()
        CampaignRedemption.objects.all().delete()
        Campaign.objects.all().delete()
        ClusteringRun.objects.all().delete()
        KmeansRunState.objects.all().delete()
        CustomerSegment.objects.all().delete()
        RfmAnalysisState.objects.all().delete()
        self.admin = _admin_user()
        self.now = timezone.now()
        # A real four-cluster K-Means++ run over persisted RFM buyers, so every
        # campaign below targets actual cluster assignments.
        self._seed_four_groups()
        self.run_result = clustering.run_clustering(save=True)
        self.clusters = sorted(self.run_result['clusters'],
                               key=lambda c: c['cluster_id'])

    def _seed_four_groups(self):
        groups = {
            'high': dict(recency=10, freq=8, money=9000),
            'frequent': dict(recency=8, freq=25, money=3000),
            'moderate': dict(recency=20, freq=5, money=1500),
            'atrisk': dict(recency=320, freq=4, money=1800),
        }
        records = []
        counter = 0
        for _name, g in groups.items():
            for i in range(25):
                counter += 1
                records.append({
                    'customer_id': f'C{counter:04d}',
                    'segment': utils.SEGMENT_LOYAL,
                    'tags': [],
                    'monetary': g['money'] + (i % 7) * (g['money'] * 0.01),
                    'recency_days': g['recency'] + (i % 5),
                    'frequency': g['freq'] + (i % 3),
                    'r_score': 3, 'f_score': 3, 'm_score': 3,
                    'first_purchase_date': '2024-01-01',
                    'last_purchase_date': '2026-01-01',
                })
        segment_store.store_records(records, version=1)

    def _members(self, cluster_id):
        return set(CustomerSegment.objects.filter(
            kmeans_cluster_id=cluster_id).values_list('customer_id', flat=True))

    def _cart(self, value):
        """Server-side cart lines worth exactly `value` (the checkout sends them)."""
        return [{'product_id': 'P1', 'name': 'Kurti', 'category': 'Ethnic',
                 'quantity': int(value) // 500, 'unit_price': 500.0}]

    def _draft(self, cluster_ids, name='Cluster Offer', code=None, **overrides):
        payload = {
            'name': name,
            'coupon_code': code or name.upper().replace(' ', '_'),
            'offer_category': OfferCategory.DISCOUNT,
            'discount_rule': {'type': 'PERCENTAGE', 'percent': 15},
            'targeting_mode': TargetingMode.KMEANS,
            'target_cluster_ids': cluster_ids,
            'start_date': self.now - timedelta(hours=1),
            'end_date': self.now + timedelta(days=7),
            'min_order_amount': 0,
            'usage_type': UsageType.UNLIMITED,
        }
        payload.update(overrides)
        serializer = CampaignSerializer(data=payload)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        return serializer.save()

    def _set_status(self, campaign, status):
        request = APIRequestFactory().post(
            f'/api/campaigns/{campaign.campaign_id}/status/',
            {'status': status}, format='json')
        force_authenticate(request, user=self.admin)
        return views.CampaignStatusView.as_view()(request,
                                                  campaign_id=campaign.campaign_id)

    def _published(self, cluster_ids, **overrides):
        campaign = self._draft(cluster_ids, **overrides)
        response = self._set_status(campaign, 'PUBLISHED')
        self.assertEqual(response.status_code, 200, response.data)
        campaign.refresh_from_db()
        return campaign, response

    # ---- the audience the admin can choose from ----

    def test_cluster_options_are_the_persisted_run_with_real_counts(self):
        options = cluster_targeting.available_clusters()
        self.assertTrue(options['available'])
        self.assertIsNotNone(options['run'])
        self.assertEqual(
            {c['cluster_id'] for c in options['clusters']},
            {c['cluster_id'] for c in self.clusters})
        for row in options['clusters']:
            # Label comes from the run mapping, never assumed from the id, and
            # the count is the buyers actually stored in that cluster.
            self.assertIn(row['category'], utils.KMEANS_CATEGORIES)
            self.assertEqual(row['customer_count'],
                             len(self._members(row['cluster_id'])))
        self.assertEqual(sum(c['customer_count'] for c in options['clusters']),
                         CustomerSegment.objects.count())

    def test_serializer_stores_clusters_labels_and_the_run_reference(self):
        campaign = self._draft([self.clusters[0]['cluster_id'],
                               self.clusters[1]['cluster_id']])
        self.assertEqual(campaign.targeting_mode, TargetingMode.KMEANS)
        self.assertEqual(campaign.target_cluster_ids,
                         sorted([self.clusters[0]['cluster_id'],
                                 self.clusters[1]['cluster_id']]))
        self.assertEqual(
            set(campaign.target_cluster_labels),
            {self.clusters[0]['category'], self.clusters[1]['category']})
        # The run it was chosen from, and none of the old segment targeting.
        self.assertEqual(campaign.clustering_run_id,
                         ClusteringRun.objects.order_by('-run_id').first().run_id)
        self.assertEqual(campaign.target_segments, [])
        self.assertEqual(campaign.target_tags, [])

    def test_unknown_cluster_is_rejected(self):
        serializer = CampaignSerializer(data={
            'name': 'Bad', 'coupon_code': 'BAD1',
            'offer_category': OfferCategory.DISCOUNT,
            'discount_rule': {'type': 'PERCENTAGE', 'percent': 10},
            'targeting_mode': TargetingMode.KMEANS,
            'target_cluster_ids': [99],
            'start_date': self.now,
            'end_date': self.now + timedelta(days=1),
            'usage_type': UsageType.UNLIMITED,
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn('target_cluster_ids', serializer.errors)

    # ---- publishing: audience resolution and coupon assignment ----

    def test_publish_issues_exactly_to_the_selected_cluster(self):
        for cluster in self.clusters:
            with self.subTest(cluster=cluster['category']):
                Campaign.objects.all().delete()
                campaign, response = self._published(
                    [cluster['cluster_id']],
                    name=f"Offer {cluster['category']}",
                    code=f"CLUSTER_{cluster['cluster_id']}")
                assigned = set(CampaignAudience.objects.filter(
                    campaign=campaign).values_list('customer_id', flat=True))
                # Exactly this cluster's customers - nobody else's.
                self.assertEqual(assigned, self._members(cluster['cluster_id']))
                audience = response.data['audience']
                self.assertEqual(audience['targeted'], len(assigned))
                self.assertEqual(audience['coupons_issued'], len(assigned))
                self.assertEqual(audience['newly_assigned'], len(assigned))
                self.assertEqual(response.data['coupons_issued'], len(assigned))

    def test_multiple_clusters_target_the_union_of_their_members(self):
        first, second = self.clusters[0], self.clusters[1]
        campaign, response = self._published(
            [first['cluster_id'], second['cluster_id']])
        assigned = set(CampaignAudience.objects.filter(
            campaign=campaign).values_list('customer_id', flat=True))
        self.assertEqual(assigned,
                         self._members(first['cluster_id'])
                         | self._members(second['cluster_id']))
        self.assertEqual(response.data['audience']['coupons_issued'], len(assigned))
        # A customer of an unselected cluster is not in the audience at all.
        outsider = next(iter(self._members(self.clusters[3]['cluster_id'])))
        self.assertNotIn(outsider, assigned)

    def test_no_duplicate_coupon_assignment(self):
        cluster = self.clusters[2]
        campaign, _ = self._published([cluster['cluster_id']])
        size = len(self._members(cluster['cluster_id']))
        # Publishing again (pause -> publish) and re-materializing add nothing.
        self._set_status(campaign, 'PAUSED')
        self._set_status(campaign, 'PUBLISHED')
        cluster_targeting.materialize_audience(campaign)
        self.assertEqual(CampaignAudience.objects.filter(
            campaign=campaign).count(), size)
        self.assertEqual(
            CampaignAudience.objects.filter(campaign=campaign).values_list(
                'customer_id', flat=True).distinct().count(), size)

    def test_publish_blocked_without_clusters_or_customers(self):
        campaign = self._draft([self.clusters[0]['cluster_id']])
        CustomerSegment.objects.update(kmeans_cluster_id=None, kmeans_category='')
        response = self._set_status(campaign, 'PUBLISHED')
        self.assertEqual(response.status_code, 400)
        campaign.refresh_from_db()
        self.assertEqual(campaign.status, CampaignStatus.DRAFT)

    # ---- customer visibility, eligibility and redemption ----

    def test_only_assigned_customers_see_and_can_use_the_coupon(self):
        cluster = self.clusters[0]
        campaign, _ = self._published([cluster['cluster_id']])
        member = next(iter(self._members(cluster['cluster_id'])))
        outsider = next(iter(self._members(self.clusters[1]['cluster_id'])))

        self.assertEqual(
            [o['coupon_code'] for o in personalization.eligible_offers(member)['offers']],
            [campaign.coupon_code])
        self.assertEqual(personalization.eligible_offers(outsider)['offers'], [])

        result = coupon_validation.validate_coupon(
            member, campaign.coupon_code, 2000, cart_lines=self._cart(2000))
        self.assertEqual(result['discount'], 300.0)      # 15% of 2000
        self.assertEqual(result['payable'], 1700.0)
        with self.assertRaises(ValidationError):
            coupon_validation.validate_coupon(
                outsider, campaign.coupon_code, 2000, cart_lines=self._cart(2000))

    def test_redemption_still_works_and_is_one_per_customer(self):
        cluster = self.clusters[1]
        campaign, _ = self._published([cluster['cluster_id']])
        member = next(iter(self._members(cluster['cluster_id'])))
        first = coupon_validation.validate_coupon(
            member, campaign.coupon_code, 1000, cart_lines=self._cart(1000))
        self.assertTrue(coupon_validation.redeem(
            campaign.campaign_id, member, 'ORD1', first['discount']))
        # Second use is refused, the offer is reported Used, and the coupon list
        # for that customer still shows it (history is never deleted).
        with self.assertRaises(ValidationError):
            coupon_validation.validate_coupon(
                member, campaign.coupon_code, 1000, cart_lines=self._cart(1000))
        offers = personalization.eligible_offers(member)['offers']
        self.assertEqual([o['status'] for o in offers], ['USED'])
        summary = campaign_audience.audience_summary(
            Campaign.objects.get(pk=campaign.campaign_id))
        self.assertEqual(summary['coupons_redeemed'], 1)
        self.assertEqual(summary['coupons_remaining'],
                         summary['coupons_issued'] - 1)

    def test_offer_rules_are_unchanged_for_cluster_campaigns(self):
        # Validity, minimum order, maximum discount and usage limits still apply.
        cluster = self.clusters[3]
        campaign, _ = self._published(
            [cluster['cluster_id']], min_order_amount=1500,
            max_discount=100, usage_type=UsageType.ONCE)
        member = next(iter(self._members(cluster['cluster_id'])))
        with self.assertRaises(ValidationError):
            coupon_validation.validate_coupon(
                member, campaign.coupon_code, 1000, cart_lines=self._cart(1000))
        result = coupon_validation.validate_coupon(
            member, campaign.coupon_code, 2000, cart_lines=self._cart(2000))
        self.assertEqual(result['discount'], 100.0)      # capped maximum
        coupon_validation.redeem(campaign.campaign_id, member, 'ORD9', 100)
        with self.assertRaises(ValidationError):
            coupon_validation.validate_coupon(
                member, campaign.coupon_code, 2000, cart_lines=self._cart(2000))

    def test_draft_audience_can_be_updated_safely(self):
        campaign = self._draft([self.clusters[0]['cluster_id']])
        self.assertEqual(CampaignAudience.objects.filter(campaign=campaign).count(), 0)
        request = APIRequestFactory().put(
            f'/api/campaigns/{campaign.campaign_id}/',
            {'target_cluster_ids': [self.clusters[1]['cluster_id']]}, format='json')
        force_authenticate(request, user=self.admin)
        response = views.CampaignDetailView.as_view()(request,
                                                      campaign_id=campaign.campaign_id)
        self.assertEqual(response.status_code, 200, response.data)
        campaign.refresh_from_db()
        self.assertEqual(campaign.target_cluster_ids,
                         [self.clusters[1]['cluster_id']])
        self.assertEqual(set(campaign.target_cluster_labels),
                         {self.clusters[1]['category']})
        # Still a draft, still no coupons issued.
        self.assertEqual(campaign.status, CampaignStatus.DRAFT)
        self.assertEqual(CampaignAudience.objects.filter(campaign=campaign).count(), 0)

    # ---- consistency with clustering runs ----

    def test_new_campaign_uses_the_latest_completed_run(self):
        first_run = ClusteringRun.objects.order_by('-run_id').first()
        # A future clustering run ... and a campaign created after it.
        clustering.run_clustering(save=True)
        second_run = ClusteringRun.objects.order_by('-run_id').first()
        self.assertNotEqual(first_run.run_id, second_run.run_id)
        campaign = self._draft([self.clusters[0]['cluster_id']])
        self.assertEqual(campaign.clustering_run_id, second_run.run_id)
        # And the options the page offers name that same run.
        self.assertEqual(cluster_targeting.available_clusters()['run']['run_id'],
                         second_run.run_id)

    def test_published_audience_does_not_move_with_a_new_clustering_run(self):
        cluster = self.clusters[0]
        other = self.clusters[1]
        campaign, _ = self._published([cluster['cluster_id']])
        assigned_before = set(CampaignAudience.objects.filter(
            campaign=campaign).values_list('customer_id', flat=True))
        moved = sorted(assigned_before)[:len(assigned_before) // 2]

        # A future clustering run reassigns half of the campaign's buyers to
        # another cluster, and moves two other buyers into the targeted cluster
        # - exactly what `clustering._persist_labels` writes.
        CustomerSegment.objects.filter(customer_id__in=moved).update(
            kmeans_cluster_id=other['cluster_id'],
            kmeans_category=other['category'])
        joiners = sorted(set(self._members(other['cluster_id']))
                         - assigned_before)[:2]
        CustomerSegment.objects.filter(customer_id__in=joiners).update(
            kmeans_cluster_id=cluster['cluster_id'],
            kmeans_category=cluster['category'])

        # The published campaign keeps exactly the customers it issued to: the
        # audience did not follow the new assignment ...
        self.assertEqual(
            set(CampaignAudience.objects.filter(campaign=campaign)
                .values_list('customer_id', flat=True)), assigned_before)
        # ... and those buyers keep seeing and using the coupon.
        mover = moved[0]
        self.assertIn(campaign.coupon_code,
                      [o['coupon_code']
                       for o in personalization.eligible_offers(mover)['offers']])
        result = coupon_validation.validate_coupon(
            mover, campaign.coupon_code, 1000, cart_lines=self._cart(1000))
        self.assertEqual(result['discount'], 150.0)
        # A buyer who only now sits in the targeted cluster was never issued a
        # coupon, so the campaign stays invisible to them.
        joiner = joiners[0]
        self.assertIn(joiner, self._members(cluster['cluster_id']))
        self.assertNotIn(joiner, assigned_before)
        self.assertEqual(
            personalization.eligible_offers(joiner)['offers'], [])
        with self.assertRaises(ValidationError):
            coupon_validation.validate_coupon(
                joiner, campaign.coupon_code, 1000, cart_lines=self._cart(1000))
        # The campaign still names the run it was published on.
        campaign.refresh_from_db()
        self.assertEqual(campaign.clustering_run_id,
                         ClusteringRun.objects.order_by('run_id').first().run_id)

    def test_a_draft_audience_follows_the_latest_run_when_published(self):
        cluster = self.clusters[0]
        campaign = self._draft([cluster['cluster_id']])
        run_at_authoring = campaign.clustering_run_id
        # A re-clustering (a real one, over changed metrics) before publishing:
        # the draft has issued no coupons yet, so publishing resolves the cluster
        # from the assignments the latest run persisted.
        CustomerSegment.objects.filter(
            kmeans_cluster_id=cluster['cluster_id']).update(
            recency=120, frequency=13, monetary=5200)
        new_run = clustering.run_clustering(save=True)
        self.assertTrue(new_run['available'])

        response = self._set_status(campaign, 'PUBLISHED')
        self.assertEqual(response.status_code, 200, response.data)
        issued = set(CampaignAudience.objects.filter(campaign=campaign)
                     .values_list('customer_id', flat=True))
        # Exactly the customers now in the selected cluster, one coupon each.
        self.assertEqual(issued, self._members(cluster['cluster_id']))
        self.assertEqual(
            CampaignAudience.objects.filter(campaign=campaign).count(), len(issued))
        # The campaign keeps naming the run the admin actually selected from.
        campaign.refresh_from_db()
        self.assertEqual(campaign.clustering_run_id, run_at_authoring)

    def test_stored_labels_survive_a_relabel_of_the_run(self):
        # The persisted labels of a run may be re-derived from its profiles; the
        # campaign's own snapshot of what it targeted is never rewritten.
        cluster = self.clusters[2]
        campaign, _ = self._published([cluster['cluster_id']])
        labels_before = list(campaign.target_cluster_labels)
        state = KmeansRunState.objects.get(pk=KmeansRunState.SINGLETON_ID)
        state.mapping = [dict(row, category='Loyal Customer')
                         for row in state.mapping]
        state.save()
        cache_manager.cache.clear()
        clustering.relabel_stored_run()
        campaign.refresh_from_db()
        self.assertEqual(campaign.target_cluster_labels, labels_before)

    # ---- backward compatibility ----

    def test_legacy_segment_campaign_keeps_working(self):
        allow_legacy_campaigns(self)
        campaign = self._legacy_campaign()
        member = 'C0001'
        offers = personalization.eligible_offers(member)['offers']
        self.assertEqual([o['coupon_code'] for o in offers], ['LEGACY20'])
        self.assertEqual(offers[0]['targeting_mode'], TargetingMode.LEGACY_RFM)
        # Its audience is still the live segment count, not a cluster count.
        self.assertEqual(
            campaign_audience.campaign_audience_count(campaign),
            campaign_audience.audience_count(campaign.target_segments,
                                             campaign.target_tags))
        self.assertEqual(CampaignAudience.objects.filter(
            campaign=campaign).count(), 0)
        result = coupon_validation.validate_coupon(member, 'LEGACY20', 1000)
        self.assertEqual(result['discount'], 200.0)

    def _legacy_campaign(self):
        records = [{'customer_id': 'C0001', 'segment': utils.SEGMENT_CHAMPIONS,
                    'tags': [utils.TAG_BIG_SPENDER], 'recency_days': 1,
                    'frequency': 9, 'monetary': 900}]
        cache_manager.publish_snapshot({
            'status': 'completed', 'analysis_date': self.now.date().isoformat(),
            'totals': {}, 'big_spender_count': 1, 'buyer_count': 1,
            'segment_counts': {utils.SEGMENT_CHAMPIONS: 1},
            'customer_ids': ['C0001'], 'records': records, 'compute_ms': 1.0,
        })
        # The same buyer also exists in the persisted clustering, so a legacy
        # campaign and a cluster campaign can be compared on one population.
        CustomerSegment.objects.update_or_create(
            customer_id='C0001',
            defaults={'segment': utils.SEGMENT_CHAMPIONS,
                      'tags': [utils.TAG_BIG_SPENDER], 'recency': 1,
                      'frequency': 9, 'monetary': 900, 'r_score': 5,
                      'f_score': 5, 'm_score': 5, 'computed_at': self.now,
                      'version': 1})
        return Campaign.objects.create(
            name='Champions: VIP 20 OFF', coupon_code='LEGACY20',
            discount_type=DiscountType.PERCENTAGE, discount_value=20,
            target_segments=[utils.SEGMENT_CHAMPIONS], target_tags=[],
            start_date=self.now - timedelta(days=1),
            end_date=self.now + timedelta(days=1),
            min_order_amount=0, usage_type=UsageType.UNLIMITED,
            status=CampaignStatus.PUBLISHED,
        )

    def test_legacy_published_campaign_cannot_be_reinterpreted(self):
        campaign = self._legacy_campaign()
        serializer = CampaignSerializer(
            campaign,
            data={'targeting_mode': TargetingMode.KMEANS,
                  'target_cluster_ids': [self.clusters[0]['cluster_id']]},
            partial=True)
        self.assertFalse(serializer.is_valid())
        self.assertIn('targeting_mode', serializer.errors)

    def test_draft_legacy_campaign_can_be_converted(self):
        campaign = self._legacy_campaign()
        campaign.status = CampaignStatus.DRAFT
        campaign.save()
        serializer = CampaignSerializer(
            campaign,
            data={'targeting_mode': TargetingMode.KMEANS,
                  'target_cluster_ids': [self.clusters[0]['cluster_id']]},
            partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        saved = serializer.save()
        self.assertEqual(saved.targeting_mode, TargetingMode.KMEANS)
        self.assertEqual(saved.target_segments, [])
        self.assertEqual(saved.target_cluster_ids,
                         [self.clusters[0]['cluster_id']])

    def test_redemption_history_of_an_old_campaign_is_untouched(self):
        campaign = self._legacy_campaign()
        CampaignRedemption.objects.create(
            campaign=campaign, customer_id='C0001', order_id='OLD1',
            discount_applied=200)
        self._published([self.clusters[0]['cluster_id']])
        self.assertEqual(CampaignRedemption.objects.filter(
            campaign=campaign).count(), 1)
        self.assertEqual(Campaign.objects.get(pk=campaign.pk).target_segments,
                         [utils.SEGMENT_CHAMPIONS])

    # ---- admin list and detail payloads ----

    def test_list_reports_groups_and_coupon_figures(self):
        cluster = self.clusters[0]
        campaign, _ = self._published([cluster['cluster_id']])
        member = next(iter(self._members(cluster['cluster_id'])))
        result = coupon_validation.validate_coupon(
            member, campaign.coupon_code, 1000, cart_lines=self._cart(1000))
        coupon_validation.redeem(campaign.campaign_id, member, 'ORD7',
                                 result['discount'])

        request = APIRequestFactory().get('/api/campaigns/', {})
        force_authenticate(request, user=self.admin)
        response = views.CampaignListCreateView.as_view()(request)
        response.render()
        self.assertEqual(response.status_code, 200)
        row = response.data['results'][0]
        self.assertEqual(row['targeting_mode'], TargetingMode.KMEANS)
        self.assertEqual(row['target_cluster_labels'], [cluster['category']])
        size = len(self._members(cluster['cluster_id']))
        self.assertEqual(row['eligible_audience_count'], size)
        self.assertEqual(row['coupons_issued'], size)
        self.assertEqual(row['coupons_redeemed'], 1)
        self.assertEqual(row['coupons_remaining'], size - 1)

    def test_list_can_be_filtered_by_customer_group(self):
        self._published([self.clusters[0]['cluster_id']], name='A', code='A1')
        self._published([self.clusters[1]['cluster_id']], name='B', code='B1')
        wanted = self.clusters[1]['category']
        request = APIRequestFactory().get('/api/campaigns/', {'cluster': wanted})
        force_authenticate(request, user=self.admin)
        response = views.CampaignListCreateView.as_view()(request)
        response.render()
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['target_cluster_labels'],
                         [wanted])

    def test_cluster_options_endpoint_is_admin_only(self):
        def _get(user):
            request = APIRequestFactory().get('/api/campaigns/clusters/')
            force_authenticate(request, user=user)
            response = views.CampaignClusterOptionsView.as_view()(request)
            response.render()
            return response

        self.assertEqual(_get(_customer_user()).status_code, 403)
        response = _get(self.admin)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['clusters']), 4)
        self.assertEqual(
            {c['category'] for c in response.data['clusters']},
            {c['category'] for c in self.clusters})

    def test_detail_shows_clusters_run_and_coupons(self):
        cluster = self.clusters[2]
        campaign, _ = self._published([cluster['cluster_id']])
        request = APIRequestFactory().get(f'/api/campaigns/{campaign.campaign_id}/')
        force_authenticate(request, user=self.admin)
        response = views.CampaignDetailView.as_view()(request,
                                                      campaign_id=campaign.campaign_id)
        response.render()
        self.assertEqual(response.status_code, 200)
        row = response.data
        self.assertEqual(row['clustering_run']['run_id'],
                         campaign.clustering_run_id)
        self.assertEqual(
            row['audience_clusters'],
            [{'cluster_id': cluster['cluster_id'],
              'category': cluster['category'],
              'eligible_customers': len(self._members(cluster['cluster_id'])),
              'coupons_issued': len(self._members(cluster['cluster_id']))}])
        self.assertEqual(row['coupons_redeemed'], 0)
        self.assertEqual(row['redemption_count'], 0)




class ClusterFixtureMixin:
    """A real four-cluster K-Means run over persisted RFM buyers (100 buyers).

    Mixed into the campaign and performance suites below so they all start from
    the same genuinely clustered population instead of a hand-written label.
    """

    GROUPS = {
        'high': dict(recency=10, freq=8, money=9000),
        'frequent': dict(recency=8, freq=25, money=3000),
        'moderate': dict(recency=20, freq=5, money=1500),
        'atrisk': dict(recency=320, freq=4, money=1800),
    }

    def _reset_stores(self):
        cache_manager.cache.clear()
        cache_manager._index_memo.clear()
        CampaignAudience.objects.all().delete()
        CampaignRedemption.objects.all().delete()
        Campaign.objects.all().delete()
        DashboardSnapshot.objects.all().delete()
        ClusteringRun.objects.all().delete()
        KmeansRunState.objects.all().delete()
        CustomerSegment.objects.all().delete()
        RfmAnalysisState.objects.all().delete()

    def _seed_and_cluster(self, per_group=25, version=1):
        records = []
        counter = 0
        for _name, g in self.GROUPS.items():
            for i in range(per_group):
                counter += 1
                records.append({
                    'customer_id': f'C{counter:04d}',
                    'segment': utils.SEGMENT_LOYAL,
                    'tags': [utils.TAG_BIG_SPENDER] if i % 10 == 0 else [],
                    'monetary': g['money'] + (i % 7) * (g['money'] * 0.01),
                    'recency_days': g['recency'] + (i % 5),
                    'frequency': g['freq'] + (i % 3),
                    'r_score': 3, 'f_score': 3, 'm_score': 3,
                    'first_purchase_date': '2024-01-01',
                    'last_purchase_date': '2026-01-01',
                })
        segment_store.store_records(records, version=version)
        result = clustering.run_clustering(save=True)
        self.assertTrue(result['available'])
        self.clusters = sorted(result['clusters'], key=lambda c: c['cluster_id'])

    def _members(self, cluster_id):
        return set(CustomerSegment.objects.filter(
            kmeans_cluster_id=cluster_id).values_list('customer_id', flat=True))

    def _cart(self, value):
        return [{'product_id': 'P1', 'name': 'Kurti', 'category': 'Ethnic',
                 'quantity': int(value) // 500, 'unit_price': 500.0}]


class RfmPerformanceTests(ClusterFixtureMixin, TestCase):
    """The RFM page reads persisted, cached aggregates - it never computes.

    Covers the performance contract: no clustering on page load, the aggregate
    served from cache (including across a process restart, which is what the
    durable snapshot exists for), a trimmed first-paint payload, the heavier
    analytics on their own lazy call, and counts that stay exactly right.
    """

    def setUp(self):
        self._reset_stores()
        self.admin = _admin_user()
        # The freshness nudge is tested on its own below; keeping its worker
        # quiet makes the rest of this class deterministic (on SQLite a real
        # background run cannot succeed anyway, since `public.orders` is absent).
        patcher = mock.patch.object(engine, '_start_freshness_worker')
        patcher.start()
        self.addCleanup(patcher.stop)
        self._seed_and_cluster()

    def _summary(self, user=None):
        request = APIRequestFactory().get('/api/analytics/rfm/summary')
        force_authenticate(request, user=user or self.admin)
        response = views.RfmSummaryView.as_view()(request)
        response.render()
        return response

    def _detail(self, user=None):
        request = APIRequestFactory().get('/api/analytics/rfm/analytics')
        force_authenticate(request, user=user or self.admin)
        response = views.RfmAnalyticsDetailView.as_view()(request)
        response.render()
        return response

    def test_summary_never_runs_the_clustering_algorithm(self):
        with mock.patch.object(
                clustering, 'run_clustering',
                side_effect=AssertionError('clustering must not run on a page load')):
            response = self._summary()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['available'])
        self.assertEqual(len(response.data['kmeans']['clusters']), 4)

    def test_first_open_after_a_restart_uses_the_durable_snapshot(self):
        """A cold process reads one small row, not the 100k-row aggregate.

        The in-process cache is emptied (exactly what a `runserver` restart does
        to LocMemCache) while the database keeps everything: the summary must
        still answer with zero aggregate queries, from the stored snapshot.
        """
        self.assertTrue(DashboardSnapshot.objects.filter(version=1).exists())
        cache_manager.cache.clear()
        with mock.patch.object(queries, 'fetch_dashboard_bundle',
                               side_effect=AssertionError('aggregate re-run')):
            response = self._summary()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['timing']['bundle_source'], 'snapshot')
        self.assertEqual(response.data['timing']['query_ms'], 0)

    def test_repeated_opens_are_a_cache_read_with_no_database_query(self):
        first = self._summary()
        self.assertEqual(first.data['timing']['bundle_source'], 'memory')
        with self.assertNumQueries(0):
            second = self._summary()
        self.assertEqual(second.data['timing']['bundle_source'], 'memory')
        self.assertEqual(second.data['timing']['query_ms'], 0)
        # The same completed numbers, not a partial or different analysis.
        self.assertEqual(second.data['totals'], first.data['totals'])
        self.assertEqual(
            [c['customer_count'] for c in second.data['kmeans']['clusters']],
            [c['customer_count'] for c in first.data['kmeans']['clusters']])

    def test_cluster_counts_are_the_actual_persisted_assignments(self):
        response = self._summary()
        clusters = {c['cluster_id']: c for c in response.data['kmeans']['clusters']}
        self.assertEqual(sum(c['customer_count'] for c in clusters.values()),
                         CustomerSegment.objects.count())
        stored = {}
        for cluster_id, label in CustomerSegment.objects.exclude(
                kmeans_cluster_id__isnull=True).values_list(
                    'kmeans_cluster_id', 'kmeans_category').distinct():
            stored.setdefault(cluster_id, set()).add(label)
        for cluster_id, row in clusters.items():
            self.assertEqual(row['customer_count'], len(self._members(cluster_id)))
            # One unambiguous stored label per cluster, which is what the bar shows.
            self.assertEqual(stored[cluster_id], {row['category']})

    def test_summary_payload_carries_only_the_first_paint_fields(self):
        data = self._summary().data
        for cluster in data['kmeans']['clusters']:
            # The heavy per-cluster profiles belong to the lazy detail call.
            for heavy in ('avg_monetary', 'avg_frequency', 'avg_recency',
                          'median_monetary', 'median_recency', 'median_frequency',
                          'share_single_order', 'share_low_order',
                          'avg_tenure_days', 'confidence', 'run_customer_count'):
                self.assertNotIn(heavy, cluster)
            # What the bars and their drill-down need stays.
            self.assertIn('category', cluster)
            self.assertIn('customer_count', cluster)
            self.assertIn('supported', cluster)
            self.assertIn('cautions', cluster)
        self.assertNotIn('distribution', data)
        self.assertNotIn('ambiguities', data['kmeans'])
        self.assertNotIn('scaler', json.dumps(data))
        # The KPI row the page renders first needs these and nothing else.
        self.assertEqual(
            set(data['totals']),
            {'total_customers', 'total_eligible_buyers',
             'never_purchased_customers', 'total_eligible_orders',
             'total_eligible_revenue'})

    def test_detail_endpoint_adds_the_heavy_analytics(self):
        response = self._detail()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['kmeans']['clusters']), 4)
        self.assertIn('avg_monetary', response.data['kmeans']['clusters'][0])
        self.assertIn('state', response.data['kmeans'])
        self.assertIn('ambiguities', response.data['kmeans'])
        self.assertIn('distribution', response.data)
        self.assertTrue(response.data['big_spender_count'] > 0)

    def test_detail_endpoint_is_admin_only(self):
        self.assertEqual(self._detail(_customer_user()).status_code, 403)

    def test_a_new_analysis_is_never_served_from_the_previous_version(self):
        # A second completed run replaces the stored population; the snapshot was
        # aggregated for version 1, so it must not be the answer for version 2.
        snapshot_version = DashboardSnapshot.objects.filter(version=1).count()
        self.assertEqual(snapshot_version, 1)
        segment_store.store_records([{
            'customer_id': 'ZZ9000', 'segment': utils.SEGMENT_NEW, 'tags': [],
            'monetary': 250, 'recency_days': 6, 'frequency': 1,
            'r_score': 5, 'f_score': 1, 'm_score': 1,
            'first_purchase_date': '2026-01-01', 'last_purchase_date': '2026-01-01',
        }], version=2)
        response = self._summary()
        self.assertEqual(response.data['version'], 2)
        # A full run stores exactly the buyers it saw, so version 2's own numbers
        # are reported - and never the superseded version 1 aggregate.
        self.assertEqual(response.data['totals']['total_eligible_buyers'],
                         CustomerSegment.objects.count())
        self.assertNotEqual(response.data['timing']['bundle_source'], 'snapshot')
        self.assertTrue(DashboardSnapshot.objects.filter(version=2).exists())

    def test_legacy_labels_are_refreshed_and_the_cache_rebuilt(self):
        # A persisted run carrying pre-switch label strings: the read path heals
        # it from the stored profiles and must not then serve the old aggregate.
        CustomerSegment.objects.exclude(kmeans_cluster_id__isnull=True).update(
            kmeans_category='Loyal Customer')
        state = KmeansRunState.objects.get(pk=KmeansRunState.SINGLETON_ID)
        state.mapping = [dict(row, category='Loyal Customer') for row in state.mapping]
        state.save()
        cache_manager.cache.clear()

        response = self._summary()
        served = {c['category'] for c in response.data['kmeans']['clusters']}
        self.assertEqual(served, set(utils.KMEANS_CATEGORIES))
        # And the very next read is a cache hit on the refreshed numbers.
        self.assertEqual(self._summary().data['timing']['bundle_source'], 'memory')

    def test_summary_does_not_block_on_a_freshness_query(self):
        # The nudge is rate limited and runs off the request thread.
        first = self._summary()
        self.assertTrue(first.data['nudging'])
        with mock.patch.object(engine, 'ensure_latest',
                               side_effect=AssertionError('inline freshness check')):
            second = self._summary()
        self.assertEqual(second.status_code, 200)
        self.assertFalse(second.data['nudging'])

    def test_customer_lists_stay_server_side_paginated(self):
        cluster = self.clusters[0]
        request = APIRequestFactory().get('/api/analytics/rfm/clusters/customers', {
            'category': cluster['category'], 'cluster_id': cluster['cluster_id'],
            'page': 2, 'page_size': 5})
        force_authenticate(request, user=self.admin)
        response = views.RfmClusterCustomersView.as_view()(request)
        response.render()
        self.assertEqual(len(response.data['results']), 5)
        self.assertEqual(response.data['count'], cluster['customer_count'])
        self.assertEqual(response.data['total_pages'],
                         -(-cluster['customer_count'] // 5))


class CampaignGroupPanelTests(ClusterFixtureMixin, TestCase):
    """The Campaign page's four-group section: labels, audiences and coupons."""

    def setUp(self):
        self._reset_stores()
        self.admin = _admin_user()
        self.now = timezone.now()
        self._seed_and_cluster()

    def _draft(self, cluster_ids, name='Group Offer', code=None, **overrides):
        payload = {
            'name': name,
            'coupon_code': code or name.upper().replace(' ', '_'),
            'offer_category': OfferCategory.DISCOUNT,
            'discount_rule': {'type': 'PERCENTAGE', 'percent': 15},
            'targeting_mode': TargetingMode.KMEANS,
            'target_cluster_ids': cluster_ids,
            'start_date': self.now - timedelta(hours=1),
            'end_date': self.now + timedelta(days=7),
            'min_order_amount': 0,
            'usage_type': UsageType.UNLIMITED,
        }
        payload.update(overrides)
        serializer = CampaignSerializer(data=payload)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        return serializer.save()

    def _set_status(self, campaign, new_status, user=None):
        request = APIRequestFactory().post(
            f'/api/campaigns/{campaign.campaign_id}/status/',
            {'status': new_status}, format='json')
        force_authenticate(request, user=user or self.admin)
        return views.CampaignStatusView.as_view()(
            request, campaign_id=campaign.campaign_id)

    def _panel(self):
        request = APIRequestFactory().get('/api/campaigns/clusters/')
        force_authenticate(request, user=self.admin)
        response = views.CampaignClusterOptionsView.as_view()(request)
        response.render()
        self.assertEqual(response.status_code, 200)
        return {c['cluster_id']: c for c in response.data['clusters']}

    def test_all_four_groups_are_reported_with_audience_and_coupon_counts(self):
        cluster = self.clusters[1]
        campaign = self._draft([cluster['cluster_id']])
        self._set_status(campaign, 'PUBLISHED')
        member = sorted(self._members(cluster['cluster_id']))[0]
        result = coupon_validation.validate_coupon(
            member, campaign.coupon_code, 1000, cart_lines=self._cart(1000))
        coupon_validation.redeem(campaign.campaign_id, member, 'ORDP1',
                                 result['discount'])

        panel = self._panel()
        row = panel[cluster['cluster_id']]
        size = len(self._members(cluster['cluster_id']))
        self.assertEqual(row['customer_count'], size)
        self.assertEqual(row['coupons_assigned'], size)
        self.assertEqual(row['coupons_redeemed'], 1)
        self.assertEqual(row['live_campaigns'], 1)
        self.assertEqual(
            [(c['name'], c['coupon_code'], c['status'], c['is_live'])
             for c in row['campaigns']],
            [(campaign.name, campaign.coupon_code, 'PUBLISHED', True)])
        # Groups nobody was issued anything for still show up, with zeros.
        other = panel[self.clusters[3]['cluster_id']]
        self.assertEqual(other['coupons_assigned'], 0)
        self.assertEqual(other['campaigns'], [])
        self.assertTrue(other['customer_count'] > 0)

    def test_group_stats_only_describe_the_current_clustering_run(self):
        cluster = self.clusters[0]
        campaign = self._draft([cluster['cluster_id']], name='Run1', code='RUN1CODE')
        self._set_status(campaign, 'PUBLISHED')
        issued = set(CampaignAudience.objects.filter(
            campaign=campaign).values_list('customer_id', flat=True))
        before = self._panel()[cluster['cluster_id']]
        self.assertEqual(before['coupons_assigned'], len(issued))
        self.assertEqual([c['name'] for c in before['campaigns']], ['Run1'])

        # A future clustering run adds a run row; cluster ids only carry meaning
        # inside the run that produced them, so the panel describes the newest
        # run's campaigns and the older campaign keeps its own frozen audience.
        clustering.run_clustering(save=True)
        after = self._panel()[cluster['cluster_id']]
        self.assertEqual(after['campaigns'], [])
        self.assertEqual(after['coupons_assigned'], 0)
        self.assertEqual(after['customer_count'],
                         len(self._members(cluster['cluster_id'])))
        self.assertEqual(set(CampaignAudience.objects.filter(
            campaign=campaign).values_list('customer_id', flat=True)), issued)
        # And it is still redeemable for exactly those customers.
        holder = sorted(issued)[0]
        self.assertIn('RUN1CODE',
                      [o['coupon_code']
                       for o in personalization.eligible_offers(holder)['offers']])

    def test_publishing_requires_a_completed_clustering_run(self):
        from .models import ClusteringRun as RunModel
        campaign = self._draft([self.clusters[0]['cluster_id']])
        RunModel.objects.all().delete()
        KmeansRunState.objects.all().update(run=None)
        cache_manager.cache.clear()
        response = self._set_status(campaign, 'PUBLISHED')
        self.assertEqual(response.status_code, 400)
        self.assertIn('clustering', response.data['detail'].lower())

    def test_no_clustering_at_all_means_no_selectable_groups(self):
        self._reset_stores()
        request = APIRequestFactory().get('/api/campaigns/clusters/')
        force_authenticate(request, user=self.admin)
        response = views.CampaignClusterOptionsView.as_view()(request)
        response.render()
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['available'])
        self.assertEqual(response.data['clusters'], [])
        # And a campaign cannot be authored without one.
        serializer = CampaignSerializer(data={
            'name': 'No Run', 'coupon_code': 'NORUN',
            'offer_category': OfferCategory.DISCOUNT,
            'discount_rule': {'type': 'PERCENTAGE', 'percent': 10},
            'targeting_mode': TargetingMode.KMEANS, 'target_cluster_ids': [0],
            'start_date': self.now, 'end_date': self.now + timedelta(days=1),
            'usage_type': UsageType.UNLIMITED,
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn('target_cluster_ids', serializer.errors)


class CampaignLifecycleTests(ClusterFixtureMixin, TestCase):
    """Edit / deactivate / reactivate, with issued coupons kept untouched."""

    def setUp(self):
        self._reset_stores()
        self.admin = _admin_user()
        self.now = timezone.now()
        self._seed_and_cluster()

    def _published(self, cluster_ids=None, **overrides):
        cluster_ids = cluster_ids or [self.clusters[0]['cluster_id']]
        base = dict(
            name='Lifecycle Offer', coupon_code='LIFECYCLE1',
            offer_category=OfferCategory.DISCOUNT,
            discount_rule={'type': 'PERCENTAGE', 'percent': 15},
            targeting_mode=TargetingMode.KMEANS,
            target_cluster_ids=cluster_ids,
            start_date=self.now - timedelta(hours=1),
            end_date=self.now + timedelta(days=7),
            min_order_amount=0, usage_type=UsageType.UNLIMITED)
        base.update(overrides)
        serializer = CampaignSerializer(data=base)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        campaign = serializer.save()
        request = APIRequestFactory().post(
            f'/api/campaigns/{campaign.campaign_id}/status/',
            {'status': 'PUBLISHED'}, format='json')
        force_authenticate(request, user=self.admin)
        response = views.CampaignStatusView.as_view()(
            request, campaign_id=campaign.campaign_id)
        self.assertEqual(response.status_code, 200, response.data)
        campaign.refresh_from_db()
        return campaign, response.data.get('audience')

    def _put(self, campaign, payload):
        request = APIRequestFactory().put(f'/api/campaigns/{campaign.campaign_id}/',
                                          payload, format='json')
        force_authenticate(request, user=self.admin)
        return views.CampaignDetailView.as_view()(
            request, campaign_id=campaign.campaign_id)

    def _set_status(self, campaign, new_status):
        request = APIRequestFactory().post(
            f'/api/campaigns/{campaign.campaign_id}/status/',
            {'status': new_status}, format='json')
        force_authenticate(request, user=self.admin)
        return views.CampaignStatusView.as_view()(
            request, campaign_id=campaign.campaign_id)

    def _payload(self, campaign, **overrides):
        payload = {
            'name': campaign.name, 'coupon_code': campaign.coupon_code,
            'description': campaign.description,
            'offer_category': campaign.offer_category,
            'discount_rule': campaign.discount_rule,
            'buy_get_rule': campaign.buy_get_rule,
            'scope': campaign.scope,
            'targeting_mode': campaign.targeting_mode,
            'target_cluster_ids': campaign.target_cluster_ids,
            'start_date': campaign.start_date.isoformat(),
            'end_date': campaign.end_date.isoformat(),
            'min_order_amount': campaign.min_order_amount,
            'usage_type': campaign.usage_type,
            'per_customer_limit': campaign.per_customer_limit,
            'global_usage_limit': campaign.global_usage_limit,
        }
        payload.update(overrides)
        return payload

    def _base(self, **overrides):
        base = dict(
            name='Draft', coupon_code='DRAFTCODE',
            offer_category=OfferCategory.DISCOUNT,
            discount_rule={'type': 'PERCENTAGE', 'percent': 10},
            targeting_mode=TargetingMode.KMEANS,
            target_cluster_ids=[self.clusters[0]['cluster_id']],
            start_date=self.now - timedelta(hours=1),
            end_date=self.now + timedelta(days=7),
            min_order_amount=0, usage_type=UsageType.UNLIMITED)
        base.update(overrides)
        return base

    def test_draft_can_be_edited_including_terms(self):
        serializer = CampaignSerializer(data=self._base(coupon_code='DRAFTEDIT'))
        self.assertTrue(serializer.is_valid(), serializer.errors)
        campaign = serializer.save()
        response = self._put(campaign, {
            'name': 'Renamed draft', 'description': 'edited',
            'discount_rule': {'type': 'PERCENTAGE', 'percent': 25},
            'min_order_amount': 500})
        self.assertEqual(response.status_code, 200, response.data)
        campaign.refresh_from_db()
        self.assertEqual(campaign.discount_value, 25)
        self.assertEqual(campaign.min_order_amount, 500)
        self.assertEqual(campaign.name, 'Renamed draft')

    def test_published_campaign_terms_are_frozen_once_coupons_are_issued(self):
        campaign, audience = self._published()
        member = sorted(self._members(self.clusters[0]['cluster_id']))[0]

        # The discount a holder is entitled to cannot be moved under their feet.
        response = self._put(campaign, self._payload(
            campaign, discount_rule={'type': 'PERCENTAGE', 'percent': 5}))
        self.assertEqual(response.status_code, 400)
        self.assertIn('discount_rule', response.data['errors'])
        # ... nor the validity window, nor the minimum order, nor the usage cap.
        for field, value in (('min_order_amount', 900),
                             ('per_customer_limit', 3),
                             ('max_discount', 100)):
            blocked = self._put(campaign, self._payload(campaign, **{field: value}))
            self.assertEqual(blocked.status_code, 400, field)
        shifted = self._put(campaign, self._payload(
            campaign, end_date=(self.now + timedelta(days=30)).isoformat()))
        self.assertEqual(shifted.status_code, 400)
        self.assertIn('end_date', shifted.data['errors'])

        campaign.refresh_from_db()
        self.assertEqual(campaign.discount_value, 15)
        result = coupon_validation.validate_coupon(
            member, campaign.coupon_code, 1000, cart_lines=self._cart(1000))
        self.assertEqual(result['discount'], 150.0)   # original 15% terms hold

    def test_published_campaign_still_edits_non_term_fields(self):
        campaign, _ = self._published()
        response = self._put(campaign, {
            'name': 'Same offer, clearer title', 'description': 'Still 15% off'})
        self.assertEqual(response.status_code, 200, response.data)
        campaign.refresh_from_db()
        self.assertEqual(campaign.name, 'Same offer, clearer title')
        self.assertEqual(campaign.discount_value, 15)

    def test_targeting_edit_extends_the_audience_without_changing_terms(self):
        first = self.clusters[0]
        second = self.clusters[1]
        campaign, _ = self._published([first['cluster_id']])
        before = set(CampaignAudience.objects.filter(
            campaign=campaign).values_list('customer_id', flat=True))
        self.assertEqual(before, self._members(first['cluster_id']))

        response = self._put(campaign, self._payload(
            campaign, target_cluster_ids=[first['cluster_id'], second['cluster_id']]))
        self.assertEqual(response.status_code, 200, response.data)
        after = set(CampaignAudience.objects.filter(
            campaign=campaign).values_list('customer_id', flat=True))
        self.assertEqual(after,
                         self._members(first['cluster_id'])
                         | self._members(second['cluster_id']))
        self.assertTrue(before.issubset(after))       # nothing revoked
        campaign.refresh_from_db()
        self.assertEqual(campaign.discount_value, 15)  # issued terms unchanged

    def test_deactivate_stops_claiming_and_redeeming_and_keeps_history(self):
        campaign, _ = self._published()
        members = sorted(self._members(self.clusters[0]['cluster_id']))
        redeemer, other = members[0], members[1]
        first = coupon_validation.validate_coupon(
            redeemer, campaign.coupon_code, 1000, cart_lines=self._cart(1000))
        coupon_validation.redeem(campaign.campaign_id, redeemer, 'ORDD1',
                                 first['discount'])

        paused = self._set_status(campaign, 'PAUSED')
        self.assertEqual(paused.status_code, 200)
        campaign.refresh_from_db()
        self.assertEqual(campaign.status, CampaignStatus.PAUSED)

        # Nobody can claim it any more: the offer list is empty for a customer
        # who never used it, and the one who did keeps only its historical Used
        # record - no AVAILABLE copy to claim.
        self.assertEqual(
            personalization.eligible_offers(other)['offers'], [])
        offers = personalization.eligible_offers(redeemer)['offers']
        self.assertEqual([o['status'] for o in offers], ['USED'])
        self.assertEqual(offers[0]['used_on_order'], 'ORDD1')
        # Checkout refuses it for both of them.
        for customer in (other, redeemer):
            with self.assertRaises(ValidationError):
                coupon_validation.validate_coupon(
                    customer, campaign.coupon_code, 1000, cart_lines=self._cart(1000))
        # Issued coupons and the redemption record are preserved.
        self.assertEqual(CampaignAudience.objects.filter(
            campaign=campaign).count(), len(members))
        self.assertEqual(CampaignRedemption.objects.filter(
            campaign=campaign).count(), 1)

    def test_reactivate_revalidates_dates_then_works_again(self):
        campaign, _ = self._published()
        member = sorted(self._members(self.clusters[0]['cluster_id']))[1]
        self._set_status(campaign, 'PAUSED')

        # Expired while paused: reactivation must be refused, not forced.
        Campaign.objects.filter(pk=campaign.pk).update(
            end_date=self.now - timedelta(minutes=1))
        campaign.refresh_from_db()
        refused = self._set_status(campaign, 'PUBLISHED')
        self.assertEqual(refused.status_code, 400)
        self.assertIn('validity', refused.data['detail'])

        Campaign.objects.filter(pk=campaign.pk).update(
            end_date=self.now + timedelta(days=3))
        resumed = self._set_status(campaign, 'PUBLISHED')
        self.assertEqual(resumed.status_code, 200, resumed.data)
        result = coupon_validation.validate_coupon(
            member, campaign.coupon_code, 1000, cart_lines=self._cart(1000))
        self.assertEqual(result['discount'], 150.0)
        self.assertIn(campaign.coupon_code,
                      [o['coupon_code']
                       for o in personalization.eligible_offers(member)['offers']])

    def test_published_campaigns_cannot_be_deleted(self):
        campaign, _ = self._published()
        request = APIRequestFactory().delete(f'/api/campaigns/{campaign.campaign_id}/')
        force_authenticate(request, user=self.admin)
        response = views.CampaignDetailView.as_view()(
            request, campaign_id=campaign.campaign_id)
        self.assertEqual(response.status_code, 409)
        self.assertIn('Deactivate', response.data['detail'])
        self.assertTrue(Campaign.objects.filter(pk=campaign.pk).exists())
        self.assertTrue(CampaignAudience.objects.filter(
            campaign=campaign).exists())

    def test_draft_can_still_be_deleted(self):
        serializer = CampaignSerializer(data=self._base(coupon_code='DRAFTDEL'))
        self.assertTrue(serializer.is_valid(), serializer.errors)
        campaign = serializer.save()
        request = APIRequestFactory().delete(f'/api/campaigns/{campaign.campaign_id}/')
        force_authenticate(request, user=self.admin)
        response = views.CampaignDetailView.as_view()(
            request, campaign_id=campaign.campaign_id)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Campaign.objects.filter(pk=campaign.pk).exists())

    def test_multi_cluster_coupon_is_visible_only_inside_the_selected_groups(self):
        first, second = self.clusters[0], self.clusters[1]
        outsider = self.clusters[2]
        campaign, audience = self._published([first['cluster_id'],
                                              second['cluster_id']])
        self.assertEqual(audience['coupons_issued'],
                         len(self._members(first['cluster_id']))
                         + len(self._members(second['cluster_id'])))
        for cluster in (first, second):
            member = sorted(self._members(cluster['cluster_id']))[0]
            offers = personalization.eligible_offers(member)['offers']
            self.assertEqual([o['coupon_code'] for o in offers],
                             [campaign.coupon_code])
            # The customer sees the real discount, validity and conditions.
            self.assertEqual(offers[0]['discount_value'], 15)
            self.assertEqual(offers[0]['offer_summary'],
                             benefits.offer_summary(campaign))
        foreign = sorted(self._members(outsider['cluster_id']))[0]
        self.assertEqual(personalization.eligible_offers(foreign)['offers'], [])
        with self.assertRaises(ValidationError):
            coupon_validation.validate_coupon(
                foreign, campaign.coupon_code, 5000, cart_lines=self._cart(5000))


class LegacyAudienceGateTests(ClusterFixtureMixin, TestCase):
    """A customer sees only their own K-Means group's offer - nothing else.

    Covers the shipped default (the previous rule-segment campaigns no longer
    reach anyone), the switch that puts them back in service, and that nothing
    about the historical rows is destroyed either way.
    """

    def setUp(self):
        self._reset_stores()
        self.admin = _admin_user()
        self.now = timezone.now()
        self._seed_and_cluster()

    def _legacy_campaign(self):
        """A campaign aimed at a segment the seeded buyer genuinely belongs to."""
        return Campaign.objects.create(
            name='Loyal Customers: VIP 20 OFF', coupon_code='OLDVIP20',
            discount_type=DiscountType.PERCENTAGE, discount_value=20,
            target_segments=[utils.SEGMENT_LOYAL], target_tags=[],
            start_date=self.now - timedelta(days=1),
            end_date=self.now + timedelta(days=1),
            min_order_amount=0, usage_type=UsageType.UNLIMITED,
            status=CampaignStatus.PUBLISHED)

    def _cluster_campaign(self, cluster_id=None):
        cluster_id = (cluster_id if cluster_id is not None
                      else self.clusters[0]['cluster_id'])
        campaign = Campaign.objects.create(
            name='Group VIP 30 OFF', coupon_code='GROUP30',
            discount_type=DiscountType.PERCENTAGE, discount_value=30,
            targeting_mode=TargetingMode.KMEANS,
            target_cluster_ids=[cluster_id],
            target_cluster_labels=[next(
                c['category'] for c in self.clusters
                if c['cluster_id'] == cluster_id)],
            clustering_run_id=clustering.latest_run().run_id,
            start_date=self.now - timedelta(days=1),
            end_date=self.now + timedelta(days=1),
            min_order_amount=0, usage_type=UsageType.UNLIMITED,
            status=CampaignStatus.DRAFT)
        audience, error = campaign_publishing.change_status(
            campaign, CampaignStatus.PUBLISHED)
        self.assertIsNone(error)
        campaign.refresh_from_db()
        return campaign, audience

    def _cart(self, value):
        return [{'product_id': 'P1', 'name': 'Kurti', 'category': 'Ethnic',
                 'quantity': int(value) // 500, 'unit_price': 500.0}]

    def test_legacy_campaign_reaches_no_customer_by_default(self):
        campaign = self._legacy_campaign()
        member = CustomerSegment.objects.get(customer_id='C0001')
        self.assertEqual(member.segment, utils.SEGMENT_LOYAL)   # it would match
        self.assertEqual(personalization.eligible_offers('C0001')['offers'], [])
        with self.assertRaises(ValidationError):
            coupon_validation.validate_coupon(
                'C0001', 'OLDVIP20', 1000, cart_lines=self._cart(1000))
        # The row itself and its targeting are untouched, just not reachable.
        campaign.refresh_from_db()
        self.assertEqual(campaign.status, CampaignStatus.PUBLISHED)
        self.assertEqual(campaign.target_segments, [utils.SEGMENT_LOYAL])

    def test_legacy_campaigns_work_again_when_the_switch_is_on(self):
        allow_legacy_campaigns(self)
        self._legacy_campaign()
        offers = personalization.eligible_offers('C0001')['offers']
        self.assertEqual([o['coupon_code'] for o in offers], ['OLDVIP20'])
        result = coupon_validation.validate_coupon(
            'C0001', 'OLDVIP20', 1000, cart_lines=self._cart(1000))
        self.assertEqual(result['discount'], 200.0)

    def test_cluster_offer_is_visible_only_to_its_own_group(self):
        campaign, audience = self._cluster_campaign()
        self.assertGreater(audience['coupons_issued'], 0)
        members = self._members(campaign.target_cluster_ids[0])
        outsider = next(iter(CustomerSegment.objects.exclude(
            kmeans_cluster_id=campaign.target_cluster_ids[0])
            .values_list('customer_id', flat=True)))

        holder = sorted(members)[0]
        self.assertEqual(
            [o['coupon_code'] for o in personalization.eligible_offers(holder)['offers']],
            ['GROUP30'])
        self.assertEqual(personalization.eligible_offers(outsider)['offers'], [])
        with self.assertRaises(ValidationError):
            coupon_validation.validate_coupon(
                outsider, 'GROUP30', 5000, cart_lines=self._cart(5000))
        # A legacy campaign published side by side never joins either list.
        self._legacy_campaign()
        self.assertEqual(
            [o['coupon_code'] for o in personalization.eligible_offers(holder)['offers']],
            ['GROUP30'])

    def test_admin_list_still_shows_and_labels_the_legacy_campaign(self):
        legacy = self._legacy_campaign()
        self._cluster_campaign()
        request = APIRequestFactory().get('/api/campaigns/', {})
        force_authenticate(request, user=self.admin)
        response = views.CampaignListCreateView.as_view()(request)
        response.render()
        codes = {c['coupon_code']: c for c in response.data['results']}
        self.assertIn('OLDVIP20', codes)                 # still manageable
        self.assertEqual(codes['OLDVIP20']['targeting_mode'], TargetingMode.LEGACY_RFM)
        self.assertEqual(codes['GROUP30']['targeting_mode'], TargetingMode.KMEANS)
        self.assertEqual(response.data['legacy_audience'],
                         {'visible_to_customers': False, 'campaign_count': 1})
        self.assertEqual(legacy.status, CampaignStatus.PUBLISHED)

    def test_deleting_a_published_campaign_is_refused_history_kept(self):
        campaign, _audience = self._cluster_campaign()
        member = sorted(self._members(campaign.target_cluster_ids[0]))[0]
        result = coupon_validation.validate_coupon(
            member, campaign.coupon_code, 1000, cart_lines=self._cart(1000))
        coupon_validation.redeem(campaign.campaign_id, member, 'ORGG1',
                                 result['discount'])

        request = APIRequestFactory().delete(f'/api/campaigns/{campaign.campaign_id}/')
        force_authenticate(request, user=self.admin)
        refused = views.CampaignDetailView.as_view()(
            request, campaign_id=campaign.campaign_id)
        self.assertEqual(refused.status_code, 409)
        self.assertTrue(Campaign.objects.filter(pk=campaign.pk).exists())
        self.assertTrue(CampaignAudience.objects.filter(
            campaign=campaign).exists())
        self.assertEqual(CampaignRedemption.objects.filter(
            campaign=campaign).count(), 1)

    def test_new_campaigns_can_only_be_authored_on_the_kmeans_groups(self):
        serializer = CampaignSerializer(data={
            'name': 'Old style', 'coupon_code': 'OLDSTYLE',
            'offer_category': OfferCategory.DISCOUNT,
            'discount_rule': {'type': 'PERCENTAGE', 'percent': 10},
            'target_segments': [utils.SEGMENT_CHAMPIONS],
            'start_date': self.now, 'end_date': self.now + timedelta(days=1),
            'usage_type': UsageType.UNLIMITED,
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn('targeting_mode', serializer.errors)
        self.assertFalse(Campaign.objects.filter(coupon_code='OLDSTYLE').exists())

    def test_publish_without_clustered_customers_is_refused_with_a_reason(self):
        CustomerSegment.objects.update(kmeans_cluster_id=None, kmeans_category='')
        campaign = Campaign.objects.create(
            name='No clustering', coupon_code='NOCLUST',
            discount_type=DiscountType.PERCENTAGE, discount_value=10,
            targeting_mode=TargetingMode.KMEANS,
            target_cluster_ids=[self.clusters[0]['cluster_id']],
            clustering_run_id=clustering.latest_run().run_id,
            start_date=self.now - timedelta(days=1),
            end_date=self.now + timedelta(days=1),
            usage_type=UsageType.UNLIMITED, status=CampaignStatus.DRAFT)
        audience, error = campaign_publishing.change_status(
            campaign, CampaignStatus.PUBLISHED)
        self.assertIsNotNone(error)
        self.assertIn('customer groups', error)
        campaign.refresh_from_db()
        self.assertEqual(campaign.status, CampaignStatus.DRAFT)
        self.assertEqual(CampaignAudience.objects.count(), 0)

    def test_deactivate_then_reactivate_round_trip_keeps_everything(self):
        campaign, audience = self._cluster_campaign()
        member = sorted(self._members(campaign.target_cluster_ids[0]))[0]
        issued = audience['coupons_issued']

        _audience, error = campaign_publishing.change_status(
            campaign, CampaignStatus.PAUSED)
        self.assertIsNone(error)
        self.assertEqual(personalization.eligible_offers(member)['offers'], [])
        with self.assertRaises(ValidationError):
            coupon_validation.validate_coupon(
                member, 'GROUP30', 1000, cart_lines=self._cart(1000))

        # Re-publishing re-checks the dates and keeps the same audience: nobody
        # new is pulled in and nobody is dropped.
        reissued, error = campaign_publishing.change_status(
            campaign, CampaignStatus.PUBLISHED)
        self.assertIsNone(error)
        self.assertEqual(reissued['coupons_issued'], issued)
        self.assertEqual(reissued['newly_assigned'], 0)
        self.assertEqual(CampaignAudience.objects.filter(
            campaign=campaign).count(), issued)
        self.assertEqual(
            coupon_validation.validate_coupon(
                member, 'GROUP30', 1000, cart_lines=self._cart(1000))['discount'],
            300.0)
