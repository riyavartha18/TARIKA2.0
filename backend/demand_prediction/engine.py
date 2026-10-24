"""
Demand Forecasting engine (ID3 decision-tree classifier).

The core ID3 logic (Shannon entropy, information gain, threshold search,
recursive tree construction, prediction traversal) is preserved exactly as it
has always been implemented here -- no sklearn, no external ML libraries and
no hardcoded predictions.

Two things were updated to match the real Supabase data warehouse:

  * Source tables are now ``public.fact_product_analysis`` (metrics) joined to
    ``public.dim_product`` (details/stock) on ``product_key``. The previous
    ``fact_demand`` / ``dim_time`` time-series schema no longer exists.
  * The dataset is a single snapshot (one row per product) rather than monthly
    observations, so the model is trained on a *weighted frequency table*
    (``GROUP BY`` the demand indicators + target bucket). Because every product
    that shares the same indicator values falls into the same leaf, weighting
    each unique combination by its row count yields ID3 results identical to
    training on all ~90k raw rows -- while transferring ~7k rows instead of 90k.

Demand indicators used as features (what the customer does):
    wishlist_count, cart_count, purchase_count
Target (demand strength) is derived from ``units_sold`` using data-driven
tercile cut-offs -- ``units_sold`` is the outcome being predicted, so it is
never a feature. ``total_sales`` and ``available_quantity`` are shown as
evidence / stock and are deliberately NOT demand features.
"""
import math
import threading
import time

from django.db import connection


class DecisionTreeEngine:
    """
    Pure Python manual ID3 Decision Tree Classifier for demand prediction.

    Mathematical workflow (unchanged core logic):
    1. Demand Classification -> target buckets (High / Medium / Low)
    2. Entropy               -> H(S) = - sum(p_i * log2(p_i))
    3. Information Gain      -> IG(S, F, T) = H(S) - weighted H_split
    4. Best Split Selection  -> feature & threshold maximising IG
    5. Recursive Tree Construction (max depth guard)
    6. Demand Prediction via tree traversal + decision path
    """

    # Features the ID3 tree splits on. All are genuine historical demand
    # indicators with low cardinality (kept the frequency-table training path
    # compact). total_sales/units_sold are intentionally excluded (see module
    # docstring) -- units_sold is the target, and available_quantity is stock.
    FEATURE_NAMES = ['wishlist_count', 'cart_count', 'purchase_count']

    CLASS_ORDER = ['Low', 'Medium', 'High']

    # ------------------------------------------------------------------
    # Entropy / Information Gain (weight-aware, same formulas)
    # ------------------------------------------------------------------
    @staticmethod
    def _count_of(sample):
        # A sample is a dict of feature values + 'target' + optional 'count'
        # (row multiplicity). Missing count means a single observation.
        return sample.get('count', 1) or 0

    @classmethod
    def calculate_entropy(cls, samples):
        """Shannon entropy H(S) over weighted class labels."""
        total = 0.0
        counts = {}
        for s in samples:
            w = cls._count_of(s)
            if w <= 0:
                continue
            total += w
            counts[s['target']] = counts.get(s['target'], 0.0) + w

        if total <= 0:
            return 0.0

        entropy = 0.0
        for c in counts.values():
            p = c / total
            if p > 0:
                entropy -= p * math.log2(p)
        return round(entropy, 4)

    @classmethod
    def weighted_size(cls, samples):
        return sum(cls._count_of(s) for s in samples)

    @classmethod
    def class_distribution(cls, samples):
        dist = {label: 0.0 for label in cls.CLASS_ORDER}
        for s in samples:
            w = cls._count_of(s)
            if w > 0:
                dist[s['target']] = dist.get(s['target'], 0.0) + w
        return dist

    @classmethod
    def calculate_split_gain(cls, dataset, feature, threshold, parent_entropy):
        """Information gain for the candidate split (feature <= threshold)."""
        n_total = cls.weighted_size(dataset)
        if n_total == 0:
            return 0.0, [], []

        left_samples = [d for d in dataset if d[feature] <= threshold]
        right_samples = [d for d in dataset if d[feature] > threshold]

        n_left = cls.weighted_size(left_samples)
        n_right = cls.weighted_size(right_samples)

        if n_left == 0 or n_right == 0:
            return 0.0, left_samples, right_samples

        entropy_left = cls.calculate_entropy(left_samples)
        entropy_right = cls.calculate_entropy(right_samples)

        weighted_entropy = (n_left / n_total) * entropy_left + (n_right / n_total) * entropy_right
        information_gain = parent_entropy - weighted_entropy

        return round(information_gain, 4), left_samples, right_samples

    @classmethod
    def _candidate_thresholds(cls, dataset, feature):
        values = sorted(set(d[feature] for d in dataset))
        if len(values) <= 1:
            return values  # single distinct value (or empty)
        candidates = [(values[i] + values[i + 1]) / 2.0 for i in range(len(values) - 1)]
        if len(candidates) > 50:
            step = len(candidates) // 50
            candidates = candidates[::step]
        return candidates

    @classmethod
    def _entropy_from_counts(cls, counts, total):
        """Shannon entropy straight from a {target: weight} count map."""
        if total <= 0:
            return 0.0
        entropy = 0.0
        for c in counts.values():
            p = c / total
            if p > 0:
                entropy -= p * math.log2(p)
        return entropy

    @classmethod
    def _value_class_counts(cls, dataset, feature):
        """
        Collapse the dataset to sorted distinct feature values, each paired with
        the weighted class distribution at that value. Sweeping cumulative counts
        over this gives identical split gains to scanning every row per threshold,
        but in O(distinct_values) instead of O(thresholds x rows).
        """
        buckets = {}
        for d in dataset:
            w = cls._count_of(d)
            if w <= 0:
                continue
            value = d[feature]
            bucket = buckets.setdefault(value, {})
            bucket[d['target']] = bucket.get(d['target'], 0.0) + w
        return sorted(buckets.items(), key=lambda kv: kv[0])

    @classmethod
    def _best_split_for_feature(cls, dataset, feature, parent_entropy):
        """
        Exact ID3 best (threshold, gain) for one continuous feature via a single
        cumulative sweep. Splits at the midpoint between consecutive distinct
        values, matching ``calculate_split_gain`` semantics precisely.
        """
        items = cls._value_class_counts(dataset, feature)
        if len(items) <= 1:
            return 0.0, None

        total_weight = sum(sum(counts.values()) for _, counts in items)
        grand = {}
        for _, counts in items:
            for target, w in counts.items():
                grand[target] = grand.get(target, 0.0) + w

        left_counts = {}
        left_weight = 0.0
        best_gain = 0.0
        best_threshold = None

        for i in range(len(items) - 1):
            value, counts = items[i]
            for target, w in counts.items():
                left_counts[target] = left_counts.get(target, 0.0) + w
                left_weight += w
            right_weight = total_weight - left_weight
            if left_weight <= 0 or right_weight <= 0:
                continue

            right_counts = {t: (grand.get(t, 0.0) - left_counts.get(t, 0.0)) for t in grand}
            h_left = cls._entropy_from_counts(left_counts, left_weight)
            h_right = cls._entropy_from_counts(right_counts, right_weight)
            weighted = (left_weight / total_weight) * h_left + (right_weight / total_weight) * h_right
            gain = parent_entropy - weighted

            if gain > best_gain:
                best_gain = gain
                best_threshold = (value + items[i + 1][0]) / 2.0

        return round(best_gain, 4), best_threshold

    @classmethod
    def evaluate_feature_gains(cls, dataset, parent_entropy):
        """Max information gain + optimal threshold per feature (root report)."""
        feature_report = {}

        for feat in cls.FEATURE_NAMES:
            values = sorted(set(d[feat] for d in dataset))
            best_gain, best_threshold = cls._best_split_for_feature(dataset, feat, parent_entropy)

            feature_report[feat] = {
                'gain': round(best_gain, 4),
                'best_threshold': round(best_threshold, 4) if best_threshold is not None else (round(values[0], 4) if values else 0.0),
                'feature_label': feat.replace('_', ' ').title(),
            }

        sorted_gains = dict(sorted(feature_report.items(), key=lambda item: item[1]['gain'], reverse=True))
        rank = 1
        for k in sorted_gains:
            sorted_gains[k]['rank'] = rank
            rank += 1
        return sorted_gains

    @classmethod
    def find_best_split(cls, dataset, parent_entropy):
        """Single best (feature, threshold) split across all candidate features."""
        best_gain = 0.0
        best_feature = None
        best_threshold = None

        for feat in cls.FEATURE_NAMES:
            gain, threshold = cls._best_split_for_feature(dataset, feat, parent_entropy)
            if threshold is not None and gain > best_gain:
                best_gain = gain
                best_feature = feat
                best_threshold = threshold

        if best_feature is None:
            return {'feature': None, 'threshold': None, 'information_gain': 0.0, 'left': [], 'right': []}

        left = [d for d in dataset if d[best_feature] <= best_threshold]
        right = [d for d in dataset if d[best_feature] > best_threshold]

        return {
            'feature': best_feature,
            'threshold': round(best_threshold, 4),
            'information_gain': round(best_gain, 4),
            'left': left,
            'right': right,
        }

    @classmethod
    def build_tree(cls, dataset, depth=0, max_depth=3, node_counter=None):
        """Recursively construct the ID3 decision tree."""
        if node_counter is None:
            node_counter = [0]

        node_id = f"node_{node_counter[0]}"
        node_counter[0] += 1

        n_samples = cls.weighted_size(dataset)
        value_counts = cls.class_distribution(dataset)
        prediction = max(value_counts, key=value_counts.get) if n_samples > 0 else 'Medium'
        node_entropy = cls.calculate_entropy(dataset)

        # Stopping criteria: pure node, max depth, or too few weighted samples.
        if node_entropy == 0.0 or depth >= max_depth or n_samples < 5:
            return {
                'node_id': node_id, 'is_leaf': True, 'prediction': prediction,
                'entropy': node_entropy, 'samples': n_samples,
                'value_counts': value_counts, 'depth': depth,
            }

        split = cls.find_best_split(dataset, node_entropy)

        if not split['feature'] or split['information_gain'] <= 0.0001 or not split['left'] or not split['right']:
            return {
                'node_id': node_id, 'is_leaf': True, 'prediction': prediction,
                'entropy': node_entropy, 'samples': n_samples,
                'value_counts': value_counts, 'depth': depth,
            }

        left_node = cls.build_tree(split['left'], depth + 1, max_depth, node_counter)
        right_node = cls.build_tree(split['right'], depth + 1, max_depth, node_counter)

        return {
            'node_id': node_id, 'is_leaf': False,
            'feature': split['feature'],
            'feature_label': split['feature'].replace('_', ' ').title(),
            'threshold': split['threshold'],
            'gain': split['information_gain'],
            'entropy': node_entropy, 'samples': n_samples,
            'value_counts': value_counts, 'prediction': prediction,
            'depth': depth, 'left': left_node, 'right': right_node,
        }

    # ------------------------------------------------------------------
    # Prediction + explanation
    # ------------------------------------------------------------------
    @classmethod
    def predict_sample(cls, node, sample):
        """Traverse the tree to a demand class for one sample."""
        while node and not node.get('is_leaf'):
            feat = node['feature']
            if float(sample.get(feat, 0) or 0) <= node['threshold']:
                node = node['left']
            else:
                node = node['right']
        return (node or {}).get('prediction', 'Medium')

    @classmethod
    def explain_prediction(cls, node, sample):
        """
        Walk the tree, recording the actual decision path taken.

        Returns (prediction, steps) where each step is
        {'feature_label','feature','threshold','value','comparison'}.
        """
        steps = []
        current = node
        while current and not current.get('is_leaf'):
            feat = current['feature']
            value = float(sample.get(feat, 0) or 0)
            threshold = current['threshold']
            go_left = value <= threshold
            steps.append({
                'feature': feat,
                'feature_label': current.get('feature_label', feat.replace('_', ' ').title()),
                'threshold': threshold,
                'value': value,
                'comparison': '<=' if go_left else '>',
            })
            current = current['left'] if go_left else current['right']
        prediction = (current or {}).get('prediction', 'Medium')
        return prediction, steps


# ==========================================================================
# Data access + trained-model cache
# ==========================================================================
_MAX_DEPTH = 3
_engine = DecisionTreeEngine()

# Simple process-local cache of the trained model, keyed by a cheap data
# fingerprint so it is rebuilt only when fact_product_analysis changes.
_MODEL_CACHE = {}
_MODEL_LOCK = threading.Lock()


def _to_number(value, default=0.0):
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def get_data_fingerprint():
    """Cheap aggregate that changes whenever product-analysis data changes."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT COUNT(*), COALESCE(SUM(units_sold), 0), COALESCE(SUM(total_sales), 0) "
            "FROM fact_product_analysis"
        )
        count, sum_units, sum_sales = cursor.fetchone()
    return f"{count}:{_to_number(sum_units):.2f}:{_to_number(sum_sales):.2f}"


def get_demand_cutoffs():
    """Data-driven tercile cut-offs on units_sold (Low / Medium / High)."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT percentile_cont(0.333) WITHIN GROUP (ORDER BY units_sold), "
            "percentile_cont(0.667) WITHIN GROUP (ORDER BY units_sold) "
            "FROM fact_product_analysis"
        )
        low_max, medium_max = cursor.fetchone()
    low_max = _to_number(low_max, 0.0)
    medium_max = _to_number(medium_max, low_max)
    if medium_max < low_max:
        medium_max = low_max
    return round(low_max, 2), round(medium_max, 2)


def load_training_frequency(low_max, medium_max):
    """
    Fetch the weighted frequency table for ID3 training.

    Each row = (wishlist, cart, purchase, target_bucket, count). The target
    bucket is derived from units_sold via the tercile cut-offs. Distinct
    indicator combinations collapse to a few thousand rows, giving identical
    ID3 output to the full dataset at a fraction of the transfer cost.
    """
    query = """
        SELECT
            COALESCE(wishlist_count, 0)::int,
            COALESCE(cart_count, 0)::int,
            COALESCE(purchase_count, 0)::int,
            CASE
                WHEN COALESCE(units_sold, 0) <= %s THEN 'Low'
                WHEN COALESCE(units_sold, 0) <= %s THEN 'Medium'
                ELSE 'High'
            END,
            COUNT(*)::int
        FROM fact_product_analysis
        GROUP BY 1, 2, 3, 4
    """
    with connection.cursor() as cursor:
        cursor.execute(query, [low_max, medium_max])
        rows = cursor.fetchall()

    dataset = []
    for wl, cart, purch, target, count in rows:
        dataset.append({
            'wishlist_count': float(wl or 0),
            'cart_count': float(cart or 0),
            'purchase_count': float(purch or 0),
            'target': target,
            'count': int(count or 0),
        })
    return dataset


def _build_model():
    """Run the ID3 pipeline over the frequency table and return the model dict."""
    t_start = time.perf_counter()

    low_max, medium_max = get_demand_cutoffs()
    dataset = load_training_frequency(low_max, medium_max)

    if not dataset:
        return {
            'success': False,
            'error': 'No product-analysis records found in fact_product_analysis.',
        }

    t_train = time.perf_counter()

    root_entropy = _engine.calculate_entropy(dataset)
    feature_gains = _engine.evaluate_feature_gains(dataset, root_entropy)
    best_split = _engine.find_best_split(dataset, root_entropy)
    tree = _engine.build_tree(dataset, depth=0, max_depth=_MAX_DEPTH)

    best_split_summary = {
        'feature': best_split['feature'],
        'feature_label': best_split['feature'].replace('_', ' ').title() if best_split['feature'] else 'N/A',
        'threshold': best_split['threshold'],
        'information_gain': best_split['information_gain'],
        'explanation': (
            f"The optimal root split is on '{best_split['feature'].replace('_', ' ').title()}' "
            f"at threshold <= {best_split['threshold']}, yielding the maximum Information Gain "
            f"of {best_split['information_gain']} bits."
            if best_split['feature'] else "No valid split found."
        ),
    }

    # Precompute exact per-product distributions from the weighted table so no
    # further 90k-row fetch or repeat calculation is needed to serve the page.
    predicted_dist = {'High': 0, 'Medium': 0, 'Low': 0}
    actual_dist = {label: 0 for label in DecisionTreeEngine.CLASS_ORDER}
    for combo in dataset:
        sample = {f: combo[f] for f in DecisionTreeEngine.FEATURE_NAMES}
        predicted_dist[_engine.predict_sample(tree, sample)] += combo['count']
        actual_dist[combo['target']] = actual_dist.get(combo['target'], 0) + combo['count']

    t_done = time.perf_counter()
    return {
        'success': True,
        'cutoffs': {'low_max': low_max, 'medium_max': medium_max},
        'root_entropy': root_entropy,
        'feature_gains': feature_gains,
        'best_split': best_split_summary,
        'decision_tree': tree,
        'predicted_distribution': predicted_dist,
        'actual_distribution': actual_dist,
        'training_rows': len(dataset),
        'training_products': int(_engine.weighted_size(dataset)),
        'fetch_ms': round((t_train - t_start) * 1000),
        'train_ms': round((t_done - t_train) * 1000),
        'built_at': time.time(),
    }


def get_trained_model(force_refresh=False):
    """Return the cached ID3 model, rebuilding it if the data fingerprint moved."""
    fingerprint = get_data_fingerprint()
    with _MODEL_LOCK:
        cached = _MODEL_CACHE.get('model')
        if (
            not force_refresh
            and cached is not None
            and cached.get('success')
            and _MODEL_CACHE.get('fingerprint') == fingerprint
        ):
            return cached, fingerprint, False
        model = _build_model()
        _MODEL_CACHE['model'] = model
        _MODEL_CACHE['fingerprint'] = fingerprint
        return model, fingerprint, True


def build_analytics_summary(force_refresh=False):
    """Assemble the analytics payload consumed by the forecasting dashboard."""
    t0 = time.perf_counter()
    model, fingerprint, rebuilt = get_trained_model(force_refresh=force_refresh)
    if not model.get('success'):
        return model

    distribution = model['predicted_distribution']
    total_products = sum(distribution.values())

    return {
        'success': True,
        'metadata': {
            'module_name': 'Demand Forecasting & Prediction',
            'algorithm': 'Manual ID3 Decision Tree Classifier (Entropy & Information Gain)',
            'features': DecisionTreeEngine.FEATURE_NAMES,
            'target': 'units_sold tercile demand bucket',
            'source_tables': ['public.fact_product_analysis', 'public.dim_product'],
            'training_products': model['training_products'],
            'training_combinations': model['training_rows'],
            'total_products_analyzed': total_products,
            'model_rebuilt': rebuilt,
            'fetch_ms': model['fetch_ms'],
            'train_ms': model['train_ms'],
            'build_ms': round((time.perf_counter() - t0) * 1000),
        },
        'summary': {
            'total_products': total_products,
            'root_entropy': model['root_entropy'],
            'demand_cutoffs': model['cutoffs'],
            'predicted_distribution': distribution,
            'actual_distribution': model['actual_distribution'],
        },
        'entropy': {
            'root_entropy': model['root_entropy'],
            'formula': 'H(S) = - sum( p_i * log2(p_i) )',
            'description': (
                f"Root dataset entropy is {model['root_entropy']} bits across the 3 "
                f"demand classes (High, Medium, Low)."
            ),
        },
        'information_gains': model['feature_gains'],
        'best_split': model['best_split'],
        'decision_tree': model['decision_tree'],
    }


# ==========================================================================
# Per-product classification helpers (used by the products endpoint + the
# legacy run_pipeline below).
# ==========================================================================
def classify_sample(tree, sample):
    prediction, steps = _engine.explain_prediction(tree, sample)
    return prediction, steps


def _sql_quote_feature(feat):
    # Feature names are from a fixed internal whitelist, never user input.
    if feat not in DecisionTreeEngine.FEATURE_NAMES:
        raise ValueError(f"Unexpected feature name: {feat}")
    return feat


def tree_to_sql_case(tree, params=None):
    """
    Serialise the trained tree into a SQL CASE expression returning the demand
    label, so filtering/ordering happens server-side without shipping rows.
    Returns (sql_string, params_list).
    """
    if params is None:
        params = []
    if tree.get('is_leaf'):
        return f"'{tree['prediction']}'", params
    feat = _sql_quote_feature(tree['feature'])
    left_sql, params = tree_to_sql_case(tree['left'], params + [tree['threshold']])
    right_sql, params = tree_to_sql_case(tree['right'], params)
    expr = f"CASE WHEN COALESCE({feat}, 0) <= %s THEN {left_sql} ELSE {right_sql} END"
    return expr, params


def recommended_action(predicted_demand, available_quantity, units_sold):
    """
    Short, plain-language action for a warehouse manager.

    Anchored strictly to the demand class and the real available_quantity. It
    never invents a numeric reorder quantity -- it points at the evidence.
    """
    stock = _to_number(available_quantity, 0.0)
    no_stock = stock <= 0
    if predicted_demand == 'High':
        if no_stock:
            return 'Urgent: restock now - high demand but no available stock.'
        return 'Prioritise replenishment; monitor stock closely.'
    if predicted_demand == 'Medium':
        if no_stock:
            return 'Review replenishment needs - steady demand but out of stock.'
        return 'Review replenishment needs.'
    # Low
    if stock > 0:
        return 'Low demand signal - consider promotion before restocking.'
    return 'Low demand and no stock - no immediate replenishment.'


# ==========================================================================
# Full-catalog pipeline entry point (retained for backward compatibility and
# the demand test suite). Returns a demand tier for every product.
# ==========================================================================
def _run_pipeline_full():
    model, fingerprint, rebuilt = get_trained_model()
    if not model.get('success'):
        return {'success': False, 'error': model.get('error', 'Failed to build demand model.')}

    tree = model['decision_tree']
    query = """
        SELECT product_key,
               COALESCE(wishlist_count, 0), COALESCE(cart_count, 0),
               COALESCE(purchase_count, 0), COALESCE(units_sold, 0), COALESCE(total_sales, 0)
        FROM fact_product_analysis
    """
    with connection.cursor() as cursor:
        cursor.execute(query)
        rows = cursor.fetchall()

    predictions = []
    dist = {'High': 0, 'Medium': 0, 'Low': 0}
    for product_key, wl, cart, purch, units, sales in rows:
        sample = {
            'wishlist_count': _to_number(wl),
            'cart_count': _to_number(cart),
            'purchase_count': _to_number(purch),
        }
        label = _engine.predict_sample(tree, sample)
        dist[label] = dist.get(label, 0) + 1
        predictions.append({
            'product_key': product_key,
            'units_sold': _to_number(units),
            'total_sales': _to_number(sales),
            'predicted_demand': label,
        })

    return {
        'success': True,
        'metadata': {
            'module_name': 'Demand Forecasting & Prediction',
            'algorithm': 'Manual ID3 Decision Tree Classifier',
            'training_products': model['training_products'],
            'total_products_analyzed': len(predictions),
            'model_rebuilt': rebuilt,
        },
        'summary': {
            'total_products': len(predictions),
            'demand_cutoffs': model['cutoffs'],
            'predicted_distribution': dist,
        },
        'entropy': {'root_entropy': model['root_entropy']},
        'information_gains': model['feature_gains'],
        'best_split': model['best_split'],
        'decision_tree': tree,
        'product_predictions': predictions,
    }


def run_pipeline():
    """
    Defensive entry point: returns a failure dict instead of raising when the
    warehouse tables are unavailable (e.g. an empty CI test database).
    """
    try:
        return _run_pipeline_full()
    except Exception as exc:
        return {'success': False, 'error': str(exc)}


# Re-export so existing imports (`from demand_prediction.engine import DecisionTreeEngine`)
# keep working while exposing the new functional API.
DecisionTreeEngine.run_pipeline = staticmethod(run_pipeline)
