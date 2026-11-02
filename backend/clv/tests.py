"""Automated tests for the CLV module.

Pure math (tiers, tenure, cohorts, survival) is tested directly; the
PostgreSQL aggregation is mocked because `public.orders` is a pre-existing
dataset table with no counterpart under the SQLite test settings (same
convention as the RFM suite). The managed `rfm_customer_segments` table does
exist there, so RFM->CLV Monetary persistence is tested for real.

Run:  python manage.py test clv --settings=test_settings
"""

from datetime import date
from decimal import Decimal
from unittest import mock

from django.test import TestCase
from rest_framework.test import APIRequestFactory, APIClient, force_authenticate

from accounts.models import Role
from rfm_analysis import segment_store
from rfm_analysis import utils as rfm_utils
from rfm_analysis.models import CustomerSegment

from . import calc, service, utils, views


def _row(customer_id, order_count, revenue, first_, last_, years, name=None):
    return {
        'customer_id': customer_id,
        'customer_name': name,
        'order_count': order_count,
        'revenue': revenue,
        'first_purchase_date': first_.isoformat() if isinstance(first_, date) else first_,
        'last_purchase_date': last_.isoformat() if isinstance(last_, date) else last_,
        'purchase_years': years,
    }


class RfmVersionMemoTests(TestCase):
    """The freshness check re-reads the persisted version at most once per TTL."""

    def test_memo_serves_repeat_reads_and_reshapes_after_invalidation(self):
        from django.core.cache import cache
        cache.delete(utils.CLV_STORED_RFM_VERSION_KEY)
        with mock.patch('rfm_analysis.segment_store.latest_version',
                        return_value=11) as latest:
            self.assertEqual(service._stored_rfm_version(), 11)
            self.assertEqual(service._stored_rfm_version(), 11)
        self.assertEqual(latest.call_count, 1)
        # An RFM run invalidates the memo (segment_store.store_records deletes
        # the key), so the very next read sees the new version.
        cache.delete(utils.CLV_STORED_RFM_VERSION_KEY)
        with mock.patch('rfm_analysis.segment_store.latest_version',
                        return_value=12):
            self.assertEqual(service._stored_rfm_version(), 12)
        cache.delete(utils.CLV_STORED_RFM_VERSION_KEY)


class EligibilityConsistencyTests(TestCase):
    """CLV must use exactly the RFM revenue definition, not a second one."""

    def test_status_and_price_policy_delegate_to_rfm(self):
        self.assertEqual(utils.eligible_delivery_statuses(),
                         rfm_utils.eligible_delivery_statuses())
        self.assertEqual(utils.exclude_negative_final_price(),
                         rfm_utils.EXCLUDE_NEGATIVE_FINAL_PRICE)


class HistoryDerivationTests(TestCase):
    def test_single_valid_purchase(self):
        h = calc.derive_history(1, 500.0, None,
                                date(2026, 1, 10), date(2026, 1, 10),
                                date(2026, 11, 1))
        self.assertEqual(h['historical_clv'], 500.0)
        self.assertEqual(h['aov'], 500.0)
        self.assertEqual(h['tenure_days'], 295)
        self.assertEqual(h['revenue_source'], 'orders_aggregate')

    def test_multiple_valid_purchases(self):
        h = calc.derive_history(4, 1200.0, None,
                                date(2025, 1, 1), date(2026, 6, 1),
                                date(2026, 11, 1))
        self.assertEqual(h['historical_clv'], 1200.0)
        self.assertEqual(h['aov'], 300.0)
        self.assertGreater(h['annual_frequency'], 1.0)

    def test_rfm_monetary_is_reused_when_stored(self):
        h = calc.derive_history(3, 999.99, Decimal('912.34'),
                                date(2025, 1, 1), date(2026, 6, 1),
                                date(2026, 11, 1))
        self.assertEqual(h['historical_clv'], 912.34)
        self.assertEqual(h['revenue_source'], 'rfm_monetary')
        # AOV numerator is the same revenue definition as historical CLV.
        self.assertEqual(h['aov'], round(912.34 / 3, 2))

    def test_zero_orders_is_safe(self):
        h = calc.derive_history(0, 0.0, None, None, None, date(2026, 11, 1))
        self.assertEqual(h['aov'], 0.0)
        self.assertEqual(h['annual_frequency'], 0.0)
        self.assertEqual(h['tenure_days'], 0)

    def test_very_short_tenure_is_stabilized_not_extrapolated(self):
        # One order the same day: frequency uses the documented 30-day floor.
        h = calc.derive_history(1, 100.0, None,
                                date(2026, 11, 1), date(2026, 11, 1),
                                date(2026, 11, 1))
        self.assertEqual(h['tenure_days'], 0)
        expected = round(1 / utils.MIN_TENURE_YEARS, 3)
        self.assertEqual(h['annual_frequency'], expected)
        self.assertLess(h['annual_frequency'], 365)

    def test_first_date_after_cutoff_never_gives_negative_tenure(self):
        h = calc.derive_history(1, 50.0, None,
                                date(2027, 1, 5), date(2027, 1, 5),
                                date(2026, 11, 1))
        self.assertEqual(h['tenure_days'], 0)


class TierTests(TestCase):
    def test_percentile_based_no_rupee_threshold(self):
        values = [float(v) for v in range(1, 101)]
        high, medium = calc.tier_boundaries(values)
        # P70/P30 of 1..100 with linear interpolation - reproducible.
        self.assertAlmostEqual(high, 70.3, places=1)
        self.assertAlmostEqual(medium, 30.7, places=1)
        self.assertEqual(calc.classify_tier(100.0, high, medium), utils.TIER_HIGH)
        self.assertEqual(calc.classify_tier(50.0, high, medium), utils.TIER_MEDIUM)
        self.assertEqual(calc.classify_tier(1.0, high, medium), utils.TIER_LOW)

    def test_empty_population_is_safe(self):
        self.assertEqual(calc.tier_boundaries([]), (None, None))
        self.assertIsNone(calc.classify_tier(10.0, None, None))


class CohortTests(TestCase):
    CUTOFF = date(2026, 11, 1)

    def _matrix(self, rows):
        return calc.build_cohort_matrix(rows)

    def test_single_period_buyers_never_survive_past_age_zero(self):
        rows = [_row('A', 1, 100, date(2024, 5, 1), date(2024, 5, 1), [2024])]
        report = calc.retention_report(self._matrix(rows), self.CUTOFF)
        # First month == last month: no survived month exists, no mature ages.
        self.assertEqual(report['mature_ages'], [])
        self.assertEqual(report['status'], utils.STATUS_INSUFFICIENT_DATA)

    def test_survival_uses_the_month_span_first_to_last_purchase(self):
        rows = [_row('A', 3, 300, date(2024, 5, 1), date(2024, 8, 15),
                     [2024])]
        matrix = self._matrix(rows)
        self.assertEqual(matrix['cells'], {(2024 * 12 + 5, 2024 * 12 + 8): 1})
        report = calc.retention_report(matrix, self.CUTOFF)
        # Three survived months observed for the one-member cohort.
        self.assertEqual(report['mature_ages'], [1, 2, 3])
        self.assertEqual(report['retention_probabilities'][1], 1.0)

    def test_cohorts_too_young_for_an_age_are_excluded_not_guessed(self):
        rows = [
            _row('OLD', 2, 200, date(2024, 1, 1), date(2024, 2, 1), [2024]),
            _row('NEW', 1, 100, date(2024, 2, 1), date(2024, 2, 1), [2024]),
        ]
        report = calc.retention_report(self._matrix(rows), self.CUTOFF)
        # Age 1 is only observable for the 2024-01 cohort (the 2024-02 cohort
        # cannot have a mature age 1 inside the horizon): S(1) = 1/1, never 1/2
        # with the young cohort silently counted as churned.
        self.assertEqual(report['retention_probabilities'][1], 1.0)

    def test_insufficient_history_reports_status_not_fabrication(self):
        # Only one mature monthly age exists across the whole history: below
        # the documented minimum, so no lifespan and 'insufficient_data'.
        rows = [
            _row('A', 2, 200, date(2024, 5, 1), date(2024, 6, 1), [2024]),
            _row('B', 1, 100, date(2024, 6, 1), date(2024, 6, 1), [2024]),
        ]
        report = calc.retention_report(self._matrix(rows), self.CUTOFF)
        self.assertEqual(report['status'], utils.STATUS_INSUFFICIENT_DATA)
        self.assertEqual(report['mature_ages'], [1])
        self.assertNotIn('expected_lifespan_years', report)
        self.assertEqual(report['message'], utils.INSUFFICIENT_DATA_MESSAGE)

    def test_mature_history_yields_documented_survival_estimate(self):
        rows = []
        # 10 buyers start 2023-03; all repurchase 2023-04, half also 2023-05.
        for i in range(10):
            last = date(2023, 5, 1) if i < 5 else date(2023, 4, 1)
            rows.append(_row(f'U{i}', 2, 100 * 2, date(2023, 3, 1), last,
                             [2023]))
        report = calc.retention_report(self._matrix(rows), self.CUTOFF)
        self.assertEqual(sorted(report['mature_ages']), [1, 2])
        survival = report['retention_probabilities']
        self.assertEqual(survival[1], 1.0)
        self.assertEqual(survival[2], 0.5)
        self.assertEqual(report['status'], utils.STATUS_OK)
        # E = 1 + S(1) + S(2) months = 2.5 (right-truncated, no invented tail)
        self.assertAlmostEqual(report['expected_lifespan_months'], 2.5, places=2)
        self.assertAlmostEqual(report['expected_lifespan_years'], 2.5 / 12.0, places=3)

    def test_missing_first_date_rows_are_skipped(self):
        rows = [_row('A', 1, 100, None, None, [])]
        matrix = self._matrix(rows)
        self.assertEqual(matrix['cells'], {})


class LifespanTests(TestCase):
    SURVIVAL = {0: 1.0, 1: 1.0, 2: 0.5}
    AGES = [1, 2]

    def test_remaining_lifespan_is_conditional(self):
        fresh = calc.remaining_lifespan_months(self.SURVIVAL, self.AGES, 0)
        survived = calc.remaining_lifespan_months(self.SURVIVAL, self.AGES, 1)
        self.assertAlmostEqual(fresh, 1.0 + 0.5, places=3)
        self.assertAlmostEqual(survived, 0.5, places=3)

    def test_beyond_observed_ages_no_invented_survival(self):
        # A buyer older than the oldest observed age has no evidence: None
        # ("cannot be estimated"), never a fabricated or a fake-zero lifespan.
        self.assertIsNone(
            calc.remaining_lifespan_months(self.SURVIVAL, self.AGES, 2))

    def test_future_clv_formula(self):
        self.assertEqual(calc.future_clv(300.0, 2.0, 1.5), 900.0)
        self.assertIsNone(calc.future_clv(300.0, 2.0, None))

    def test_future_for_customer_uses_the_pooled_curve(self):
        retention = {
            'status': utils.STATUS_OK, 'horizon_period': 2024 * 12 + 12,
            'observation_horizon': '2024-12-15',
            'mature_ages': [1, 2], 'retention_probabilities': self.SURVIVAL,
        }
        remaining, future, total = calc.future_for_customer(
            historical_clv=1000.0, aov=100.0, order_count=10,
            first_purchase_date='2024-10-01', retention=retention)
        # elapsed = 2 months -> beyond the observed ages: no estimate, no zero.
        self.assertIsNone(remaining)
        self.assertIsNone(future)
        self.assertIsNone(total)

        remaining, future, total = calc.future_for_customer(
            historical_clv=1000.0, aov=100.0, order_count=10,
            first_purchase_date='2024-11-01', retention=retention)
        # elapsed = 1: remaining = S(2)/S(1) = 0.5 months = 0.042 years.
        self.assertEqual(remaining, round(0.5 / 12.0, 3))
        observed_years = 44 / utils.DAYS_PER_YEAR  # 2024-11-01 -> 2024-12-15
        expected_freq = round(10 / max(observed_years, utils.MIN_TENURE_YEARS), 3)
        self.assertEqual(future, round(100.0 * expected_freq * remaining, 2))
        self.assertEqual(total, round(1000.0 + future, 2))

    def test_future_clv_sql_expression_shape(self):
        retention = {
            'status': utils.STATUS_OK, 'horizon_period': 2024 * 12 + 12,
            'observation_horizon': '2024-12-15',
            'mature_ages': [1, 2], 'retention_probabilities': self.SURVIVAL,
        }
        sql = calc.future_clv_sql(retention)
        self.assertIsNotNone(sql)
        self.assertIn("DATE '2024-12-15'", sql)
        self.assertIn('WHEN 0 THEN', sql)
        self.assertIn('WHEN 1 THEN', sql)
        self.assertNotIn('WHEN 2 THEN', sql)  # elapsed >= max age: NULL
        # Placeholder-free: the expression can be repeated in WHERE/ORDER BY.
        self.assertNotIn('%s', sql)
        # Insufficient curve -> no expression at all.
        self.assertIsNone(
            calc.future_clv_sql({'status': utils.STATUS_INSUFFICIENT_DATA}))


class RfmMonetaryPersistenceTests(TestCase):
    """The RFM run persists the Monetary value CLV consumes (data sharing)."""

    def test_store_records_persists_monetary_and_segment(self):
        records = [
            {'customer_id': 'A', 'segment': rfm_utils.SEGMENT_CHAMPIONS,
             'tags': [rfm_utils.TAG_BIG_SPENDER], 'monetary': 1234.56},
            {'customer_id': 'B', 'segment': rfm_utils.SEGMENT_AT_RISK,
             'tags': [], 'monetary': 10.0},
        ]
        stored = segment_store.store_records(records, version=7, analysis_date=date(2026, 11, 1))
        self.assertEqual(stored, 2)
        row = CustomerSegment.objects.get(pk='A')
        self.assertEqual(row.monetary, Decimal('1234.56'))
        self.assertEqual(row.segment, rfm_utils.SEGMENT_CHAMPIONS)

        # A re-run that drops buyer B removes the stale label entirely.
        segment_store.store_records(records[:1], version=8)
        self.assertFalse(CustomerSegment.objects.filter(pk='B').exists())
        self.assertEqual(CustomerSegment.objects.get(pk='A').version, 8)

    def test_fetch_stored_rfm_metrics_reads_current_version(self):
        segment_store.store_records(
            [{'customer_id': 'A', 'segment': rfm_utils.SEGMENT_LOYAL,
              'tags': [], 'monetary': 500.0}], version=3)
        from . import queries
        version, stored = queries.fetch_stored_rfm_metrics()
        self.assertEqual(version, 3)
        self.assertEqual(stored['A']['monetary'], 500.0)
        self.assertEqual(stored['A']['segment'], rfm_utils.SEGMENT_LOYAL)

    def test_legacy_rows_without_monetary_fall_back_to_live_revenue(self):
        # Rows written before Monetary persistence existed: value stays None,
        # and derive_history uses the orders-side revenue instead.
        from django.utils import timezone
        CustomerSegment.objects.create(customer_id='OLD', segment='Champions',
                                       monetary=None, version=1,
                                       computed_at=timezone.now())
        from . import queries
        with mock.patch('clv.queries.RfmAnalysisState.objects') as state_objects:
            state = mock.Mock(version=1)
            state_objects.filter.return_value.first.return_value = state
            with mock.patch('clv.queries.CustomerSegment.objects') as seg_objects:
                # The result table is read in full (latest state per customer),
                # so there is no version filter to chain onto any more.
                seg_objects.values_list.return_value = [
                    ('OLD', 'Champions', None)]
                version, stored = queries.fetch_stored_rfm_metrics()
        self.assertEqual(version, 1)
        self.assertIsNone(stored['OLD']['monetary'])
        h = calc.derive_history(2, 777.0, stored['OLD']['monetary'],
                                date(2025, 1, 1), date(2026, 1, 1), date(2026, 11, 1))
        self.assertEqual(h['historical_clv'], 777.0)
        self.assertEqual(h['revenue_source'], 'orders_aggregate')


def _sample_rows():
    return [
        _row('A', 2, 900.0, date(2024, 5, 1), date(2025, 5, 1), [2024, 2025], name='Alice'),
        _row('B', 1, 100.0, date(2026, 10, 1), date(2026, 10, 1), [2026], name='Bob'),
        _row('C', 5, 5000.0, date(2024, 1, 1), date(2026, 8, 1), [2024, 2025, 2026], name='Carol'),
    ], date(2026, 11, 1)


class ServiceBuildTests(TestCase):
    """build_state runs the whole pipeline against mocked SQL reads."""

    def _build(self, stored=None, rfm_version=1):
        rows, cutoff = _sample_rows()
        with mock.patch('clv.queries.fetch_buyer_clv_rows', return_value=(rows, cutoff.isoformat())), \
             mock.patch('clv.queries.fetch_stored_rfm_metrics',
                        return_value=(rfm_version, stored or {})):
            return service.build_state()

    def test_records_and_totals(self):
        meta = self._build()
        self.assertEqual(meta['buyer_count'], 3)
        self.assertEqual(meta['totals']['total_historical_revenue'], 6000.0)
        self.assertEqual(meta['totals']['avg_historical_clv'], 2000.0)
        records = service.get_records()
        self.assertEqual([r['customer_id'] for r in records], ['A', 'B', 'C'])
        self.assertEqual(records[2]['historical_clv'], 5000.0)

    def test_missing_rfm_segment_is_reported_not_crashing(self):
        meta = self._build()
        records = service.get_records()
        self.assertIsNone(records[0]['rfm_segment'])
        # The segment analysis buckets unsegmented buyers explicitly.
        self.assertTrue(any(s['segment'] == 'Unsegmented' for s in meta['segments']))

    def test_stored_rfm_monetary_flows_into_historical_clv(self):
        meta = self._build(stored={'A': {'segment': 'Champions',
                                         'monetary': 850.0}})
        self.assertEqual(meta['monetary_source'], 'mixed_orders_fallback')
        record_a = next(r for r in service.get_records() if r['customer_id'] == 'A')
        self.assertEqual(record_a['historical_clv'], 850.0)
        self.assertEqual(record_a['rfm_segment'], 'Champions')

    def test_future_clv_computed_when_history_supports_it(self):
        # The sample spans 2024-01 -> 2026-10: dozens of mature MONTHLY ages,
        # so the pooled survival curve supports a per-buyer Future CLV.
        meta = self._build()
        self.assertEqual(meta['future_clv_status'], utils.STATUS_OK)
        self.assertIsNotNone(meta['totals']['avg_future_clv'])
        records = {r['customer_id']: r for r in service.get_records()}
        # A (first 2024-05) and B (brand-new 2026-10) sit inside the observed
        # ages and get a real positive estimate ...
        for cid in ('A', 'B'):
            self.assertIsNotNone(records[cid]['future_clv'])
            self.assertGreater(records[cid]['future_clv'], 0)
            self.assertEqual(
                records[cid]['total_clv'],
                round(records[cid]['historical_clv']
                      + records[cid]['future_clv'], 2))
        # ... C started in the very first cohort month and has already lived
        # beyond the oldest observed age: no evidence to project on, so the
        # value stays None (never a fabricated number or a fake zero).
        self.assertIsNone(records['C']['future_clv'])

    def test_empty_population_is_valid_state(self):
        with mock.patch('clv.queries.fetch_buyer_clv_rows', return_value=([], None)), \
             mock.patch('clv.queries.fetch_stored_rfm_metrics', return_value=(None, {})):
            meta = service.build_state()
        self.assertEqual(meta['buyer_count'], 0)
        self.assertEqual(meta['future_clv_status'], utils.STATUS_INSUFFICIENT_DATA)

    def test_at_risk_overlay_uses_rfm_segment(self):
        meta = self._build(stored={
            'A': {'segment': rfm_utils.SEGMENT_AT_RISK, 'monetary': 900.0},
            'C': {'segment': rfm_utils.SEGMENT_CHAMPIONS, 'monetary': 5000.0},
        })
        self.assertEqual(meta['at_risk_count'], 1)


class FastPathBuildTests(TestCase):
    """build_state aggregates CLV in SQL over the persisted RFM table and never
    loads the population or scans orders on the fast path."""

    def test_summary_segments_and_cohorts_are_all_aggregated(self):
        agg = {'buyer_count': 2, 'total_revenue': 5900.0,
               'avg_historical_clv': 2950.0, 'high_value': 3000.0,
               'medium_value': 1000.0, 'at_risk_count': 1,
               'future_supported_count': 2, 'avg_future_clv': 900.0,
               'avg_total_clv': 3850.0}
        # Two buyers from 2024-01: one survives 2 months, one survives 12.
        matrix = {'cells': {(2024 * 12 + 1, 2024 * 12 + 3): 1,
                            (2024 * 12 + 1, 2025 * 12 + 1): 1},
                  'horizon_period': 2025 * 12 + 1,
                  'horizon_date': '2025-01-20'}
        tiers = {'High Value': 1, 'Medium Value': 0, 'Low Value': 1}
        segments = [{'segment': 'Champions', 'customer_count': 1,
                     'avg_historical_clv': 900.0, 'total_historical_clv': 900.0,
                     'avg_orders': 2.0, 'avg_future_clv': 500.0}]
        state = mock.Mock(version=9, analysis_date=date(2027, 6, 1))
        with mock.patch('clv.queries.fetch_clv_aggregates', return_value=agg), \
             mock.patch('clv.queries.fetch_cohort_matrix', return_value=matrix), \
             mock.patch('clv.queries.fetch_tier_counts', return_value=tiers), \
             mock.patch('clv.queries.fetch_segment_analysis', return_value=segments), \
             mock.patch('rfm_analysis.segment_store.get_state', return_value=state), \
             mock.patch('clv.queries.fetch_buyer_clv_rows') as orders_scan:
            meta = service.build_state()
            orders_scan.assert_not_called()  # no 1M-row scan / no 100k load

        self.assertEqual(meta['buyer_count'], 2)
        self.assertEqual(meta['rfm_version'], 9)
        self.assertEqual(meta['cutoff_date'], '2027-06-01')
        self.assertEqual(meta['monetary_source'], 'rfm_stored')
        self.assertEqual(meta['totals']['total_historical_revenue'], 5900.0)
        self.assertEqual(meta['totals']['high_value_count'], 1)
        # Population Future CLV comes straight from the SQL aggregate.
        self.assertEqual(meta['totals']['avg_future_clv'], 900.0)
        self.assertEqual(meta['totals']['future_clv_eligible_count'], 2)
        self.assertEqual(meta['at_risk_count'], 1)
        self.assertEqual(meta['segments'], segments)
        # Server-side cohort histogram drove the survival report: every month
        # from the earliest cohort to the horizon is an observed age.
        self.assertEqual(meta['future_clv_status'], utils.STATUS_OK)
        self.assertEqual(sorted(meta['cohorts']['mature_ages']),
                         list(range(1, 13)))

    def test_no_persisted_results_falls_back_to_orders_build(self):
        # Aggregate path unavailable (backend without the live table) -> the
        # original per-buyer order build is used so CLV still produces results.
        rows, cutoff = _sample_rows()
        with mock.patch('clv.queries.fetch_clv_aggregates', return_value=None), \
             mock.patch('clv.queries.fetch_buyer_clv_rows',
                        return_value=(rows, cutoff.isoformat())), \
             mock.patch('clv.queries.fetch_stored_rfm_metrics', return_value=(1, {})):
            meta = service.build_state()
        self.assertEqual(meta['buyer_count'], 3)


class ViewTests(TestCase):
    """Endpoint behaviour with the state mocked (pagination, filters, auth)."""

    def setUp(self):
        self.client = APIClient()
        meta = {'cutoff_date': '2026-11-01', 'computed_at': 'x', 'rfm_version': 1,
                'monetary_source': 'rfm_stored', 'buyer_count': 2,
                'totals': {'total_historical_revenue': 300.0, 'avg_historical_clv': 150.0,
                           'high_value_count': 1, 'high_value_pct': 50.0,
                           'avg_future_clv': None, 'avg_total_clv': None},
                'tiers': [{'tier': utils.TIER_HIGH, 'count': 1},
                          {'tier': utils.TIER_MEDIUM, 'count': 0},
                          {'tier': utils.TIER_LOW, 'count': 1}],
                'at_risk_count': 0, 'segments': [],
                'tier_boundaries': {'high': 200.0, 'medium': 50.0},
                'cohorts': None, 'future_clv_status': utils.STATUS_INSUFFICIENT_DATA,
                'future_clv_message': utils.INSUFFICIENT_DATA_MESSAGE,
                'assumptions': {}, 'compute_ms': 1}
        self.records = [
            {'customer_id': 'A', 'customer_name': 'Ann', 'historical_clv': 250.0,
             'future_clv': None, 'total_clv': None, 'aov': 250.0, 'order_count': 1,
             'first_purchase_date': '2024-01-01', 'last_purchase_date': '2024-01-01',
             'tenure_days': 1000, 'annual_frequency': 1.0,
             'rfm_segment': 'Champions', 'clv_tier': utils.TIER_HIGH},
            {'customer_id': 'B', 'customer_name': 'Ben', 'historical_clv': 50.0,
             'future_clv': None, 'total_clv': None, 'aov': 25.0, 'order_count': 2,
             'first_purchase_date': '2025-01-01', 'last_purchase_date': '2025-06-01',
             'tenure_days': 640, 'annual_frequency': 2.0,
             'rfm_segment': 'At-Risk', 'clv_tier': utils.TIER_LOW},
        ]
        self.patches = [
            mock.patch.object(service, 'ensure_state',
                              return_value={'available': True, 'refreshing': False,
                                            'run_status': {'status': 'completed'}}),
            mock.patch.object(service, 'get_meta', return_value=meta),
            mock.patch.object(service, 'get_records', return_value=self.records),
            mock.patch.object(service, 'get_run_status',
                              return_value={'status': 'completed'}),
        ]
        for p in self.patches:
            p.start()
        self.addCleanup(mock.patch.stopall)

    def _as(self, role):
        """Attach a fake authenticated user with the given role."""
        user = mock.Mock()
        user.is_authenticated = True
        user.is_active = True
        user.role = role
        return user

    def test_customers_pagination_and_search(self):
        user = self._as(Role.ADMIN)
        base = [
            {'customer_id': 'A', 'segment': 'Champions', 'monetary': 250.0,
             'frequency': 1, 'first_purchase_date': '2024-01-01',
             'last_purchase_date': '2024-01-01'},
            {'customer_id': 'B', 'segment': 'At-Risk', 'monetary': 50.0,
             'frequency': 2, 'first_purchase_date': '2025-01-01',
             'last_purchase_date': '2025-06-01'},
        ]

        def fake_page(segment=None, tier=None, search='', order_by='monetary',
                      direction='desc', limit=25, offset=0, future_sql=None,
                      future_min=None, future_max=None, future_state=None):
            rows = [r for r in base
                    if not search or search.lower() in r['customer_id'].lower()]
            return rows[offset:offset + limit], len(rows)

        with mock.patch('clv.queries.fetch_customer_page', side_effect=fake_page):
            request = APIRequestFactory().get(
                '/api/clv/customers', {'page': 1, 'page_size': 1})
            force_authenticate(request, user=user)
            response = views.ClvCustomersView.as_view()(request)
            response.render()
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data['count'], 2)
            self.assertEqual(len(response.data['results']), 1)

            request = APIRequestFactory().get('/api/clv/customers', {'search': 'b'})
            force_authenticate(request, user=user)
            response = views.ClvCustomersView.as_view()(request)
            response.render()
            self.assertEqual(response.data['count'], 1)
            self.assertEqual(response.data['results'][0]['customer_id'], 'B')

            request = APIRequestFactory().get('/api/clv/customers')
            force_authenticate(request, user=user)
            response = views.ClvCustomersView.as_view()(request)
            response.render()
            a = next(r for r in response.data['results'] if r['customer_id'] == 'A')
            # Derived from the persisted RFM monetary + cached boundaries.
            self.assertEqual(a['historical_clv'], 250.0)
            self.assertEqual(a['clv_tier'], utils.TIER_HIGH)

    def test_future_filters_reach_the_query(self):
        """Future-CLV range/availability filters are server-side parameters."""
        captured = {}

        def fake_page(**kwargs):
            captured.update(kwargs)
            return [], 0

        user = self._as(Role.ADMIN)
        with mock.patch('clv.queries.fetch_customer_page', side_effect=fake_page):
            request = APIRequestFactory().get('/api/clv/customers', {
                'future_state': 'insufficient', 'future_min': '100',
                'future_max': '5000'})
            force_authenticate(request, user=user)
            response = views.ClvCustomersView.as_view()(request)
            response.render()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(captured['future_state'], 'insufficient')
        self.assertEqual(captured['future_min'], 100.0)
        self.assertEqual(captured['future_max'], 5000.0)

    def test_endpoints_are_admin_only(self):
        customer = self._as(Role.CUSTOMER)
        request = APIRequestFactory().get('/api/clv/summary')
        force_authenticate(request, user=customer)
        response = views.ClvSummaryView.as_view()(request)
        response.render()
        self.assertEqual(response.status_code, 403)

        request = APIRequestFactory().post('/api/clv/recalculate')
        force_authenticate(request, user=customer)
        response = views.ClvRecalculateView.as_view()(request)
        response.render()
        self.assertEqual(response.status_code, 403)

        # An unauthenticated request is rejected as well (401 by the project's
        # authentication classes, before permissions are even consulted).
        request = APIRequestFactory().get('/api/clv/summary')
        response = views.ClvSummaryView.as_view()(request)
        response.render()
        self.assertEqual(response.status_code, 401)

    def test_summary_exposes_cutoff_and_insufficient_status(self):
        from rest_framework.test import APIRequestFactory
        request = APIRequestFactory().get('/api/clv/summary')
        force_authenticate(request, user=self._as(Role.ADMIN))
        response = views.ClvSummaryView.as_view()(request)
        response.render()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['available'])
        self.assertEqual(response.data['cutoff_date'], '2026-11-01')
        self.assertEqual(response.data['future_clv_status'],
                         utils.STATUS_INSUFFICIENT_DATA)
        self.assertEqual(response.data['future_clv_message'],
                         utils.INSUFFICIENT_DATA_MESSAGE)

    def test_segments_separates_tiers_from_at_risk_overlay(self):
        from rest_framework.test import APIRequestFactory
        request = APIRequestFactory().get('/api/clv/segments')
        force_authenticate(request, user=self._as(Role.ADMIN))
        response = views.ClvSegmentsView.as_view()(request)
        response.render()
        self.assertEqual([t['tier'] for t in response.data['tiers']], utils.VALUE_TIERS)
        self.assertEqual(response.data['at_risk']['segment'], rfm_utils.SEGMENT_AT_RISK)
        self.assertIn('overlaps', response.data['at_risk']['note'])

    def test_recalculate_starts_forced_background_build(self):
        from rest_framework.test import APIRequestFactory
        request = APIRequestFactory().post('/api/clv/recalculate')
        force_authenticate(request, user=self._as(Role.ADMIN))
        with mock.patch.object(service, 'start_background_build',
                               return_value=(True, {'status': 'queued'})) as starter:
            response = views.ClvRecalculateView.as_view()(request)
        response.render()
        self.assertEqual(response.status_code, 202)
        starter.assert_called_once_with(force=True)

    def test_recalculate_conflict_when_already_running(self):
        from rest_framework.test import APIRequestFactory
        request = APIRequestFactory().post('/api/clv/recalculate')
        force_authenticate(request, user=self._as(Role.ADMIN))
        with mock.patch.object(service, 'start_background_build',
                               return_value=(False, {'status': 'running'})):
            response = views.ClvRecalculateView.as_view()(request)
        response.render()
        self.assertEqual(response.status_code, 409)

    def test_customer_detail_is_index_hit_not_recompute(self):
        from rest_framework.test import APIRequestFactory
        request = APIRequestFactory().get('/api/clv/customers/A')
        force_authenticate(request, user=self._as(Role.ADMIN))
        stored = mock.Mock(customer_id='A', segment='Champions', monetary=250.0,
                           frequency=1, first_purchase_date=date(2024, 1, 1),
                           last_purchase_date=date(2024, 1, 1))
        with mock.patch.object(service, 'state_is_current', return_value=True), \
             mock.patch('clv.views.segment_store.get', return_value=stored):
            response = views.ClvCustomerDetailView.as_view()(request, customer_id='A')
        response.render()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['historical_clv'], 250.0)
        self.assertEqual(response.data['clv_tier'], utils.TIER_HIGH)

    def test_customer_detail_falls_back_to_single_customer_query(self):
        from rest_framework.test import APIRequestFactory
        request = APIRequestFactory().get('/api/clv/customers/Z')
        force_authenticate(request, user=self._as(Role.ADMIN))
        metrics = {'order_count': 2, 'revenue': '120.00',
                   'first_purchase_date': '2025-02-01',
                   'last_purchase_date': '2026-03-01',
                   'cutoff_date': '2026-11-01'}
        with mock.patch.object(service, 'state_is_current', return_value=False), \
             mock.patch('clv.queries.fetch_single_customer_metrics', return_value=metrics), \
             mock.patch('clv.views.segment_store.get', return_value=None):
            response = views.ClvCustomerDetailView.as_view()(request, customer_id='Z')
        response.render()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['historical_clv'], 120.0)
        self.assertIsNone(response.data['future_clv'])

    def test_customer_detail_404_without_valid_orders(self):
        from rest_framework.test import APIRequestFactory
        request = APIRequestFactory().get('/api/clv/customers/Z')
        force_authenticate(request, user=self._as(Role.ADMIN))
        with mock.patch.object(service, 'state_is_current', return_value=False), \
             mock.patch('clv.queries.fetch_single_customer_metrics', return_value=None):
            response = views.ClvCustomerDetailView.as_view()(request, customer_id='Z')
        response.render()
        self.assertEqual(response.status_code, 404)
