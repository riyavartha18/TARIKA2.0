"""Stage one of the analysis: turn raw buyer rows into the three RFM metrics.

The metrics themselves come straight from the PostgreSQL aggregate in
`queries.fetch_buyer_metrics`; this module only normalises their types and
documents the exact meaning chosen for each, so the rest of the pipeline works
on a clean, uniform record.

Metric definitions (verified against the live `public.orders` schema):

* Recency   - whole days between the analysis date and the customer's most
              recent eligible purchase. Lower is better. The analysis date is
              the greater of the database's current date and the latest
              purchase date, so future-dated rows never make Recency negative.
* Frequency - count of DISTINCT eligible `orderid` values. `orderid` is the
              primary key and one row is one order, so this is already the
              number of orders, not product rows, and cannot double-count.
* Monetary  - the sum of `final_price` over those eligible orders. `final_price`
              is the amount actually paid for the (single-line) order, so there
              is no order-vs-line aggregation ambiguity. Negative `final_price`
              rows (verified as corrupted discounts, not refunds) are excluded
              by the eligibility filter unless that policy is switched off.
"""

from . import utils


def build_metrics(buyer_rows):
    """Return a list of normalised metric dicts plus the analysis date.

    Each record keeps the raw metric values and the first/last purchase dates
    (used for the accurate New-Customer interpretation in Section 7), but no
    score or segment yet - those are added by the scoring and segmentation
    stages.
    """
    metrics = []
    for row in buyer_rows:
        recency = row.get('recency_days')
        frequency = row.get('frequency')
        monetary = row.get('monetary')
        metrics.append({
            'customer_id': row['customer_id'],
            'customer_name': row.get('customer_name'),
            'recency_days': int(recency) if recency is not None else None,
            'frequency': int(frequency) if frequency is not None else 0,
            'monetary': round(float(monetary or 0), 2),
            'last_purchase_date': row.get('last_purchase_date'),
            'first_purchase_date': row.get('first_purchase_date'),
            'lifetime_orders': int(row.get('lifetime_orders') or 0),
        })
    analysis_date = buyer_rows[0]['analysis_date'] if buyer_rows else None
    return metrics, analysis_date
