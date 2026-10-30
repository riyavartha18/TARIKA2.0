"""Dynamic percentile-based RFM scoring (no fixed monetary/frequency cutoffs).

Percentiles are derived from the *current* eligible-buyer population on every
run, so the scoring adapts to the data instead of relying on hardcoded amount
thresholds. Ties use average ranking (equal metric values share one rank and
are never arbitrarily split), and the direction is set per metric:

* Recency    - lower days is better, so its percentile is reversed.
* Frequency  - higher is better.
* Monetary   - higher is better.

The formulas are exactly the ones fixed by the business rules, with N the
number of eligible buyers:

    R_percentile = 100 * (N - avg_rank(recency_days)) / (N - 1)
    F_percentile = 100 * (avg_rank(frequency) - 1)    / (N - 1)
    M_percentile = 100 * (avg_rank(monetary) - 1)     / (N - 1)

`avg_rank(...)` is the ascending average rank (1 = smallest value). N == 1 is
handled explicitly (the sole buyer sits at the top, percentile 100) and N == 0
returns an empty scoring state, so there is never a division by zero.
"""

import numpy as np
import pandas as pd

# Score band edges (percentile -> display score). Kept here as the single
# definition used by both scoring and the tests.
SCORE_BANDS = [
    (20.0, 1),
    (40.0, 2),
    (60.0, 3),
    (80.0, 4),
    (100.0, 5),
]


def _average_rank(values):
    """Ascending average rank (ties share the mean of their ordinal ranks)."""
    return pd.Series(values).rank(method='average', ascending=True).to_numpy(dtype='float64')


def _percentile_from_rank(rank, n, reverse):
    if reverse:
        return 100.0 * (n - rank) / (n - 1)
    return 100.0 * (rank - 1) / (n - 1)


def _score_from_percentile(percentile):
    for upper, score in SCORE_BANDS:
        if percentile <= upper:
            return score
    return 5


def score_metrics(metrics):
    """Attach r/f/m percentile and 1-5 score to each metric dict, in place.

    Percentiles are rounded to two decimals for display; scores are derived
    from the rounded percentile so a value shown as exactly 80.00 scores 4 and
    one shown as 80.01 scores 5, matching the inclusive band edges.
    """
    n = len(metrics)
    if n == 0:
        return metrics

    if n == 1:
        # Single buyer: no spread to rank, place them at the top explicitly.
        for metric in metrics:
            metric['r_percentile'] = 100.0
            metric['f_percentile'] = 100.0
            metric['m_percentile'] = 100.0
            metric['r_score'] = metric['f_score'] = metric['m_score'] = 5
        return metrics

    recency = np.array([m['recency_days'] for m in metrics], dtype='float64')
    frequency = np.array([m['frequency'] for m in metrics], dtype='float64')
    monetary = np.array([m['monetary'] for m in metrics], dtype='float64')

    r_rank = _average_rank(recency)
    f_rank = _average_rank(frequency)
    m_rank = _average_rank(monetary)

    r_pct = _percentile_from_rank(r_rank, n, reverse=True)
    f_pct = _percentile_from_rank(f_rank, n, reverse=False)
    m_pct = _percentile_from_rank(m_rank, n, reverse=False)

    for index, metric in enumerate(metrics):
        rp = round(float(r_pct[index]), 2)
        fp = round(float(f_pct[index]), 2)
        mp = round(float(m_pct[index]), 2)
        metric['r_percentile'] = rp
        metric['f_percentile'] = fp
        metric['m_percentile'] = mp
        metric['r_score'] = _score_from_percentile(rp)
        metric['f_score'] = _score_from_percentile(fp)
        metric['m_score'] = _score_from_percentile(mp)

    return metrics
