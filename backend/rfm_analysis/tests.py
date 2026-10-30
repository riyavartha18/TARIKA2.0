"""Automated tests for the RFM segmentation and personalization system.

Pure logic (scoring, segmentation) is tested directly; the cache, personalization
and coupon layers run against the SQLite test database (the managed campaign
tables exist there) with the PostgreSQL aggregation mocked, since `public.orders`
is a pre-existing dataset table that has no counterpart under test settings.

Run:  python manage.py test rfm_analysis --settings=test_settings
"""

from datetime import timedelta
from unittest import mock

from django.test import TestCase
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from . import cache_manager, coupon_validation, personalization, rfm_scoring, segmentation, utils
from .models import Campaign, CampaignRedemption, CampaignStatus, DiscountType, UsageType


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


class CouponValidationTests(TestCase):
    def setUp(self):
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
        campaign = self._campaign(usage_type=UsageType.LIMITED, per_customer_limit=2)
        for i in range(2):
            d = coupon_validation.validate_coupon('C001', 'CHAMP20', 1000)['discount']
            coupon_validation.redeem(campaign.campaign_id, 'C001', f'ORD{i}', d)
        with self.assertRaises(ValidationError):
            coupon_validation.validate_coupon('C001', 'CHAMP20', 1000)

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
