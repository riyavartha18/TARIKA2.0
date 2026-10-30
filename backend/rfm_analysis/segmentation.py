"""Finalized rule-based customer segmentation (no K-Means, no ML clustering).

Segments are assigned with the exact percentile conditions fixed by the
business rules, evaluated in a strict priority order so the *first* matching
rule wins. This module is the single home for those conditions; nothing here
is scattered elsewhere and no monetary/frequency amount cutoff is used - the
inputs are the dynamic percentiles produced by `rfm_scoring`.

Primary segments (R = Recency percentile, F = Frequency, M = Monetary):

    1. Champions          R>=80  and F>=80  and M>=80
    2. Loyal Customers    R>=60  and F>=80  (M any)
    3. Potential Loyalists R>=80 and 20<F<=60 (M any)
    4. New Customers      R>=80  and F<=20  and M<=60
    5. At-Risk            R<=40  and F>=60  (M any)
    6. Hibernating        R<=20  and F<=40  and M<=40

There is deliberately no "Others" segment: every eligible buyer who matches
none of the ordered rules is resolved by `_fallback_classify` into one of the
same six segments (see the documented residual rules below).

"Any" means that metric is ignored for the rule. Big Spenders is NOT a primary
segment: it is an independent secondary tag applied when M>=90, so a Big
Spender still keeps whichever primary segment they qualify for. Never Purchased
customers never reach this module at all (they are excluded before scoring).
"""

from . import utils


# Each rule is (segment_label, predicate) in priority order. `r`, `f`, `m` are
# the Recency/Frequency/Monetary percentiles (0-100).
SEGMENT_RULES = [
    (utils.SEGMENT_CHAMPIONS, lambda r, f, m: r >= 80 and f >= 80 and m >= 80),
    (utils.SEGMENT_LOYAL, lambda r, f, m: r >= 60 and f >= 80),
    (utils.SEGMENT_POTENTIAL_LOYALISTS, lambda r, f, m: r >= 80 and 20 < f <= 60),
    (utils.SEGMENT_NEW, lambda r, f, m: r >= 80 and f <= 20 and m <= 60),
    (utils.SEGMENT_AT_RISK, lambda r, f, m: r <= 40 and f >= 60),
    (utils.SEGMENT_HIBERNATING, lambda r, f, m: r <= 20 and f <= 40 and m <= 40),
]

BIG_SPENDER_PERCENTILE = 90


def classify(r_percentile, f_percentile, m_percentile):
    """Return (primary_segment, [secondary_tags]) for one buyer's percentiles.

    The six percentile rules are tried in priority order first (first match
    wins). Every eligible buyer must land in a primary segment, so a buyer who
    matches none is resolved by `_fallback_classify` into one of the same six
    segments. The percentile inputs are unchanged; only the residual bucket is
    newly mapped (previously it would have been "Others").
    """
    segment = None
    for label, predicate in SEGMENT_RULES:
        if predicate(r_percentile, f_percentile, m_percentile):
            segment = label
            break
    if segment is None:
        segment = _fallback_classify(r_percentile, f_percentile, m_percentile)

    tags = []
    if m_percentile >= BIG_SPENDER_PERCENTILE:
        tags.append(utils.TAG_BIG_SPENDER)

    return segment, tags


# ---------------------------------------------------------------------------
# Residual (fallback) classification - documented
# ---------------------------------------------------------------------------
# Only reached when NONE of the six ordered percentile rules matched, so it
# never competes with them (priority is respected) and always returns exactly
# one of the six primary segments (no buyer is unclassified or double-counted).
# It reads the customer's dominant RFM signal:
#
#   Recent side (R >= 50):
#     - Frequency-dominant repeat buyer .............. -> Loyal Customers
#     - Very low frequency (a recent first purchase) . -> New Customers
#     - otherwise (a habit still forming) ............ -> Potential Loyalists
#   Dormant side (R < 50):
#     - still frequent or still high-value (drifting) . -> At-Risk
#     - low across the board ......................... -> Hibernating
#
# Big Spenders (secondary tag) and Never Purchased are handled independently
# and are unaffected by this fallback.
FALLBACK_RECENT_THRESHOLD = 50
FALLBACK_SIGNAL_THRESHOLD = 50
FALLBACK_NEW_FREQUENCY_THRESHOLD = 20


def _fallback_classify(r, f, m):
    if r >= FALLBACK_RECENT_THRESHOLD:
        if f > FALLBACK_SIGNAL_THRESHOLD and f >= r and f >= m:
            return utils.SEGMENT_LOYAL
        if f <= FALLBACK_NEW_FREQUENCY_THRESHOLD:
            return utils.SEGMENT_NEW
        return utils.SEGMENT_POTENTIAL_LOYALISTS
    if f >= FALLBACK_SIGNAL_THRESHOLD or m >= FALLBACK_SIGNAL_THRESHOLD:
        return utils.SEGMENT_AT_RISK
    return utils.SEGMENT_HIBERNATING


def apply_segments(metrics):
    """Attach `segment` and `tags` to every scored metric dict, in place."""
    for metric in metrics:
        segment, tags = classify(
            metric['r_percentile'],
            metric['f_percentile'],
            metric['m_percentile'],
        )
        metric['segment'] = segment
        metric['tags'] = tags
    return metrics


def segment_counts(metrics):
    """Aggregate counts per primary segment plus the Big Spender tag count."""
    counts = {label: 0 for label in utils.PRIMARY_SEGMENTS}
    big_spender_count = 0
    for metric in metrics:
        counts[metric['segment']] = counts.get(metric['segment'], 0) + 1
        if utils.TAG_BIG_SPENDER in metric['tags']:
            big_spender_count += 1
    return counts, big_spender_count
