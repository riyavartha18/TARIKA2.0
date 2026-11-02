"""Pure CLV mathematics: documented, deterministic, no machine learning.

Every function here takes plain values and returns plain values, so the whole
formula set is unit-testable without a database. The rules this module
implements (all documented in `utils.py`):

* Historical CLV  = the customer's valid lifetime revenue (RFM Monetary).
* AOV             = historical revenue / valid distinct order count.
* Tenure          = cutoff date - first purchase date (days / years).
* Annual purchase frequency = orders / max(tenure in years, MIN_TENURE_YEARS).
* Value tiers     = percentile bands (P70 / P30) of historical CLV across the
                    whole buyer population, average-rank percentiles - the
                    same reproducible method RFM scoring uses.
* Cohort survival: a customer belongs to the cohort of the calendar MONTH of
                    their FIRST valid purchase and their observed lifespan is
                    the month span from first to last valid purchase. The
                    pooled survival probability S(k) is the share of the
                    buyers observable at age k (cohort month + k within the
                    data horizon) whose last valid purchase is at least k
                    months after their first. A cell only counts while its
                    observation month is fully inside the observed history -
                    the horizon is the latest valid purchase date, never a
                    calendar-year boundary (a ~2-year history can complete
                    24 monthly ages, it can never complete two yearly ones).
* Expected lifespan: discrete survival approximation over the pooled monthly
                    curve S(1..K) (months, right-truncated at the oldest
                    mature age - no tail is invented):
                        E[lifespan months] = 1 + SUM_{k=1..K} S(k)
* Remaining lifespan given the customer already survived `elapsed` months:
                        SUM_{j=1..K-elapsed} S(elapsed+j) / S(elapsed)
                    (an approximation, clearly labelled as such downstream).
* Future CLV      = AOV x observed annual frequency x remaining lifespan in
                    years, only when the data supports it; otherwise an
                    explicit insufficient-data status - never a fabricated
                    number. Customers whose elapsed age already exceeds the
                    oldest observed age have no evidence to project on and
                    are reported without a Future CLV.
"""

from datetime import date

import pandas as pd

from . import utils


def average_rank_percentiles(values):
    """Ascending average-rank percentile (0-100) of each value in the batch.

    Same method as `rfm_analysis.rfm_scoring`: ties share the mean of their
    ordinal ranks; N == 1 places the single value at 100; N == 0 is empty.
    """
    n = len(values)
    if n == 0:
        return []
    if n == 1:
        return [100.0]
    rank = pd.Series(list(values)).rank(method='average', ascending=True)
    return [round(float(r), 2) for r in (100.0 * (rank - 1) / (n - 1))]


def tier_boundaries(values):
    """Historical-CLV values at the High/Medium percentile bands.

    Returns (high_value, medium_value) - a customer is High Value at or above
    `high_value`, Medium Value at or above `medium_value`, else Low Value.
    Percentiles are taken on the sorted population (linear interpolation), a
    documented, reproducible definition.
    """
    if not values:
        return None, None
    series = pd.Series(sorted(values), dtype='float64')
    high = float(series.quantile(utils.CLV_HIGH_PERCENTILE / 100.0))
    medium = float(series.quantile(utils.CLV_MEDIUM_PERCENTILE / 100.0))
    return round(high, 2), round(medium, 2)


def classify_tier(historical_clv, high_value, medium_value):
    if high_value is None:
        return None
    if historical_clv >= high_value:
        return utils.TIER_HIGH
    if historical_clv >= medium_value:
        return utils.TIER_MEDIUM
    return utils.TIER_LOW


def parse_iso_date(value):
    if isinstance(value, date):
        return value
    if not value:
        return None
    return date.fromisoformat(str(value))


def derive_history(order_count, revenue, stored_monetary, first_date, last_date, cutoff):
    """All history-side CLV inputs for one buyer.

    `stored_monetary` is the persisted RFM Monetary value (None when the
    stored row predates Monetary persistence) - historical CLV then reuses the
    live revenue from the orders table, which follows the identical definition.
    """
    order_count = int(order_count or 0)
    historical_clv = (round(float(stored_monetary), 2)
                      if stored_monetary is not None
                      else round(float(revenue or 0), 2))
    aov = round(historical_clv / order_count, 2) if order_count else 0.0

    tenure_days = 0
    if first_date and cutoff:
        # Defensive: a (data-changed-mid-run) first date after the cutoff can
        # never produce a negative tenure.
        tenure_days = max(0, (cutoff - first_date).days)
    tenure_years = tenure_days / utils.DAYS_PER_YEAR
    annual_frequency = (round(order_count / max(tenure_years, utils.MIN_TENURE_YEARS), 3)
                        if order_count else 0.0)
    return {
        'order_count': order_count,
        'historical_clv': historical_clv,
        'aov': aov,
        'tenure_days': tenure_days,
        'tenure_years': round(tenure_years, 3),
        'annual_frequency': annual_frequency,
        'revenue_source': ('rfm_monetary' if stored_monetary is not None
                           else 'orders_aggregate'),
    }


def period_index(value):
    """Calendar-month index (year * 12 + month) - cohort/age arithmetic unit."""
    d = parse_iso_date(value)
    return d.year * 12 + d.month if d else None


def _month_label(period):
    return f'{period // 12:04d}-{period % 12 or 12:02d}'


def build_cohort_matrix(rows):
    """Histogram {(cohort_month, last_month): buyers} from per-buyer rows.

    Each row needs `first_purchase_date` and `last_purchase_date`. The result
    has the same shape `queries.fetch_cohort_matrix` returns, so the SQL
    aggregate and this Python fallback feed one report builder.
    """
    cells = {}
    horizon_period = None
    horizon_date = None
    for row in rows:
        first = parse_iso_date(row.get('first_purchase_date'))
        last = parse_iso_date(row.get('last_purchase_date'))
        if not first or not last:
            continue
        cohort, last_p = period_index(first), period_index(last)
        cells[(cohort, last_p)] = cells.get((cohort, last_p), 0) + 1
        if horizon_period is None or last_p > horizon_period:
            horizon_period, horizon_date = last_p, last
    return {
        'cells': cells,
        'horizon_period': horizon_period,
        'horizon_date': horizon_date.isoformat() if horizon_date else None,
    }


def retention_report(matrix, cutoff):
    """Maturity-filtered monthly cohort survival plus the pooled curve.

    `matrix` is the {(cohort_month, last_month): buyers} histogram (see
    `build_cohort_matrix`); the observation horizon is its latest purchase
    month, so a cell only counts when the customer could still have been seen
    active (never extrapolated past the data).

    Returns a dict with:
      rows        - per-cohort detail (size, per-age survived/observed + S)
      mature_ages - ages with observed buyers, ascending
      retention_probabilities - the pooled survival curve S(age in months),
                    with S(0) = 1.0
      status      - 'ok' when enough mature ages support a lifespan estimate
      expected_lifespan_months / _years - discrete survival approximation
                    (see module docstring), only present when status is 'ok'
    """
    matrix = matrix or {}
    cells = matrix.get('cells') or {}
    horizon = matrix.get('horizon_period')

    def _base(rows_out=None):
        return {
            'cutoff_date': cutoff.isoformat() if cutoff else None,
            'observation_horizon': matrix.get('horizon_date'),
            'horizon_period': horizon,
            'unit': 'month',
            'rows': rows_out or [],
            'mature_ages': [],
            'retention_probabilities': {0: 1.0},
            'status': utils.STATUS_INSUFFICIENT_DATA,
            'message': utils.INSUFFICIENT_DATA_MESSAGE,
        }

    if not cells or horizon is None:
        return _base()

    sizes = {}
    for (cohort, _last), n in cells.items():
        sizes[cohort] = sizes.get(cohort, 0) + n
    cohort_years_sorted = sorted(sizes)
    max_age = horizon - cohort_years_sorted[0]

    survival = {0: 1.0}
    cell_totals = {}  # age -> [survived, observed] over mature cells only
    for age in range(1, max_age + 1):
        survived = observed = 0
        for (cohort, last), n in cells.items():
            if cohort + age <= horizon:  # fully observable at this age
                observed += n
                if last - cohort >= age:
                    survived += n
        if observed > 0:
            survival[age] = round(survived / observed, 4)
            cell_totals[age] = [survived, observed]

    rows = []
    for cohort in cohort_years_sorted:
        entry = {'cohort_period': cohort,
                 'cohort_month': _month_label(cohort),
                 'size': sizes[cohort],
                 'retention': {}}
        for age in range(1, horizon - cohort + 1):
            if age in cell_totals:
                survived, _ = cell_totals[age]
                entry['retention'][age] = {
                    'survived': survived, 'rate': survival.get(age),
                    'mature': True,
                }
        rows.append(entry)

    mature_ages = sorted(cell_totals)
    status = (utils.STATUS_OK
              if len(mature_ages) >= utils.MIN_MATURE_RETENTION_AGES
              else utils.STATUS_INSUFFICIENT_DATA)
    report = _base(rows_out=rows)
    report['mature_ages'] = mature_ages
    report['retention_probabilities'] = survival
    report['status'] = status
    if status == utils.STATUS_OK:
        months = expected_lifespan_months(survival, mature_ages)
        report['expected_lifespan_months'] = round(months, 2)
        report['expected_lifespan_years'] = round(months / 12.0, 3)
        report.pop('message', None)
    return report


def expected_lifespan_months(survival, mature_ages):
    """E[lifespan months] = 1 + SUM_k S(k) over observed mature ages."""
    if not mature_ages:
        return 0.0
    total = 1.0
    for age in range(1, mature_ages[-1] + 1):
        total += survival.get(age, 0.0)
    return total


def remaining_lifespan_months(survival, mature_ages, elapsed_months):
    """Conditional remaining lifespan (months) given survival to `elapsed`.

    Approximation (documented): the pooled monthly survival curve conditioned
    on the elapsed age - SUM_j S(elapsed+j)/S(elapsed). Returns None when the
    customer already survived beyond the oldest observed age (no evidence to
    project on) or the curve cannot support the conditioning - never 0 for
    "unknown": the caller then reports the customer without a Future CLV.
    """
    if not mature_ages:
        return None
    max_age = mature_ages[-1]
    if elapsed_months >= max_age:
        return None
    base = survival.get(elapsed_months)
    if not base or base <= 0:
        return None
    total = 0.0
    for age in range(elapsed_months + 1, max_age + 1):
        total += survival.get(age, 0.0) / base
    return round(total, 3)


def future_clv(aov, annual_frequency, remaining_lifespan):
    """Expected Future CLV = AOV x annual frequency x remaining lifespan."""
    if aov is None or annual_frequency is None or remaining_lifespan is None:
        return None
    return round(aov * annual_frequency * remaining_lifespan, 2)


def future_for_customer(*, historical_clv, aov, order_count,
                        first_purchase_date, retention):
    """(remaining lifespan years, future CLV, total CLV) for one buyer.

    Purchase frequency is observed over the data horizon (first purchase to
    the last observed purchase), not the reporting cutoff: nothing after the
    horizon can be distinguished from "stopped buying", so measuring
    activity beyond it would systematically deflate the frequency.
    Returns (None, None, None) whenever the survival curve cannot support a
    per-customer estimate (insufficient data or already beyond the observed
    ages) - the value is then reported as unavailable, never invented.
    """
    if not retention or retention.get('status') != utils.STATUS_OK:
        return None, None, None
    horizon_period = retention.get('horizon_period')
    first = parse_iso_date(first_purchase_date)
    if horizon_period is None or first is None:
        return None, None, None

    mature_ages = retention.get('mature_ages') or []
    survival = retention.get('retention_probabilities') or {}
    elapsed = max(0, horizon_period - period_index(first))
    remaining_months = remaining_lifespan_months(survival, mature_ages, elapsed)
    if remaining_months is None or remaining_months <= 0:
        return None, None, None
    remaining_years = round(remaining_months / 12.0, 3)

    horizon_date = parse_iso_date(retention.get('observation_horizon'))
    observed_days = max(0, (horizon_date - first).days) if horizon_date else 0
    observed_years = observed_days / utils.DAYS_PER_YEAR
    annual_frequency = (round(order_count / max(observed_years, utils.MIN_TENURE_YEARS), 3)
                        if order_count else 0.0)

    future = future_clv(aov, annual_frequency, remaining_years)
    total = (round(historical_clv + future, 2)
             if future is not None else None)
    return remaining_years, future, total


def future_clv_sql(retention, monetary_col='monetary',
                   first_col='first_purchase_date', orders_col='frequency'):
    """SQL expression reproducing `future_for_customer` row by row, or None.

    The conditional remaining lifespan is a step function of the elapsed
    monthly age, so the whole per-customer formula (AOV x observed annual
    frequency x remaining lifespan) collapses into one CASE over the stored
    columns - letting population averages, range filters and a Future-CLV
    sort run entirely server-side over `rfm_customer_segments` with the exact
    numbers the customer table shows. The expression is placeholder-free (all
    values are numeric constants derived from the pooled curve), so callers
    may repeat it in WHERE / SELECT / ORDER BY without parameter bookkeeping.
    """
    if not retention or retention.get('status') != utils.STATUS_OK:
        return None
    horizon_period = retention.get('horizon_period')
    horizon_date = retention.get('observation_horizon')
    mature_ages = retention.get('mature_ages') or []
    survival = retention.get('retention_probabilities') or {}
    if horizon_period is None or not horizon_date or not mature_ages:
        return None

    max_age = mature_ages[-1]
    whens = []
    for elapsed in range(0, max_age):
        months = remaining_lifespan_months(survival, mature_ages, elapsed)
        if months:
            whens.append(f'WHEN {elapsed} THEN {round(months / 12.0, 3)}')
    if not whens:
        return None

    elapsed_expr = (f'({horizon_period} - (EXTRACT(YEAR FROM {first_col})::int * 12'
                    f' + EXTRACT(MONTH FROM {first_col})::int))')
    remaining_years = (f"CASE {elapsed_expr} {' '.join(whens)} ELSE NULL END")
    # Mirror the Python formula exactly, including the per-step rounding:
    # AOV = round(monetary / orders, 2); frequency = round(orders /
    # max(observed years, floor), 3); result = round(AOV x freq x lifespan).
    aov = (f'ROUND(COALESCE({monetary_col}, 0)::numeric'
           f' / NULLIF({orders_col}, 0), 2)')
    frequency = (f'ROUND(COALESCE({orders_col}, 0)::numeric / '
                 f"GREATEST((DATE '{horizon_date}' - {first_col})::numeric"
                 f' / {utils.DAYS_PER_YEAR}, {utils.MIN_TENURE_YEARS!r}), 3)')
    return f'ROUND(({aov} * {frequency} * {remaining_years})::numeric, 2)'


def derive_page_row(row, cutoff, high_value, medium_value, retention):
    """Derive one CLV customer row from a persisted-RFM page record.

    The heavy population work (tier boundaries, the pooled survival curve) is
    done once and passed in, so this is pure per-row arithmetic for the ~25
    rows of a page - it never touches the orders table and never loads the
    population.
    """
    order_count = int(row.get('frequency') or row.get('order_count') or 0)
    monetary = float(row.get('monetary') or 0)
    historical = round(monetary, 2)
    aov = round(historical / order_count, 2) if order_count else 0.0

    first_date = parse_iso_date(row.get('first_purchase_date'))
    tenure_days = max(0, (cutoff - first_date).days) if (first_date and cutoff) else 0
    tenure_years = tenure_days / utils.DAYS_PER_YEAR
    annual_frequency = (round(order_count / max(tenure_years, utils.MIN_TENURE_YEARS), 3)
                        if order_count else 0.0)

    remaining, future, total = future_for_customer(
        historical_clv=historical, aov=aov, order_count=order_count,
        first_purchase_date=row.get('first_purchase_date'), retention=retention)

    return {
        'customer_id': row['customer_id'],
        'customer_name': row.get('customer_name'),
        'historical_clv': historical,
        'aov': aov,
        'order_count': order_count,
        'first_purchase_date': row.get('first_purchase_date'),
        'last_purchase_date': row.get('last_purchase_date'),
        'tenure_days': tenure_days,
        'tenure_years': round(tenure_years, 3),
        'annual_frequency': annual_frequency,
        'rfm_segment': row.get('segment'),
        'clv_tier': classify_tier(historical, high_value, medium_value),
        'remaining_lifespan_years': remaining,
        'future_clv': future,
        'total_clv': total,
    }
