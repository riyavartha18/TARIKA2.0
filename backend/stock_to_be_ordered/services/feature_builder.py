"""
feature_builder.py
------------------
Builds regression feature rows from historical demand records.

Features used (no future data leakage):
  - prev_month_demand        : units_sold in the month BEFORE the target month
  - prev_2m_avg_demand       : average units_sold over the 2 months before target
  - prev_3m_avg_demand       : average units_sold over the 3 months before target
  - prev_month_wishlist      : wishlist_count in the month before target
  - prev_month_cart          : cart_quantity in the month before target
  - discount_percentage      : discount in the current feature month
  - month_num                : calendar month (1–12) as a cyclical indicator

Each training row represents:
  X_m (feature vector at month m) → Y_{m+1} (target: units_sold at month m+1)

For prediction:
  X_latest_month → Y_next_month (never uses next-month actual data)
"""

# Minimum number of historical months a product must have to attempt regression
MIN_HISTORY_MONTHS = 4


def build_feature_row(records, target_idx):
    """
    Builds a single regression feature vector for target_idx (the target month).
    Uses only records BEFORE target_idx — no future data leakage.

    Args:
        records: list of monthly dicts for ONE product, sorted by month_start asc
        target_idx: index of the target month (records[target_idx])

    Returns:
        (feature_vector, target_value) tuple, or None if not enough prior data.
    """
    if target_idx < 1:
        # Need at least 1 prior month
        return None

    target_rec = records[target_idx]
    prev_recs = records[:target_idx]  # All months strictly before target

    # prev_month_demand: units_sold one month before
    prev_month_demand = prev_recs[-1]['units_sold']

    # prev_2m_avg_demand: average over last 2 months (or fewer if only 1 available)
    prev_2 = prev_recs[-2:] if len(prev_recs) >= 2 else prev_recs
    prev_2m_avg_demand = sum(r['units_sold'] for r in prev_2) / len(prev_2)

    # prev_3m_avg_demand: average over last 3 months
    prev_3 = prev_recs[-3:] if len(prev_recs) >= 3 else prev_recs
    prev_3m_avg_demand = sum(r['units_sold'] for r in prev_3) / len(prev_3)

    # prev_month_wishlist
    prev_month_wishlist = prev_recs[-1]['wishlist_count']

    # prev_month_cart
    prev_month_cart = prev_recs[-1]['cart_quantity']

    # discount_percentage: use the feature month's discount (available at prediction time)
    discount_percentage = prev_recs[-1]['discount_percentage']

    # month_num: calendar month of the FEATURE month (not the target)
    # Encodes seasonal patterns (1=Jan, 12=Dec)
    month_num = float(prev_recs[-1]['month_num'])

    feature_vector = [
        prev_month_demand,
        prev_2m_avg_demand,
        prev_3m_avg_demand,
        prev_month_wishlist,
        prev_month_cart,
        discount_percentage,
        month_num,
    ]

    target_value = target_rec['units_sold']
    return feature_vector, target_value


def build_training_dataset(sorted_records):
    """
    Builds a complete training dataset (X_matrix, Y_vector) for a product
    using all available historical months.

    Args:
        sorted_records: list of monthly records sorted ascending by month_start

    Returns:
        (X_matrix, Y_vector) — or ([], []) if insufficient data
    """
    X_matrix = []
    Y_vector = []

    for i in range(1, len(sorted_records)):
        result = build_feature_row(sorted_records, i)
        if result is not None:
            x_row, y_val = result
            X_matrix.append(x_row)
            Y_vector.append(y_val)

    return X_matrix, Y_vector


def build_prediction_features(sorted_records):
    """
    Builds the feature vector for next-month prediction using the
    LATEST available historical month's data.

    No future data (next month actuals) is used here.

    Args:
        sorted_records: list of all historical months, sorted asc

    Returns:
        feature_vector list, or None if insufficient data
    """
    n = len(sorted_records)
    if n < 1:
        return None

    # Latest available month is the last record
    latest = sorted_records[-1]
    prev_recs = sorted_records  # All records up to and including latest

    # prev_month_demand = latest month units_sold
    prev_month_demand = latest['units_sold']

    prev_2 = prev_recs[-2:] if len(prev_recs) >= 2 else prev_recs
    prev_2m_avg_demand = sum(r['units_sold'] for r in prev_2) / len(prev_2)

    prev_3 = prev_recs[-3:] if len(prev_recs) >= 3 else prev_recs
    prev_3m_avg_demand = sum(r['units_sold'] for r in prev_3) / len(prev_3)

    prev_month_wishlist = latest['wishlist_count']
    prev_month_cart = latest['cart_quantity']
    discount_percentage = latest['discount_percentage']
    month_num = float(latest['month_num'])

    return [
        prev_month_demand,
        prev_2m_avg_demand,
        prev_3m_avg_demand,
        prev_month_wishlist,
        prev_month_cart,
        discount_percentage,
        month_num,
    ]
