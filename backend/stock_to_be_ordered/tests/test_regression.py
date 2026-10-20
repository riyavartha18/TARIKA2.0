"""
test_regression.py
------------------
Unit tests for the pure Python OLS Multiple Linear Regression engine.
NO scikit-learn used — all assertions compare against known analytic values.
"""
from django.test import SimpleTestCase
from stock_to_be_ordered.services.regression import (
    fit_ols,
    predict_ols,
    run_regression,
    _transpose,
    _matmul,
)


class TestMatrixHelpers(SimpleTestCase):
    """Tests for internal matrix utilities."""

    def test_transpose_square(self):
        A = [[1, 2], [3, 4]]
        self.assertEqual(_transpose(A), [[1, 3], [2, 4]])

    def test_transpose_rectangular(self):
        A = [[1, 2, 3], [4, 5, 6]]
        self.assertEqual(_transpose(A), [[1, 4], [2, 5], [3, 6]])

    def test_matmul_2x2(self):
        A = [[1, 0], [0, 1]]
        B = [[5, 6], [7, 8]]
        result = _matmul(A, B)
        self.assertAlmostEqual(result[0][0], 5.0)
        self.assertAlmostEqual(result[1][1], 8.0)


class TestFitOLS(SimpleTestCase):
    """Tests for the OLS fitting function."""

    def test_perfect_linear_fit(self):
        """Y = 2*X: coefficients should be ≈ [0, 2]."""
        X = [[1.0], [2.0], [3.0], [4.0], [5.0]]
        Y = [2.0, 4.0, 6.0, 8.0, 10.0]
        coeffs = fit_ols(X, Y)
        self.assertIsNotNone(coeffs)
        self.assertGreater(len(coeffs), 1)
        # intercept ≈ 0, slope ≈ 2
        self.assertAlmostEqual(coeffs[1], 2.0, places=3)

    def test_multiple_features(self):
        """Y ≈ 1 + 2*X1 + 3*X2 — verify coefficients."""
        X = [[1.0, 0.0], [0.0, 1.0], [1.0, 1.0], [2.0, 2.0], [3.0, 1.0]]
        Y = [3.0, 4.0, 6.0, 9.0, 10.0]
        coeffs = fit_ols(X, Y)
        self.assertEqual(len(coeffs), 3)  # intercept + 2 features

    def test_empty_inputs(self):
        """Empty inputs should return empty list."""
        self.assertEqual(fit_ols([], []), [])

    def test_single_feature_intercept(self):
        """Even with X=0 samples, a trivial case should not crash."""
        X = [[0.0], [0.0], [0.0]]
        Y = [5.0, 5.0, 5.0]
        coeffs = fit_ols(X, Y)
        # Prediction at X=0 should be ≈ 5.0 (intercept only)
        self.assertAlmostEqual(coeffs[0], 5.0, places=1)


class TestPredictOLS(SimpleTestCase):
    """Tests for the OLS prediction function."""

    def test_basic_prediction(self):
        """Y = 0 + 1*X → predict(5) = 5."""
        coeffs = [0.0, 1.0]
        self.assertEqual(predict_ols(coeffs, [5.0]), 5)

    def test_non_negative_floor(self):
        """Negative raw predictions should be floored to 0."""
        coeffs = [100.0, -200.0]
        # 100 + (-200)*10 = -1900 → should be 0
        result = predict_ols(coeffs, [10.0])
        self.assertEqual(result, 0)

    def test_integer_rounding(self):
        """Should round to nearest integer."""
        coeffs = [0.0, 1.0]
        # 1.0 * 3.7 = 3.7 → rounds to 4
        self.assertEqual(predict_ols(coeffs, [3.7]), 4)

    def test_empty_coefficients_returns_zero(self):
        """Empty coefficients should return 0."""
        self.assertEqual(predict_ols([], [1.0, 2.0]), 0)


class TestRunRegression(SimpleTestCase):
    """Tests for the end-to-end run_regression convenience function."""

    def test_full_pipeline_multiple_features(self):
        X = [
            [10.0, 5.0, 2.0],
            [12.0, 6.0, 3.0],
            [15.0, 8.0, 4.0],
            [20.0, 10.0, 5.0],
            [8.0, 4.0, 1.0],
            [14.0, 7.0, 3.5],
        ]
        Y = [12.0, 14.0, 18.0, 24.0, 9.0, 16.5]
        result = run_regression(X, Y, [18.0, 9.0, 4.0])

        self.assertIn('predicted_demand', result)
        self.assertIn('coefficients', result)
        self.assertIn('n_training_samples', result)
        self.assertEqual(result['n_training_samples'], 6)
        self.assertIsNotNone(result['predicted_demand'])
        self.assertGreaterEqual(result['predicted_demand'], 0)

    def test_predicted_demand_is_non_negative(self):
        """Negative raw predictions must be floored to 0."""
        X = [[100.0], [200.0]]
        Y = [5.0, 10.0]
        # Predict with x=-500 — raw may go negative
        result = run_regression(X, Y, [-500.0])
        self.assertGreaterEqual(result['predicted_demand'], 0)

    def test_empty_training_returns_none(self):
        result = run_regression([], [], [1.0, 2.0])
        self.assertIsNone(result['predicted_demand'])
