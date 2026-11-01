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
from rest_framework.serializers import ValidationError as DRFValidationError

from . import (benefits, cache_manager, campaign_engine, coupon_validation,
               personalization, rfm_scoring, segment_store, segmentation, utils)
from .models import (
    Campaign, CampaignRedemption, CampaignStatus, CustomerSegment, DiscountType,
    OfferCategory, RfmAnalysisState, UsageType,
)
from .serializers import CampaignSerializer


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
    """Authoring guards: segment mandatory, vocabulary and rule consistency."""

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
