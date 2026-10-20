"""
regression.py
-------------
Pure Python implementation of Multiple Linear Regression using
Ordinary Least Squares (OLS) — NO scikit-learn, NO ML libraries.

Mathematical formulation:
    Y = β₀ + β₁X₁ + β₂X₂ + ... + βₙXₙ

OLS closed-form solution:
    β = (XᵀX)⁻¹ XᵀY

Matrix operations are implemented manually (no numpy, no scipy).
Ridge regularisation (λ = 1e-4) is added to XᵀX before inversion to
prevent singular-matrix issues when features are colinear or when there
are few training samples.
"""


# ---------------------------------------------------------------------------
# Core Matrix Arithmetic
# ---------------------------------------------------------------------------

def _transpose(matrix):
    """Returns the transpose of a 2-D list-of-lists matrix."""
    if not matrix or not matrix[0]:
        return []
    rows = len(matrix)
    cols = len(matrix[0])
    return [[matrix[r][c] for r in range(rows)] for c in range(cols)]


def _matmul(A, B):
    """
    Multiplies two 2-D matrices A (m×n) and B (n×p).
    Returns result matrix of shape (m×p).
    """
    rows_A = len(A)
    cols_A = len(A[0])
    cols_B = len(B[0])
    result = [[0.0] * cols_B for _ in range(rows_A)]
    for i in range(rows_A):
        for k in range(cols_A):
            if A[i][k] == 0.0:
                continue
            for j in range(cols_B):
                result[i][j] += A[i][k] * B[k][j]
    return result


def _invert_matrix(matrix, ridge_lambda=1e-4):
    """
    Inverts a square matrix using Gauss-Jordan elimination with Ridge (L2)
    regularisation added to the diagonal.

    Ridge term: XᵀX + λI — prevents singular matrix when features correlate
    or when the training set is very small.

    If the matrix is still numerically singular after regularisation,
    lambda is multiplied by 10 and the function retries recursively.
    """
    n = len(matrix)

    # Build augmented matrix [A + λI | I]
    aug = []
    for i in range(n):
        row = []
        for j in range(n):
            val = float(matrix[i][j])
            if i == j:
                val += ridge_lambda  # Ridge regularisation
            row.append(val)
        for j in range(n):
            row.append(1.0 if i == j else 0.0)
        aug.append(row)

    # Forward / backward elimination (Gauss-Jordan)
    for i in range(n):
        # Partial pivoting: swap with the row that has the largest |pivot|
        max_row = i
        for k in range(i + 1, n):
            if abs(aug[k][i]) > abs(aug[max_row][i]):
                max_row = k
        aug[i], aug[max_row] = aug[max_row], aug[i]

        pivot = aug[i][i]
        if abs(pivot) < 1e-14:
            # Matrix is still singular — increase regularisation and retry
            return _invert_matrix(matrix, ridge_lambda=ridge_lambda * 10.0)

        # Scale row i so that aug[i][i] = 1
        scale = 1.0 / pivot
        for j in range(2 * n):
            aug[i][j] *= scale

        # Eliminate column i from all other rows
        for k in range(n):
            if k == i:
                continue
            factor = aug[k][i]
            if factor == 0.0:
                continue
            for j in range(2 * n):
                aug[k][j] -= factor * aug[i][j]

    # Extract inverse from the right half of the augmented matrix
    return [row[n:] for row in aug]


# ---------------------------------------------------------------------------
# OLS Fitting
# ---------------------------------------------------------------------------

def fit_ols(X_matrix, Y_vector):
    """
    Fits Ordinary Least Squares (OLS) Multiple Linear Regression.

    β = (XᵀX)⁻¹ XᵀY

    A bias column of 1.0 is prepended to X so that β₀ (intercept) is
    included automatically.

    Args:
        X_matrix : list of feature vectors, shape (n_samples, n_features)
        Y_vector : list of target values, shape (n_samples,)

    Returns:
        coefficients : list [β₀, β₁, …, βₙ]   (length = n_features + 1)
        Returns [] if inputs are empty or invalid.
    """
    n_samples = len(X_matrix)
    if n_samples == 0 or len(Y_vector) == 0:
        return []
    if n_samples != len(Y_vector):
        return []

    # Augment X with bias column (intercept term β₀)
    X_aug = [[1.0] + [float(v) for v in row] for row in X_matrix]

    # Y as column vector
    Y_col = [[float(y)] for y in Y_vector]

    X_T = _transpose(X_aug)          # Shape: (n_features+1, n_samples)
    XT_X = _matmul(X_T, X_aug)       # Shape: (n_features+1, n_features+1)
    XT_X_inv = _invert_matrix(XT_X)  # Shape: (n_features+1, n_features+1)
    XT_Y = _matmul(X_T, Y_col)       # Shape: (n_features+1, 1)

    beta_col = _matmul(XT_X_inv, XT_Y)  # Shape: (n_features+1, 1)
    return [b[0] for b in beta_col]


# ---------------------------------------------------------------------------
# OLS Prediction
# ---------------------------------------------------------------------------

def predict_ols(coefficients, x_vector):
    """
    Predicts Y for a single sample using fitted OLS coefficients.

    Ŷ = β₀ + β₁x₁ + β₂x₂ + … + βₙxₙ

    Enforces:
      - Non-negative prediction (minimum 0)
      - Integer rounding (round half away from zero)

    Args:
        coefficients : list [β₀, β₁, …, βₙ]
        x_vector     : list of feature values [x₁, x₂, …, xₙ]

    Returns:
        Predicted demand as a non-negative integer.
    """
    if not coefficients:
        return 0

    y_pred = float(coefficients[0])  # Intercept β₀
    for beta, x_val in zip(coefficients[1:], x_vector):
        y_pred += float(beta) * float(x_val)

    # Non-negative integer rounding rule
    return max(0, int(round(y_pred)))


# ---------------------------------------------------------------------------
# Convenience wrapper
# ---------------------------------------------------------------------------

def run_regression(X_matrix, Y_vector, x_predict):
    """
    End-to-end helper: fit OLS and predict for one sample.

    Returns:
        {
          'coefficients': [...],
          'predicted_demand': int,
          'n_training_samples': int,
        }
    """
    coefficients = fit_ols(X_matrix, Y_vector)
    if not coefficients:
        return {
            'coefficients': [],
            'predicted_demand': None,
            'n_training_samples': len(X_matrix),
        }

    predicted = predict_ols(coefficients, x_predict)

    return {
        'coefficients': coefficients,
        'predicted_demand': predicted,
        'n_training_samples': len(X_matrix),
    }
