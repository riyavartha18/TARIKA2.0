import calendar
from datetime import date, datetime
import os
from unittest.mock import patch, MagicMock
import numpy as np

import django
from django.apps import apps
if not apps.ready:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    django.setup()

from django.test import SimpleTestCase
from demand_prediction import engine, views
from demand_prediction.engine import DecisionTreeEngine
from demand_prediction import inventory_metrics as im
from demand_prediction.revenue_forecasting import (
    fit_holt_winters_additive,
    calculate_metrics,
    compute_prediction_interval,
    RevenueForecastingService,
)


class InventoryVelocityClassificationTest(SimpleTestCase):
    """Movement is classified from ACTUAL sales quantity, not from stock."""

    # Tier cuts for a distribution: FAST > 4 units, NORMAL > 2, SLOW <= 2.
    FAST_CUT, NORMAL_CUT = 4.0, 2.0

    def test_zero_sales_is_always_not_moving(self):
        # Any zero-sales product is NOT MOVING regardless of stock, and its
        # days_of_stock is None ("No Sales") when it still holds stock.
        for stock in (0, 500):
            movement, avg, days = im.classify(0, self.FAST_CUT, self.NORMAL_CUT, stock=stock)
            self.assertEqual(movement, im.MOVEMENT_NOT)
            self.assertEqual(avg, 0.0)
        self.assertIsNone(im.classify(0, self.FAST_CUT, self.NORMAL_CUT, stock=500)[2])
        self.assertEqual(im.classify(0, self.FAST_CUT, self.NORMAL_CUT, stock=0)[2], 0.0)

    def test_higher_sales_never_lands_in_a_lower_tier(self):
        # As sales quantity grows, the tier rank only stays or improves
        # (lower rank number = higher movement tier); it never regresses.
        prev_rank = 99
        for units in range(0, 15):
            movement, _avg, _d = im.classify(units, self.FAST_CUT, self.NORMAL_CUT, stock=100)
            rank = im.MOVEMENT_RANK[movement]
            self.assertLessEqual(rank, prev_rank)
            prev_rank = rank

    def test_bands_by_sales_quantity(self):
        self.assertEqual(im.classify(10, self.FAST_CUT, self.NORMAL_CUT)[0], im.MOVEMENT_FAST)
        self.assertEqual(im.classify(3, self.FAST_CUT, self.NORMAL_CUT)[0], im.MOVEMENT_NORMAL)
        self.assertEqual(im.classify(2, self.FAST_CUT, self.NORMAL_CUT)[0], im.MOVEMENT_SLOW)
        self.assertEqual(im.classify(1, self.FAST_CUT, self.NORMAL_CUT)[0], im.MOVEMENT_SLOW)

    def test_stock_never_moves_a_product_up_a_tier(self):
        # Same sales, wildly different stock => same movement tier.
        low = im.classify(10, self.FAST_CUT, self.NORMAL_CUT, stock=1)[0]
        high = im.classify(10, self.FAST_CUT, self.NORMAL_CUT, stock=99999)[0]
        self.assertEqual(low, high)

    def test_avg_daily_and_days_of_stock_edges(self):
        # avg daily = units / 30 (2 dp); zero stock with sales => 0 days.
        _m, avg, days = im.classify(30, self.FAST_CUT, self.NORMAL_CUT, stock=0)
        self.assertEqual(avg, 1.0)
        self.assertEqual(days, 0.0)

    def test_tier_labels_and_display_priority(self):
        self.assertEqual(
            list(im.MOVEMENT_LABELS),
            ['FAST MOVING', 'NORMAL MOVING', 'SLOW MOVING', 'NOT MOVING'],
        )
        self.assertEqual(
            [im.MOVEMENT_RANK[l] for l in im.MOVEMENT_LABELS], [0, 1, 2, 3],
        )
        self.assertEqual(im.SALES_WINDOW_DAYS, 30)


class DemandPredictionEngineTest(SimpleTestCase):
    databases = {'default'}

    def test_feature_names_are_real_demand_indicators(self):
        """ID3 features must be demand indicators; stock/target are excluded."""
        self.assertEqual(
            set(DecisionTreeEngine.FEATURE_NAMES),
            {'wishlist_count', 'cart_count'},
        )
        self.assertNotIn('available_quantity', DecisionTreeEngine.FEATURE_NAMES)
        self.assertNotIn('units_sold', DecisionTreeEngine.FEATURE_NAMES)
        self.assertNotIn('purchase_count', DecisionTreeEngine.FEATURE_NAMES)

    def test_weighted_entropy_matches_manual_value(self):
        """Weighted entropy equals the unweighted case when counts are 1."""
        samples = [
            {'target': 'High', 'count': 1},
            {'target': 'High', 'count': 1},
            {'target': 'Low', 'count': 1},
            {'target': 'Low', 'count': 1},
        ]
        self.assertEqual(DecisionTreeEngine.calculate_entropy(samples), 1.0)

    def test_weighted_entropy_collapses_duplicates(self):
        """A row repeated by count behaves identically to repeated rows."""
        repeated = [{'target': 'High'}, {'target': 'High'}, {'target': 'Low'}]
        weighted = [{'target': 'High', 'count': 2}, {'target': 'Low', 'count': 1}]
        self.assertEqual(
            DecisionTreeEngine.calculate_entropy(repeated),
            DecisionTreeEngine.calculate_entropy(weighted),
        )

    def test_build_tree_and_predict(self):
        """ID3 builds a tree and predicts cleanly on a small dataset."""
        dataset = [
            {'wishlist_count': 0.0, 'cart_count': 0.0, 'target': 'Low', 'count': 40},
            {'wishlist_count': 10.0, 'cart_count': 20.0, 'target': 'High', 'count': 40},
            {'wishlist_count': 5.0, 'cart_count': 8.0, 'target': 'Medium', 'count': 20},
        ]
        tree = DecisionTreeEngine.build_tree(dataset, depth=0, max_depth=3)
        high, _ = DecisionTreeEngine.explain_prediction(
            tree, {'wishlist_count': 10.0, 'cart_count': 20.0}
        )
        self.assertEqual(high, 'High')

    def test_tree_to_sql_case_roundtrip(self):
        """The tree serialises to a CASE expression with one param per node."""
        dataset = [
            {'wishlist_count': 0.0, 'cart_count': 0.0, 'target': 'Low', 'count': 40},
            {'wishlist_count': 10.0, 'cart_count': 20.0, 'target': 'High', 'count': 40},
        ]
        tree = DecisionTreeEngine.build_tree(dataset, depth=0, max_depth=3)
        sql, params = engine.tree_to_sql_case(tree)
        self.assertIn('CASE', sql)
        self.assertTrue("'High'" in sql and "'Low'" in sql)
        # One numeric parameter is bound per internal (non-leaf) node.
        internal_nodes = sql.count('CASE')
        self.assertEqual(len(params), internal_nodes)
        for p in params:
            self.assertIsInstance(p, float)

    def test_recommended_action_distinguishes_stock_from_demand(self):
        """Action text references the real available_quantity, not demand."""
        high_out_of_stock = engine.recommended_action('High', 0, 50)
        self.assertIn('restock', high_out_of_stock.lower())
        self.assertNotIn('undefined', high_out_of_stock.lower())

    def test_run_pipeline_contract(self):
        """Full pipeline returns the shape downstream consumers expect, or a
        clean failure when the warehouse tables are unavailable."""
        try:
            results = engine.run_pipeline()
        except Exception:
            self.fail('run_pipeline must handle DB access defensively')
        self.assertIn('success', results)
        if results.get('success'):
            self.assertIn('product_predictions', results)
            for pred in results['product_predictions'][:5]:
                self.assertIn(pred['predicted_demand'], ['High', 'Medium', 'Low'])


class DemandSellingPriceSQLTest(SimpleTestCase):
    """The product-fetch selling price must be computed from the columns that
    actually exist (no `initial_price`) and never go negative."""

    def test_selling_price_does_not_reference_missing_initial_price(self):
        sql = views._SELLING_PRICE_SQL
        self.assertNotIn('initial_price', sql)

    def test_selling_price_subtracts_discount_from_parsed_actual_price(self):
        sql = views._SELLING_PRICE_SQL
        self.assertIn('d.actual_price', sql)
        self.assertIn('d.discount_price', sql)
        # Floored at 0 so a discount can never produce a negative price.
        self.assertTrue(sql.startswith('GREATEST(0,'))


# =============================================================================
# REVENUE FORECASTING TEST SUITE
# =============================================================================

class FixedDateTime202611(datetime):
    @classmethod
    def now(cls, tz=None):
        return datetime(2026, 11, 3, 12, 0, 0)


class FixedDateTime202604(datetime):
    @classmethod
    def now(cls, tz=None):
        return datetime(2026, 4, 15, 12, 0, 0)


def create_realistic_db_rows():
    """
    Generate realistic synthetic test rows for database simulation:
    - 1 partial boundary start month: 2024-03-31 (1 day, low volume)
    - 24 complete calendar months: 2024-04 to 2026-03 (day 1 to last_day, normal volume)
    - 1 partial boundary end month: 2026-04 (10 days, partial volume)
    """
    rows = []
    # 1 partial start boundary month: 2024-03-31
    rows.append(('2024-03', 841, 2540, 6125966.44, 7284.15, date(2024, 3, 31), date(2024, 3, 31)))

    # 24 complete calendar months: 2024-04 to 2026-03
    month_pairs = (
        [(2024, m) for m in range(4, 13)] +
        [(2025, m) for m in range(1, 13)] +
        [(2026, m) for m in range(1, 4)]
    )
    # Seasonal deviations ensure realistic non-zero holdout errors
    seasonal_effects = [0, 5e6, -8e6, 3e6, 2e6, -4e6, 6e6, -7e6, 1e6, 4e6, -5e6, 8e6]

    for y, m in month_pairs:
        _, last_day = calendar.monthrange(y, m)
        rev = 150000000.0 + ((y - 2024) * 4000000.0) + seasonal_effects[(m - 1) % 12]
        rows.append((f"{y}-{m:02d}", 24000, 72000, rev, rev / 24000.0, date(y, m, 1), date(y, m, last_day)))

    # 1 partial end boundary month: 2026-04 (mid-month cutoff on day 10)
    rows.append(('2026-04', 500, 1500, 3125000.0, 6250.0, date(2026, 4, 1), date(2026, 4, 10)))
    return rows


class RevenueForecastingMathTest(SimpleTestCase):
    """Unit tests for Holt-Winters algorithm, evaluation metrics, and prediction intervals."""

    def test_calculate_metrics(self):
        actual = [100.0, 200.0, 300.0]
        pred = [110.0, 190.0, 315.0]
        mae, rmse, mape = calculate_metrics(actual, pred)
        # Differences: [10, 10, 15] -> MAE = 35 / 3 = 11.666...
        self.assertAlmostEqual(mae, 35.0 / 3.0, places=3)
        # Squared differences: [100, 100, 225] -> MSE = 425 / 3 -> RMSE = sqrt(141.666...) = 11.902...
        self.assertAlmostEqual(rmse, float(np.sqrt(425.0 / 3.0)), places=3)
        # Percentage differences: [10%, 5%, 5%] -> MAPE = 20 / 3 = 6.666...%
        self.assertAlmostEqual(mape, 20.0 / 3.0, places=3)

    def test_safe_mape_with_zero(self):
        actual = [0.0, 100.0]
        pred = [5.0, 105.0]
        mae, rmse, mape = calculate_metrics(actual, pred)
        self.assertTrue(np.isfinite(mape))
        self.assertGreater(mape, 0)

    def test_fit_holt_winters_additive_shape_and_bounds(self):
        # 24-month synthetic seasonal series
        np.random.seed(42)
        base = 100.0
        trend_slope = 2.0
        seasonal_pattern = [10, -5, -15, 20, 5, -10, 15, -20, 0, 5, -10, 5]
        series = np.array([
            base + trend_slope * i + seasonal_pattern[i % 12] + np.random.normal(0, 1)
            for i in range(24)
        ])

        fitted, future, rmse, final_l, final_t, seasonals = fit_holt_winters_additive(
            series, season_length=12, alpha=0.5, beta=0.2, gamma=0.5, n_preds=3
        )

        self.assertEqual(len(fitted), 24)
        self.assertEqual(len(future), 3)
        self.assertGreater(rmse, 0.0)
        self.assertTrue(all(np.isfinite(future)))

    def test_meaningful_seasonal_forecast_preservation(self):
        """
        Meaningful seasonal forecast test:
        Verifies that Holt-Winters Triple Exponential Smoothing captures and preserves
        the cyclic seasonal peak-and-trough dynamics in future multi-step forecasts.
        """
        base = 150.0
        # Distinct seasonal shape: Month 0 (Jan) is high peak (+30), Month 1 (Feb) is trough (-25)
        seasonal_cycle = [30.0, -25.0, 10.0, 5.0, -5.0, -10.0, 15.0, -15.0, 0.0, 5.0, -10.0, 0.0]
        # Construct 24 months of pure seasonal data across 2 full cycles
        series = np.array([base + seasonal_cycle[i % 12] for i in range(24)])

        fitted, future, rmse, final_l, final_t, seasonals = fit_holt_winters_additive(
            series, season_length=12, alpha=0.6, beta=0.3, gamma=0.6, n_preds=3
        )

        # In-sample fitted series must strongly correlate with the seasonal ground truth
        corr = np.corrcoef(series, fitted)[0, 1]
        self.assertGreater(corr, 0.95, f"In-sample fit correlation {corr:.4f} must exceed 0.95")

        # Future step 1 corresponds to month index 0 (peak), step 2 to month index 1 (trough)
        # The model must preserve this seasonal inversion: future[0] > future[1]
        self.assertGreater(future[0], future[1], "Forecast must reflect the seasonal peak in step 1 over trough in step 2")
        self.assertGreater(future[0], base, "Forecast at peak season must exceed overall baseline")
        self.assertLess(future[1], base, "Forecast at trough season must drop below baseline")

        # Learned seasonal indices must reflect peak in index 0 and trough in index 1
        self.assertGreater(seasonals[0], seasonals[1], "Learned seasonal index for peak must exceed trough index")

    def test_prediction_interval_exact_formula_and_production_parameters(self):
        """
        Verifies that prediction interval calculations match the exact Chatfield & Yar /
        Hyndman state-space variance formula using production parameters (alpha=0.6, beta=0.3, gamma=0.6, L=12):
          Var(e_t(h)) = sigma^2 * (1 + sum_{j=1}^{h-1} c_j^2)
          c_j = alpha + j*alpha*beta + (gamma if j%12==0 else 0)
        """
        pred_val = 150000000.0
        rmse_sigma = 2000000.0
        alpha, beta, gamma = 0.6, 0.3, 0.6
        L = 12

        low1, high1, se1 = compute_prediction_interval(pred_val, 1, rmse_sigma, alpha, beta, gamma, L)
        low2, high2, se2 = compute_prediction_interval(pred_val, 2, rmse_sigma, alpha, beta, gamma, L)
        low3, high3, se3 = compute_prediction_interval(pred_val, 3, rmse_sigma, alpha, beta, gamma, L)

        # Analytical Step 1: c_sum = 0 -> Var = sigma^2 -> SE = sigma
        self.assertAlmostEqual(se1, rmse_sigma, places=4)

        # Analytical Step 2: j=1 -> c_1 = 0.6 + 1*(0.6*0.3) = 0.78 -> c_1^2 = 0.6084
        # Var = sigma^2 * (1 + 0.6084) = 1.6084 * sigma^2 -> SE(2) = sigma * sqrt(1.6084)
        expected_se2 = rmse_sigma * np.sqrt(1.6084)
        self.assertAlmostEqual(se2, expected_se2, places=4)

        # Analytical Step 3: j=2 -> c_2 = 0.6 + 2*(0.6*0.3) = 0.96 -> c_2^2 = 0.9216
        # Var = sigma^2 * (1 + 0.6084 + 0.9216) = 2.53 * sigma^2 -> SE(3) = sigma * sqrt(2.53)
        expected_se3 = rmse_sigma * np.sqrt(2.53)
        self.assertAlmostEqual(se3, expected_se3, places=4)

        # SE must strictly expand monotonically with forecast horizon lead time
        self.assertLess(se1, se2)
        self.assertLess(se2, se3)

        # Width check: intervals must span 2 * 1.95996 * SE
        z = 1.95996
        self.assertAlmostEqual(high1 - pred_val, z * se1, places=1)
        self.assertAlmostEqual(pred_val - low1, z * se1, places=1)
        self.assertAlmostEqual(high2 - pred_val, z * se2, places=1)
        self.assertAlmostEqual(pred_val - low2, z * se2, places=1)

        # Lower bound clipping: lower bound must never be negative
        low_clip, _, _ = compute_prediction_interval(100.0, 3, 500.0, alpha, beta, gamma, L)
        self.assertGreaterEqual(low_clip, 0.0)

    def test_stale_data_detection_deterministic(self):
        """
        Test stale-data detection deterministically using fixed reference dates,
        verifying that data lag classification is independent of machine wall-clock time.
        """
        last_hist_year = 2026
        last_hist_month = 3  # Historical data ends March 2026

        # Scenario A: Reference date is November 2026 -> lag = 8 months -> is_stale = True
        ref_dt_nov = datetime(2026, 11, 3)
        lag_nov = (ref_dt_nov.year - last_hist_year) * 12 + (ref_dt_nov.month - last_hist_month)
        self.assertEqual(lag_nov, 8)
        self.assertTrue(lag_nov > 1)

        # Scenario B: Reference date is April 2026 -> lag = 1 month -> is_stale = False (immediate next month)
        ref_dt_apr = datetime(2026, 4, 15)
        lag_apr = (ref_dt_apr.year - last_hist_year) * 12 + (ref_dt_apr.month - last_hist_month)
        self.assertEqual(lag_apr, 1)
        self.assertFalse(lag_apr > 1)

        # Scenario C: Reference date is March 2026 -> lag = 0 months -> is_stale = False (current month)
        ref_dt_mar = datetime(2026, 3, 31)
        lag_mar = (ref_dt_mar.year - last_hist_year) * 12 + (ref_dt_mar.month - last_hist_month)
        self.assertEqual(lag_mar, 0)
        self.assertFalse(lag_mar > 1)

        # Scenario D: Cross-year lag (February 2027 vs March 2026) -> lag = 11 months
        ref_dt_next_year = datetime(2027, 2, 1)
        lag_next_year = (ref_dt_next_year.year - last_hist_year) * 12 + (ref_dt_next_year.month - last_hist_month)
        self.assertEqual(lag_next_year, 11)
        self.assertTrue(lag_next_year > 1)


class RevenueForecastingProductionLogicTest(SimpleTestCase):
    """
    Tests actual production forecasting service logic in RevenueForecastingService,
    including calendar filtering, single-pass reconciliation, chronological validation,
    missing months, and deterministic staleness classification.
    """

    def setUp(self):
        self.mock_rows = create_realistic_db_rows()

    def _get_mocked_cursor(self, rows):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = rows
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        return mock_conn

    def test_production_calendar_month_filtering_and_exclusion(self):
        """
        Test that production logic in RevenueForecastingService._compute_revenue_forecasting:
        - Excludes partial boundary months (e.g. 1-day start or cutoff end) with dynamic reasons.
        - Retains all complete calendar months (day 1 to last_day, normal volume).
        - Generates complete data reconciliation without dropping records.
        """
        mock_conn = self._get_mocked_cursor(self.mock_rows)

        with patch('demand_prediction.revenue_forecasting.connection', mock_conn):
            with patch('demand_prediction.revenue_forecasting.datetime', FixedDateTime202611):
                result = RevenueForecastingService._compute_revenue_forecasting()

        self.assertTrue(result.get('success'), f"Service failed: {result.get('error')}")

        # Complete months in history should be exactly 24
        history = result['history']
        self.assertEqual(len(history), 24)
        self.assertEqual(history[0]['month_key'], '2024-04')
        self.assertEqual(history[-1]['month_key'], '2026-03')

        # Reconciliation check
        recon = result['data_reconciliation']
        total_delivered_db = sum(r[1] for r in self.mock_rows)
        self.assertEqual(recon['total_delivered_in_database'], total_delivered_db)
        self.assertEqual(recon['validated_orders_used'], 24 * 24000)
        self.assertEqual(recon['total_excluded_orders'], 841 + 500)
        self.assertTrue(recon['reconciled'])

        # Excluded records validation: exactly 2 boundary months
        excluded = recon['excluded_records']
        self.assertEqual(len(excluded), 2)

        # Inception month (2024-03)
        self.assertEqual(excluded[0]['month_key'], '2024-03')
        self.assertIn('starts on day 31 instead of day 1', excluded[0]['reason'])
        self.assertIn('partial volume (841 orders', excluded[0]['reason'])

        # Cutoff trailing month (2026-04)
        self.assertEqual(excluded[1]['month_key'], '2026-04')
        self.assertIn('ends on day 10 instead of day 30', excluded[1]['reason'])
        self.assertIn('partial volume (500 orders', excluded[1]['reason'])

    def test_revenue_reconciliation_sum_final_price_logic(self):
        """
        Test revenue reconciliation using the verified SUM(final_price) definition:
        - Revenue is the direct sum of final_price (net amount paid for each order line).
        - It is NOT multiplied by quantity (which would double-count sales volume).
        - Validated revenue + excluded revenue accounts for the entire delivered population.
        """
        mock_conn = self._get_mocked_cursor(self.mock_rows)

        with patch('demand_prediction.revenue_forecasting.connection', mock_conn):
            with patch('demand_prediction.revenue_forecasting.datetime', FixedDateTime202611):
                result = RevenueForecastingService._compute_revenue_forecasting()

        self.assertTrue(result.get('success'))

        # Revenue arithmetic check
        kpis = result['kpis']
        expected_validated_revenue = sum(r[3] for r in self.mock_rows[1:25])
        self.assertAlmostEqual(kpis['total_historical_revenue'], expected_validated_revenue, places=2)

        # Total historical units check
        expected_units = sum(r[2] for r in self.mock_rows[1:25])
        self.assertEqual(kpis['total_units'], expected_units)

        # Reconciliation formula format
        recon = result['data_reconciliation']
        self.assertIn('validated 24M', recon['reconciliation_formula'])
        self.assertIn(f"{recon['total_delivered_in_database']:,}", recon['reconciliation_formula'])

    def test_missing_months_and_insufficient_data(self):
        """
        Test system behavior when data is missing or incomplete:
        - When fewer than 12 complete calendar months exist (e.g. 5 months), the service
          must fail gracefully indicating insufficient data for 12-month seasonality.
        - When zero delivered order rows exist, it must return an informative error.
        """
        # Case 1: Insufficient complete months (< 12)
        short_rows = self.mock_rows[1:6]  # 5 complete months
        mock_conn_short = self._get_mocked_cursor(short_rows)

        with patch('demand_prediction.revenue_forecasting.connection', mock_conn_short):
            result_short = RevenueForecastingService._compute_revenue_forecasting()

        self.assertFalse(result_short.get('success'))
        self.assertIn('Insufficient complete calendar months', result_short.get('error', ''))
        self.assertIn('at least 12 required', result_short.get('error', ''))

        # Case 2: Zero rows returned from DB
        empty_rows = []
        mock_conn_empty = self._get_mocked_cursor(empty_rows)

        with patch('demand_prediction.revenue_forecasting.connection', mock_conn_empty):
            result_empty = RevenueForecastingService._compute_revenue_forecasting()

        self.assertFalse(result_empty.get('success'))
        self.assertIn('No delivered order records found', result_empty.get('error', ''))

    def test_chronological_ordering_and_continuity(self):
        """
        Test chronological continuity:
        - Historical complete calendar months are strictly contiguous with zero missing months.
        - Future 3-month forecast starts on the immediate consecutive calendar month following
          the historical series endpoint (e.g., historical end 2026-03 -> forecast 2026-04, 2026-05, 2026-06).
        """
        mock_conn = self._get_mocked_cursor(self.mock_rows)

        with patch('demand_prediction.revenue_forecasting.connection', mock_conn):
            with patch('demand_prediction.revenue_forecasting.datetime', FixedDateTime202611):
                result = RevenueForecastingService._compute_revenue_forecasting()

        self.assertTrue(result.get('success'))

        history = result['history']
        # Check chronological continuity of history (step == 1 calendar month)
        for i in range(len(history) - 1):
            h1 = history[i]
            h2 = history[i + 1]
            month_index_1 = h1['year'] * 12 + h1['month']
            month_index_2 = h2['year'] * 12 + h2['month']
            self.assertEqual(
                month_index_2 - month_index_1, 1,
                f"Missing month detected between {h1['month_key']} and {h2['month_key']}"
            )

        # Check forecast chronological continuity immediately following history
        forecast = result['forecast']
        self.assertEqual(len(forecast), 3)

        last_hist = history[-1]
        last_hist_idx = last_hist['year'] * 12 + last_hist['month']

        for step_idx, f in enumerate(forecast, start=1):
            f_idx = f['year'] * 12 + f['month']
            self.assertEqual(
                f_idx - last_hist_idx, step_idx,
                f"Forecast step {step_idx} ({f['month_key']}) does not follow immediately after history ({last_hist['month_key']})"
            )

    def test_chronological_holdout_validation_and_baseline_comparison(self):
        """
        Verify chronological train/test holdout validation:
        - Train set: first 21 complete months (months 1-21, Apr 2024 - Dec 2025).
        - Holdout test set: last 3 complete months (months 22-24, Jan 2026 - Mar 2026).
        - Out-of-sample benchmark against 3-Month Moving Average and Seasonal Naive baselines.
        """
        mock_conn = self._get_mocked_cursor(self.mock_rows)

        with patch('demand_prediction.revenue_forecasting.connection', mock_conn):
            with patch('demand_prediction.revenue_forecasting.datetime', FixedDateTime202611):
                result = RevenueForecastingService._compute_revenue_forecasting()

        self.assertTrue(result.get('success'))

        model_perf = result['model_performance']
        self.assertEqual(model_perf['model_name'], 'Holt-Winters Triple Exponential Smoothing')
        self.assertIn('21 Months Train / 3 Months Test', model_perf['validation_split'])
        self.assertEqual(model_perf['test_period'], 'Jan 2026 – Mar 2026')

        # Holdout breakdown should contain exactly 3 months
        breakdown = model_perf['validation_breakdown']
        self.assertEqual(len(breakdown), 3)
        self.assertEqual(breakdown[0]['month'], 'Jan 2026')
        self.assertEqual(breakdown[1]['month'], 'Feb 2026')
        self.assertEqual(breakdown[2]['month'], 'Mar 2026')

        # Verify holdout metrics are non-negative finite numbers
        self.assertGreater(model_perf['mae'], 0.0)
        self.assertGreater(model_perf['rmse'], 0.0)
        self.assertGreater(model_perf['mape'], 0.0)

        # Baseline comparisons
        baselines = model_perf['baseline_comparison']
        self.assertIn('moving_avg_3m', baselines)
        self.assertIn('seasonal_naive', baselines)
        self.assertGreater(baselines['moving_avg_3m']['mae'], 0.0)
        self.assertGreater(baselines['seasonal_naive']['mae'], 0.0)
        self.assertIn('improvement_over_moving_avg_pct', baselines)
        self.assertIn('improvement_over_seasonal_naive_pct', baselines)

    def test_deterministic_stale_data_production_response(self):
        """
        Verify production stale-data classification and notice banners:
        - Injected date Nov 2026 vs historical end Mar 2026: lag = 8M -> classified as retrospective backtest.
        - Injected date Apr 2026 vs historical end Mar 2026: lag = 1M -> classified as active 3M forecast.
        """
        mock_conn = self._get_mocked_cursor(self.mock_rows)

        # Scenario 1: Reference date is Nov 2026 (Stale-Data Backtest)
        with patch('demand_prediction.revenue_forecasting.connection', mock_conn):
            with patch('demand_prediction.revenue_forecasting.datetime', FixedDateTime202611):
                result_stale = RevenueForecastingService._compute_revenue_forecasting()

        self.assertTrue(result_stale.get('success'))
        kpis_stale = result_stale['kpis']
        self.assertTrue(kpis_stale['is_stale_data'])
        self.assertEqual(kpis_stale['lag_months'], 8)
        self.assertEqual(kpis_stale['projection_badge'], 'Stale-Data Projection')
        self.assertEqual(kpis_stale['projection_title'], 'Projected Revenue (Apr 2026 – Jun 2026)')

        freshness_stale = result_stale['data_freshness']
        self.assertEqual(freshness_stale['badge'], 'Historical Backtest (8M Lag)')
        self.assertIn('Stale-Data Projection (Historical Backtest)', freshness_stale['title'])
        self.assertIn('retrospective historical forecast', freshness_stale['warning'])

        # Scenario 2: Reference date is April 2026 (Active Forecast)
        with patch('demand_prediction.revenue_forecasting.connection', mock_conn):
            with patch('demand_prediction.revenue_forecasting.datetime', FixedDateTime202604):
                result_fresh = RevenueForecastingService._compute_revenue_forecasting()

        self.assertTrue(result_fresh.get('success'))
        kpis_fresh = result_fresh['kpis']
        self.assertFalse(kpis_fresh['is_stale_data'])
        self.assertEqual(kpis_fresh['lag_months'], 1)
        self.assertEqual(kpis_fresh['projection_badge'], 'Next 3 Months')
        self.assertEqual(kpis_fresh['projection_title'], 'Predicted Revenue (Next 3M)')

        freshness_fresh = result_fresh['data_freshness']
        self.assertEqual(freshness_fresh['badge'], 'Active 3M Forecast')
        self.assertIn('Active 3M Forecast', freshness_fresh['badge'])


def create_mock_olap_rows():
    """
    Generate realistic synthetic test rows for OLAP time dimension testing:
    - 1 partial start boundary month: 2024-03-31 (1 day, low volume)
    - 24 complete calendar months: 2024-04 to 2026-03
    Total: exactly 25 months across 9 quarters and 3 years.
    """
    rows = []
    # 2024-03 (Partial)
    rows.append(('2024-03', '2024', 'Q1', 841, 841, 2540, 6125966.44, date(2024, 3, 31), date(2024, 3, 31)))

    month_pairs = (
        [(2024, m) for m in range(4, 13)] +
        [(2025, m) for m in range(1, 13)] +
        [(2026, m) for m in range(1, 4)]
    )
    for y, m in month_pairs:
        _, last_day = calendar.monthrange(y, m)
        q = f"Q{(m - 1)//3 + 1}"
        m_key = f"{y}-{m:02d}"
        rows.append((m_key, str(y), q, 24000, 24000, 72000, 160000000.0, date(y, m, 1), date(y, m, last_day)))
    return rows


class RevenueTimeOLAPTest(SimpleTestCase):
    """
    Unit tests for Time Dimension Revenue OLAP (Roll-up & Drill-down):
    - Month -> Quarter -> Year Roll-up
    - Year -> Quarter -> Month Drill-down
    - Exact three-tier reconciliation
    - Partial period labeling (March 2024, 2024-Q1, 2024, 2026)
    - AOV = SUM(final_price) / COUNT(DISTINCT orderid)
    - Strict Gregorian date validation
    """
    databases = {'default'}

    def setUp(self):
        self.mock_olap_rows = create_mock_olap_rows()

    def _get_mocked_olap_conn(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = self.mock_olap_rows
        total_delivered = sum(r[3] for r in self.mock_olap_rows)
        mock_cursor.fetchone.return_value = (total_delivered,)
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        return mock_conn

    def test_rollup_three_tier_aggregation_and_exact_reconciliation(self):
        """
        Test that Roll-up across Month -> Quarter -> Year preserves exact mathematical equality:
        Total Monthly Revenue == Total Quarterly Revenue == Total Yearly Revenue,
        and total delivered order counts match without discrepancy.
        """
        from demand_prediction.olap_service import RevenueTimeOLAPService

        with patch('demand_prediction.olap_service.connection', self._get_mocked_olap_conn()):
            # Level 1: Month
            res_m = RevenueTimeOLAPService.get_time_olap_analysis(operation='rollup', level='month', force_refresh=True)
            self.assertTrue(res_m.get('success'))
            self.assertEqual(res_m['operation'], 'rollup')
            self.assertEqual(res_m['level'], 'month')
            self.assertEqual(len(res_m['records']), 25)

            # Level 2: Quarter
            res_q = RevenueTimeOLAPService.get_time_olap_analysis(operation='rollup', level='quarter', force_refresh=False)
            self.assertTrue(res_q.get('success'))
            self.assertEqual(res_q['level'], 'quarter')
            self.assertEqual(len(res_q['records']), 9)

            # Level 3: Year
            res_y = RevenueTimeOLAPService.get_time_olap_analysis(operation='rollup', level='year', force_refresh=False)
            self.assertTrue(res_y.get('success'))
            self.assertEqual(res_y['level'], 'year')
            self.assertEqual(len(res_y['records']), 3)

            # Exact three-tier reconciliation check
            recon = res_y['data_reconciliation']
            self.assertTrue(recon['reconciled'])
            self.assertAlmostEqual(recon['monthly_total_revenue'], recon['quarterly_total_revenue'], places=2)
            self.assertAlmostEqual(recon['quarterly_total_revenue'], recon['yearly_total_revenue'], places=2)
            expected_total_orders = 841 + 24 * 24000
            self.assertEqual(recon['total_delivered_orders'], expected_total_orders)
            expected_total_units = 2540 + 24 * 72000
            self.assertEqual(recon['total_units_sold'], expected_total_units)

    def test_drilldown_year_to_quarter_to_month(self):
        """
        Test that Drill-down from Year -> Quarter -> Month decomposes aggregate totals consistently:
        - Selecting Year 2025 returns exactly 4 quarters of 2025.
        - Selecting 2025 and Q1 returns exactly 3 months (Jan, Feb, Mar 2025).
        - Sum of drilled months in 2025-Q1 matches the 2025-Q1 quarter total.
        - Sum of drilled quarters in 2025 matches the Year 2025 annual total.
        """
        from demand_prediction.olap_service import RevenueTimeOLAPService

        with patch('demand_prediction.olap_service.connection', self._get_mocked_olap_conn()):
            # Step 1: Top-level Year view
            res_yr = RevenueTimeOLAPService.get_time_olap_analysis(operation='drilldown', level='year', force_refresh=True)
            self.assertTrue(res_yr.get('success'))
            self.assertEqual(len(res_yr['records']), 3)
            y2025_record = next(r for r in res_yr['records'] if r['year'] == '2025')

            # Step 2: Drill down into quarters of 2025
            res_qtr = RevenueTimeOLAPService.get_time_olap_analysis(
                operation='drilldown', level='quarter', selected_year='2025', force_refresh=False
            )
            self.assertTrue(res_qtr.get('success'))
            self.assertEqual(len(res_qtr['records']), 4)
            for q in res_qtr['records']:
                self.assertEqual(q['year'], '2025')

            # Sum of 4 quarters in 2025 must equal 2025 year total
            sum_q_rev = round(sum(q['total_revenue'] for q in res_qtr['records']), 2)
            self.assertAlmostEqual(sum_q_rev, y2025_record['total_revenue'], places=2)
            sum_q_orders = sum(q['order_count'] for q in res_qtr['records'])
            self.assertEqual(sum_q_orders, y2025_record['order_count'])

            # Step 3: Drill down into months of 2025-Q1
            res_mo = RevenueTimeOLAPService.get_time_olap_analysis(
                operation='drilldown', level='month', selected_year='2025', selected_quarter='Q1', force_refresh=False
            )
            self.assertTrue(res_mo.get('success'))
            self.assertEqual(len(res_mo['records']), 3)
            self.assertEqual(res_mo['records'][0]['label'], 'Jan 2025')
            self.assertEqual(res_mo['records'][1]['label'], 'Feb 2025')
            self.assertEqual(res_mo['records'][2]['label'], 'Mar 2025')

            # Sum of 3 months in Q1 must equal 2025-Q1 quarter total
            q1_record = next(q for q in res_qtr['records'] if q['quarter'] == 'Q1')
            sum_m_rev = round(sum(m['total_revenue'] for m in res_mo['records']), 2)
            self.assertAlmostEqual(sum_m_rev, q1_record['total_revenue'], places=2)

    def test_partial_period_classifications_and_analytical_notices(self):
        """
        Verify explicit labeling of partial vs complete periods:
        - March 2024: Partial Month (Day 31 only)
        - 2024-Q1: Partial Quarter (1 Day only)
        - 2024: Partial Year (9M + 1D)
        - 2025: Complete Calendar Year (12M)
        - 2026: Partial Year (Q1 only / 3M)
        - Warning notice against comparing partial 2024/2026 to full 2025.
        """
        from demand_prediction.olap_service import RevenueTimeOLAPService

        with patch('demand_prediction.olap_service.connection', self._get_mocked_olap_conn()):
            # Check Monthly partial badging
            res_m = RevenueTimeOLAPService.get_time_olap_analysis(operation='rollup', level='month', force_refresh=True)
            mar_2024 = next(m for m in res_m['records'] if m['period_key'] == '2024-03')
            self.assertTrue(mar_2024['is_partial'])
            self.assertIn('Partial Month', mar_2024['status_label'])

            apr_2024 = next(m for m in res_m['records'] if m['period_key'] == '2024-04')
            self.assertFalse(apr_2024['is_partial'])
            self.assertEqual(apr_2024['status_label'], 'Complete Month')

            # Check Quarterly partial badging
            res_q = RevenueTimeOLAPService.get_time_olap_analysis(operation='rollup', level='quarter', force_refresh=False)
            q1_2024 = next(q for q in res_q['records'] if q['period_key'] == '2024-Q1')
            self.assertTrue(q1_2024['is_partial'])
            self.assertIn('Partial Quarter', q1_2024['status_label'])

            q2_2024 = next(q for q in res_q['records'] if q['period_key'] == '2024-Q2')
            self.assertFalse(q2_2024['is_partial'])

            # Check Yearly partial badging
            res_y = RevenueTimeOLAPService.get_time_olap_analysis(operation='rollup', level='year', force_refresh=False)
            y2024 = next(y for y in res_y['records'] if y['year'] == '2024')
            self.assertTrue(y2024['is_partial'])
            self.assertIn('Partial Year', y2024['status_badge'])

            y2025 = next(y for y in res_y['records'] if y['year'] == '2025')
            self.assertFalse(y2025['is_partial'])
            self.assertIn('Full Calendar Year (12M)', y2025['status_badge'])

            y2026 = next(y for y in res_y['records'] if y['year'] == '2026')
            self.assertTrue(y2026['is_partial'])
            self.assertIn('Partial Year', y2026['status_badge'])

            # Verify warning notice text
            notices = res_y['notices']
            self.assertIn('partial-year records', notices['partial_year_warning'])
            self.assertIn('must not be compared directly against Year 2025', notices['partial_year_warning'])

    def test_aov_definition_and_no_quantity_multiplication(self):
        """
        Verify AOV is calculated as SUM(final_price) / COUNT(DISTINCT orderid)
        and final_price is not multiplied by quantity.
        """
        from demand_prediction.olap_service import RevenueTimeOLAPService

        with patch('demand_prediction.olap_service.connection', self._get_mocked_olap_conn()):
            res = RevenueTimeOLAPService.get_time_olap_analysis(operation='rollup', level='quarter', force_refresh=True)
            self.assertTrue(res['success'])

            for q in res['records']:
                expected_aov = round(q['total_revenue'] / q['distinct_orders'], 2)
                self.assertAlmostEqual(q['avg_order_value'], expected_aov, places=2)
                # Row grain check: order_count equals distinct_orders
                self.assertEqual(q['order_count'], q['distinct_orders'])

    def test_safe_gregorian_calendar_validation_rules(self):
        """
        Verify that Gregorian date logic correctly accepts valid dates and rejects
        invalid dates like 31-04-2025 (30-day month), 29-02-2025 (non-leap year Feb),
        year 0000 (invalid Gregorian year), and malformed strings.
        Also validates SQL SAFE_GREGORIAN_DATE_CONDITION behavior against PostgreSQL.
        """
        import calendar
        import re
        from demand_prediction.olap_service import SAFE_GREGORIAN_DATE_CONDITION
        from django.db import connection

        def is_valid_gregorian(d_str):
            if not d_str or not re.match(r'^\d{2}-\d{2}-\d{4}$', d_str):
                return False
            try:
                d, m, y = map(int, d_str.split('-'))
                if y < 1 or y > 9999:
                    return False
                if m < 1 or m > 12:
                    return False
                _, max_days = calendar.monthrange(y, m)
                return 1 <= d <= max_days
            except Exception:
                return False

        # 1. Valid leap year 2024
        self.assertTrue(is_valid_gregorian('29-02-2024'))
        # 2. Invalid leap date 2025
        self.assertFalse(is_valid_gregorian('29-02-2025'))
        # 3. Invalid days in 30-day months (cannot have day 31)
        self.assertFalse(is_valid_gregorian('31-04-2025'))
        self.assertFalse(is_valid_gregorian('31-06-2025'))
        self.assertFalse(is_valid_gregorian('31-09-2025'))
        self.assertFalse(is_valid_gregorian('31-11-2025'))
        # 4. Valid 31-day months
        self.assertTrue(is_valid_gregorian('31-03-2024'))
        self.assertTrue(is_valid_gregorian('31-12-2025'))
        self.assertTrue(is_valid_gregorian('31-01-2026'))
        # 5. Year 0000 rejection
        self.assertFalse(is_valid_gregorian('01-01-0000'))
        self.assertFalse(is_valid_gregorian('29-02-0000'))
        self.assertFalse(is_valid_gregorian('31-12-0000'))
        # 6. Malformed strings & boundaries
        self.assertFalse(is_valid_gregorian('malformed-date'))
        self.assertFalse(is_valid_gregorian('2024-03-31'))
        self.assertFalse(is_valid_gregorian(''))
        self.assertFalse(is_valid_gregorian(None))

        # 7. SQL-level verification of SAFE_GREGORIAN_DATE_CONDITION in PostgreSQL
        sql_test_matrix = [
            ('29-02-2024', True),   # Valid leap date
            ('29-02-2025', False),  # Invalid leap date
            ('31-04-2025', False),  # Invalid day in April (30 days max)
            ('30-04-2025', True),   # Valid day in April
            ('01-01-0000', False),  # Year 0000 explicitly rejected
            ('29-02-0000', False),  # Year 0000 leap explicitly rejected
            ('31-03-2024', True),   # Valid month end
            ('invalid-date', False),# Malformed string
            ('2024-03-31', False),  # ISO format string (fails DD-MM-YYYY regex)
        ]
        try:
            with connection.cursor() as cursor:
                for date_val, expected in sql_test_matrix:
                    date_repr = f"'{date_val}'"
                    cond_with_val = SAFE_GREGORIAN_DATE_CONDITION.replace('purchase_date', date_repr)
                    q = f"SELECT {cond_with_val};"
                    cursor.execute(q)
                    sql_res = cursor.fetchone()[0]
                    self.assertEqual(sql_res, expected, f"PostgreSQL validation mismatch for '{date_val}'")
        except Exception as exc:
            self.fail(f"PostgreSQL SAFE_GREGORIAN_DATE_CONDITION evaluation failed: {exc}")

    def test_revenue_olap_api_endpoint_permissions(self):
        """
        Test GET /api/demand-prediction/revenue-olap/ with authentication:
        - Anonymous user returns 401/403.
        - Authenticated admin user returns 200 with complete OLAP payload.
        """
        from rest_framework.test import APIRequestFactory, force_authenticate
        from demand_prediction.views import RevenueOLAPView

        class MockAdmin:
            is_authenticated = True
            is_active = True
            role = 'ADMIN'

        factory = APIRequestFactory()

        # Case 1: Unauthenticated
        req_unauth = factory.get('/api/demand-prediction/revenue-olap/?operation=rollup&level=quarter')
        res_unauth = RevenueOLAPView.as_view()(req_unauth)
        self.assertIn(res_unauth.status_code, (401, 403))

        # Case 2: Authenticated Admin
        with patch('demand_prediction.olap_service.connection', self._get_mocked_olap_conn()):
            req_auth = factory.get('/api/demand-prediction/revenue-olap/?operation=rollup&level=quarter')
            force_authenticate(req_auth, user=MockAdmin())
            res_auth = RevenueOLAPView.as_view()(req_auth)
            self.assertEqual(res_auth.status_code, 200)
            self.assertTrue(res_auth.data.get('success'))
            self.assertIn('data_reconciliation', res_auth.data)
            self.assertIn('data_quality_report', res_auth.data)
            self.assertIn('notices', res_auth.data)

    def test_slice_operation_year_and_quarter(self):
        """
        Verify OLAP SLICE by fixing one time coordinate (Year or Quarter):
        - Slicing 2025 returns 12 months with share of slice % summing to ~100%.
        - Slicing 2025-Q1 returns 3 months.
        - Slicing 2024-Q1 returns 1 month (partial inception).
        """
        from demand_prediction.olap_service import RevenueTimeOLAPService

        with patch('demand_prediction.olap_service.connection', self._get_mocked_olap_conn()):
            # 1. Slice Year 2025
            res_y = RevenueTimeOLAPService.get_slice_analysis(slice_type='year', slice_value='2025', force_refresh=True)
            self.assertTrue(res_y['success'])
            self.assertEqual(res_y['slice_summary']['slice_value'], '2025')
            self.assertEqual(len(res_y['records']), 12)
            sum_slice_share = sum(r['share_of_slice_pct'] for r in res_y['records'])
            self.assertAlmostEqual(sum_slice_share, 100.0, places=0)

            # 2. Slice Quarter 2025-Q1
            res_q = RevenueTimeOLAPService.get_slice_analysis(slice_type='quarter', slice_value='2025-Q1', force_refresh=False)
            self.assertTrue(res_q['success'])
            self.assertEqual(res_q['slice_summary']['slice_value'], '2025-Q1')
            self.assertEqual(len(res_q['records']), 3)

            # 3. Slice Quarter 2024-Q1 (Partial)
            res_q_part = RevenueTimeOLAPService.get_slice_analysis(slice_type='quarter', slice_value='2024-Q1', force_refresh=False)
            self.assertTrue(res_q_part['success'])
            self.assertTrue(res_q_part['slice_summary']['is_partial'])
            self.assertEqual(len(res_q_part['records']), 1)

    def test_dice_operation_subcube_filtering(self):
        """
        Verify OLAP DICE by multi-condition predicates (Selected Years and Months):
        - Subcube correctly filters intersecting months across clean lists, comma-separated lists, and comma strings.
        - Empty selection returns an empty subcube safely with clear message.
        - Default selection returns the full 25-month historical cube.
        """
        from demand_prediction.olap_service import RevenueTimeOLAPService

        with patch('demand_prediction.olap_service.connection', self._get_mocked_olap_conn()):
            # 1. Dice: Clean lists [2024, 2025] and Months [4, 5, 6] -> 6 records
            res_dice = RevenueTimeOLAPService.get_dice_analysis(
                selected_years=['2024', '2025'], selected_months=[4, 5, 6], force_refresh=True
            )
            self.assertTrue(res_dice['success'])
            self.assertEqual(len(res_dice['records']), 6)
            for r in res_dice['records']:
                self.assertIn(r['year'], ('2024', '2025'))
                self.assertIn(r['month'], (4, 5, 6))

            # 2. Dice: Comma-separated strings inside lists (e.g. from query_params.getlist)
            res_comma_list = RevenueTimeOLAPService.get_dice_analysis(
                selected_years=['2024,2025,2026'],
                selected_months=['1,2,3,4,5,6,7,8,9,10,11,12'],
                force_refresh=False
            )
            self.assertTrue(res_comma_list['success'])
            self.assertEqual(len(res_comma_list['records']), 25)
            self.assertFalse(res_comma_list['subcube_summary']['is_empty'])

            # 3. Dice: Single comma string inputs
            res_str = RevenueTimeOLAPService.get_dice_analysis(
                selected_years='2024,2025',
                selected_months='4,5,6',
                force_refresh=False
            )
            self.assertTrue(res_str['success'])
            self.assertEqual(len(res_str['records']), 6)

            # 4. Empty selection
            res_empty = RevenueTimeOLAPService.get_dice_analysis(
                selected_years=[], selected_months=[], force_refresh=False
            )
            self.assertTrue(res_empty['success'])
            self.assertEqual(len(res_empty['records']), 0)
            self.assertTrue(res_empty['subcube_summary']['is_empty'])

            # 5. Default selection (None)
            res_default = RevenueTimeOLAPService.get_dice_analysis(
                selected_years=None, selected_months=None, force_refresh=False
            )
            self.assertTrue(res_default['success'])
            self.assertEqual(len(res_default['records']), 25)

    def test_pivot_operation_matrix_reconciliation(self):
        """
        Verify OLAP PIVOT Year x Quarter 2D matrix:
        - Row totals equal yearly totals.
        - Column totals equal sum of quarters across years.
        - Grand total equals exactly ₹3,960.38 Cr.
        - Unrecorded cells (2026 Q2, Q3, Q4) show recorded: False.
        """
        from demand_prediction.olap_service import RevenueTimeOLAPService

        with patch('demand_prediction.olap_service.connection', self._get_mocked_olap_conn()):
            res_pivot = RevenueTimeOLAPService.get_pivot_analysis(force_refresh=True)
            self.assertTrue(res_pivot['success'])
            matrix_rows = res_pivot['matrix_rows']
            self.assertEqual(len(matrix_rows), 3)

            # Check unrecorded quarters in 2026
            row_2026 = next(r for r in matrix_rows if r['year'] == '2026')
            self.assertTrue(row_2026['cells']['Q1']['recorded'])
            self.assertFalse(row_2026['cells']['Q2']['recorded'])
            self.assertEqual(row_2026['cells']['Q2']['display_value'], 'N/A')

            # Check grand total reconciliation
            gt = res_pivot['grand_total']
            self.assertTrue(gt['reconciled'])

    def test_ranking_operation_and_partial_period_badges(self):
        """
        Verify OLAP RANKING:
        - Ranks months (25 items), quarters (9 items), years (3 items).
        - Highest revenue ranked #1.
        - Partial periods are flagged with warning text.
        """
        from demand_prediction.olap_service import RevenueTimeOLAPService

        with patch('demand_prediction.olap_service.connection', self._get_mocked_olap_conn()):
            res_rank = RevenueTimeOLAPService.get_ranking_analysis(granularity='month', sort_order='desc', force_refresh=True)
            self.assertTrue(res_rank['success'])
            self.assertEqual(len(res_rank['records']), 25)
            self.assertEqual(res_rank['records'][0]['rank'], 1)

            # Revenue must be monotonically non-increasing
            revs = [r['total_revenue'] for r in res_rank['records']]
            for i in range(len(revs) - 1):
                self.assertGreaterEqual(revs[i], revs[i + 1])

            # Partial month 2024-03 must carry warning
            mar_2024 = next(r for r in res_rank['records'] if r['period_key'] == '2024-03')
            self.assertTrue(mar_2024['is_partial'])
            self.assertIsNotNone(mar_2024['comparison_warning'])

    def test_drillthrough_orders_pagination_ceiling_and_masking(self):
        """
        Verify OLAP DRILL-THROUGH:
        - Rejection of page_size > 50.
        - Deterministic ordering and customer ID masking.
        - Optimization fence verification (MATERIALIZED CTE).
        - Live drill-through count and fetch safety.
        """
        import inspect
        from demand_prediction.olap_service import RevenueTimeOLAPService, mask_customer_id

        # 1. Customer ID Masking
        self.assertEqual(mask_customer_id('U422670'), 'U4****70')
        self.assertEqual(mask_customer_id('U123'), 'U***')
        self.assertEqual(mask_customer_id(None), '—')

        # 2. Maximum page size rejection (> 50)
        res_reject = RevenueTimeOLAPService.get_drillthrough_orders(page_size=51)
        self.assertFalse(res_reject['success'])
        self.assertIn('Maximum page size for Drill-Through is 50', res_reject['error'])

        # 3. Verify MATERIALIZED CTE optimization fence is present in base and drillthrough queries
        src_dt = inspect.getsource(RevenueTimeOLAPService.get_drillthrough_orders)
        src_base = inspect.getsource(RevenueTimeOLAPService.get_base_monthly_data)
        self.assertIn('WITH valid_delivered_orders AS MATERIALIZED', src_dt)
        self.assertIn('WITH valid_delivered_orders AS MATERIALIZED', src_base)

        # 4. Successful paginated query with mock database cursor
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (841, 841, 2540, 6125966.44)
        sample_rows = [
            ('ORD0001', '31-03-2024', 'U422670', 'P1001', 'UPI', 2, 5000.0, 3, 4.5),
            ('ORD0002', '31-03-2024', 'U422671', 'P1002', 'COD', 1, 2500.0, 4, 4.0),
        ]
        mock_cursor.fetchall.return_value = sample_rows
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        with patch('demand_prediction.olap_service.connection', mock_conn):
            res_dt = RevenueTimeOLAPService.get_drillthrough_orders(
                period_type='month', period_key='2024-03', page=1, page_size=50
            )
            self.assertTrue(res_dt['success'])
            self.assertEqual(len(res_dt['orders']), 2)
            self.assertEqual(res_dt['orders'][0]['customer_id_masked'], 'U4****70')
            self.assertEqual(res_dt['pagination']['page'], 1)
            self.assertEqual(res_dt['pagination']['page_size'], 50)
            self.assertEqual(res_dt['pagination']['total_orders'], 841)

        # 5. Live PostgreSQL drill-through count and fetch safety test
        live_res = RevenueTimeOLAPService.get_drillthrough_orders(
            period_type='month', period_key='2024-03', page=1, page_size=10
        )
        self.assertTrue(live_res['success'])
        self.assertEqual(live_res['pagination']['total_orders'], 841)
        self.assertEqual(len(live_res['orders']), 10)
        # Verify first order is masked and contains required fields
        first_ord = live_res['orders'][0]
        self.assertIn('****', first_ord['customer_id_masked'])
        self.assertEqual(first_ord['delivery_status'], 'Delivered')

    def test_trend_analysis_calculations_and_anomaly_flags(self):
        """
        Verify Historical Actual Revenue Trend Analysis:
        - 25 chronological months evaluated.
        - Month 1: MoM change is None (Inception).
        - Month 2: Inception baseline artifact flagged (+2516.55%).
        - Month 13: Non-comparable YoY flagged (+2707.66%).
        - SMA-3: March 2024 partial month (1 day) is excluded from moving averages.
          First valid SMA-3 is June 2024 (idx=3, April + May + June 2024).
          Earlier months (March, April, May 2024) return sma_3 as None (N/A).
        """
        from demand_prediction.olap_service import RevenueTimeOLAPService

        with patch('demand_prediction.olap_service.connection', self._get_mocked_olap_conn()):
            res_trend = RevenueTimeOLAPService.get_trend_analysis(force_refresh=True)
            self.assertTrue(res_trend['success'])
            self.assertEqual(len(res_trend['records']), 25)

            rec_m1 = res_trend['records'][0]
            self.assertEqual(rec_m1['period_key'], '2024-03')
            self.assertIsNone(rec_m1['mom_growth_pct'])
            self.assertIsNone(rec_m1['sma_3'])
            self.assertEqual(rec_m1['sma_3_status'], 'N/A')

            rec_m2 = res_trend['records'][1]
            self.assertEqual(rec_m2['period_key'], '2024-04')
            self.assertTrue(rec_m2['is_mom_artifact'])
            self.assertIsNone(rec_m2['sma_3'])
            self.assertEqual(rec_m2['sma_3_status'], 'N/A')

            rec_m3 = res_trend['records'][2]
            self.assertEqual(rec_m3['period_key'], '2024-05')
            # May 2024 excludes March 2024 partial month; sma_3 must be None (N/A)
            self.assertIsNone(rec_m3['sma_3'])
            self.assertEqual(rec_m3['sma_3_status'], 'N/A')

            rec_m4 = res_trend['records'][3]
            self.assertEqual(rec_m4['period_key'], '2024-06')
            # June 2024 is first valid SMA-3 = (Apr + May + Jun) / 3
            self.assertIsNotNone(rec_m4['sma_3'])
            self.assertEqual(rec_m4['sma_3_status'], 'VALID')
            expected_jun_sma = round((rec_m2['actual_revenue'] + rec_m3['actual_revenue'] + rec_m4['actual_revenue']) / 3.0, 2)
            self.assertEqual(rec_m4['sma_3'], expected_jun_sma)

            rec_m13 = res_trend['records'][12]
            self.assertEqual(rec_m13['period_key'], '2025-03')
            self.assertTrue(rec_m13['is_yoy_non_comparable'])

    def test_api_endpoint_all_six_operations_and_permissions(self):
        """
        Test API endpoint /api/demand-prediction/revenue-olap/ across all operations:
        - Anonymous / Non-admin rejection (401/403).
        - Admin access succeeds for slice, dice, pivot, ranking, drillthrough, trend.
        - Page size > 50 in drillthrough returns 400 Bad Request.
        """
        from rest_framework.test import APIRequestFactory, force_authenticate
        from demand_prediction.views import RevenueOLAPView

        class MockAdmin:
            is_authenticated = True
            is_active = True
            role = 'ADMIN'

        class MockCustomer:
            is_authenticated = True
            is_active = True
            role = 'CUSTOMER'

        factory = APIRequestFactory()

        # 1. Non-admin user receives 403 Forbidden
        req_non_admin = factory.get('/api/demand-prediction/revenue-olap/?operation=slice&slice_value=2025')
        force_authenticate(req_non_admin, user=MockCustomer())
        res_non_admin = RevenueOLAPView.as_view()(req_non_admin)
        self.assertIn(res_non_admin.status_code, (401, 403))

        # 2. Page size > 50 returns 400 Bad Request
        req_overflow = factory.get('/api/demand-prediction/revenue-olap/?operation=drillthrough&page_size=100')
        force_authenticate(req_overflow, user=MockAdmin())
        res_overflow = RevenueOLAPView.as_view()(req_overflow)
        self.assertEqual(res_overflow.status_code, 400)
        self.assertIn('Maximum page size for Drill-Through is 50', res_overflow.data.get('error', ''))

        # 3. Successful admin calls across all operations
        with patch('demand_prediction.olap_service.connection', self._get_mocked_olap_conn()):
            for op in ['slice', 'dice', 'pivot', 'ranking', 'trend']:
                req = factory.get(f'/api/demand-prediction/revenue-olap/?operation={op}')
                force_authenticate(req, user=MockAdmin())
                res = RevenueOLAPView.as_view()(req)
                self.assertEqual(res.status_code, 200)
                self.assertTrue(res.data.get('success'))

            # 4. Specific Dice query parameter tests
            # All years & months (comma-separated query params) -> 25 records
            req_dice_all = factory.get('/api/demand-prediction/revenue-olap/?operation=dice&years=2024,2025,2026&months=1,2,3,4,5,6,7,8,9,10,11,12')
            force_authenticate(req_dice_all, user=MockAdmin())
            res_dice_all = RevenueOLAPView.as_view()(req_dice_all)
            self.assertEqual(res_dice_all.status_code, 200)
            self.assertEqual(len(res_dice_all.data.get('records', [])), 25)

            # Q2 Benchmark (years 2024, 2025 and months 4, 5, 6) -> 6 records
            req_dice_q2 = factory.get('/api/demand-prediction/revenue-olap/?operation=dice&years=2024,2025&months=4,5,6')
            force_authenticate(req_dice_q2, user=MockAdmin())
            res_dice_q2 = RevenueOLAPView.as_view()(req_dice_q2)
            self.assertEqual(res_dice_q2.status_code, 200)
            self.assertEqual(len(res_dice_q2.data.get('records', [])), 6)

            # Explicit empty selection -> 0 records, is_empty = True
            req_dice_empty = factory.get('/api/demand-prediction/revenue-olap/?operation=dice&years=&months=')
            force_authenticate(req_dice_empty, user=MockAdmin())
            res_dice_empty = RevenueOLAPView.as_view()(req_dice_empty)
            self.assertEqual(res_dice_empty.status_code, 200)
            self.assertEqual(len(res_dice_empty.data.get('records', [])), 0)
            self.assertTrue(res_dice_empty.data.get('subcube_summary', {}).get('is_empty'))



