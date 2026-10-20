"""
test_feature_builder.py
-----------------------
Unit tests for the feature_builder module (no future data leakage validation).
"""
from django.test import SimpleTestCase
from stock_to_be_ordered.services.feature_builder import (
    build_feature_row,
    build_training_dataset,
    build_prediction_features,
    MIN_HISTORY_MONTHS,
)


def _make_record(month_num, year, units_sold, cart_quantity=5.0,
                 wishlist_count=3.0, discount_percentage=10.0):
    """Helper to create a minimal record dict."""
    return {
        'month_num': month_num,
        'year': year,
        'month_start': f'{year}-{month_num:02d}-01',
        'units_sold': units_sold,
        'cart_quantity': cart_quantity,
        'wishlist_count': wishlist_count,
        'discount_percentage': discount_percentage,
    }


SAMPLE_RECORDS = [
    _make_record(1, 2026, 10.0),
    _make_record(2, 2026, 12.0),
    _make_record(3, 2026, 15.0),
    _make_record(4, 2026, 11.0),
    _make_record(5, 2026, 14.0),
    _make_record(6, 2026, 13.0),
]


class TestBuildFeatureRow(SimpleTestCase):

    def test_requires_at_least_one_prior_month(self):
        """Target index 0 has no prior data — should return None."""
        self.assertIsNone(build_feature_row(SAMPLE_RECORDS, 0))

    def test_valid_feature_row_length(self):
        """Feature vector should have exactly 7 elements."""
        result = build_feature_row(SAMPLE_RECORDS, 2)
        self.assertIsNotNone(result)
        feature_vec, target = result
        self.assertEqual(len(feature_vec), 7)

    def test_no_future_data_in_features(self):
        """Verify the feature vector uses only prior-to-target data."""
        result = build_feature_row(SAMPLE_RECORDS, 3)
        self.assertIsNotNone(result)
        feature_vec, target = result
        # prev_month_demand = SAMPLE_RECORDS[2]['units_sold'] = 15.0
        self.assertAlmostEqual(feature_vec[0], 15.0)
        # target = SAMPLE_RECORDS[3]['units_sold'] = 11.0
        self.assertAlmostEqual(target, 11.0)

    def test_target_is_next_month_demand(self):
        """The target value must equal the units_sold at the target_idx."""
        result = build_feature_row(SAMPLE_RECORDS, 4)
        _, target = result
        self.assertAlmostEqual(target, SAMPLE_RECORDS[4]['units_sold'])


class TestBuildTrainingDataset(SimpleTestCase):

    def test_produces_correct_number_of_rows(self):
        """6 months of history → 5 training rows (indices 1..5)."""
        X, Y = build_training_dataset(SAMPLE_RECORDS)
        self.assertEqual(len(X), 5)
        self.assertEqual(len(Y), 5)

    def test_empty_records(self):
        X, Y = build_training_dataset([])
        self.assertEqual(X, [])
        self.assertEqual(Y, [])

    def test_single_record_not_enough(self):
        X, Y = build_training_dataset([SAMPLE_RECORDS[0]])
        self.assertEqual(X, [])
        self.assertEqual(Y, [])


class TestBuildPredictionFeatures(SimpleTestCase):

    def test_returns_seven_features(self):
        """Prediction feature vector should have 7 elements."""
        result = build_prediction_features(SAMPLE_RECORDS)
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 7)

    def test_uses_latest_month_data(self):
        """prev_month_demand should equal the latest record's units_sold."""
        result = build_prediction_features(SAMPLE_RECORDS)
        # Latest record = SAMPLE_RECORDS[-1] = month 6, units_sold = 13.0
        self.assertAlmostEqual(result[0], 13.0)

    def test_empty_records_returns_none(self):
        self.assertIsNone(build_prediction_features([]))

    def test_single_record_returns_vector(self):
        """Even a single record should return a valid vector."""
        single = [_make_record(1, 2026, 5.0)]
        result = build_prediction_features(single)
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 7)
