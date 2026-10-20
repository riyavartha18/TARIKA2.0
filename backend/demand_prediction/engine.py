import math
from django.db import connection


class DecisionTreeEngine:
    """
    Pure Python Manual Implementation of Decision Tree Classifier for Demand Prediction.
    Strictly avoids sklearn or external ML libraries.

    Mathematical Workflow:
    1. Historical Demand Classification -> Target creation (High, Medium, Low)
    2. Entropy Calculation -> H(S) = - sum(p_i * log2(p_i))
    3. Information Gain Calculation -> IG(S, F, T) = H(S) - H_split(S, F, T)
    4. Best Split Selection -> Feature & Threshold maximizing IG
    5. Recursive Tree Construction
    6. Product Demand Prediction
    """

    FEATURE_NAMES = ['units_sold', 'cart_quantity', 'wishlist_count', 'discount_percentage', 'notify_me_count']

    @staticmethod
    def calculate_entropy(targets):
        """
        Calculates Shannon Entropy H(S) for a list of target class labels.
        H(S) = - sum(p_i * log2(p_i))
        """
        if not targets:
            return 0.0
        
        n = len(targets)
        counts = {}
        for label in targets:
            counts[label] = counts.get(label, 0) + 1
        
        entropy = 0.0
        for count in counts.values():
            p = count / n
            if p > 0:
                entropy -= p * math.log2(p)
        
        return round(entropy, 4)

    @classmethod
    def calculate_split_gain(cls, dataset, feature, threshold, parent_entropy):
        """
        Calculates Information Gain for a candidate split (feature <= threshold).
        """
        n_total = len(dataset)
        if n_total == 0:
            return 0.0, [], []

        left_samples = [d for d in dataset if d[feature] <= threshold]
        right_samples = [d for d in dataset if d[feature] > threshold]

        if not left_samples or not right_samples:
            return 0.0, left_samples, right_samples

        left_targets = [d['target'] for d in left_samples]
        right_targets = [d['target'] for d in right_samples]

        entropy_left = cls.calculate_entropy(left_targets)
        entropy_right = cls.calculate_entropy(right_targets)

        weighted_entropy = (len(left_samples) / n_total) * entropy_left + (len(right_samples) / n_total) * entropy_right
        information_gain = parent_entropy - weighted_entropy

        return round(information_gain, 4), left_samples, right_samples

    @classmethod
    def evaluate_feature_gains(cls, dataset, parent_entropy):
        """
        Calculates the maximum Information Gain and optimal threshold for EACH feature at a given node.
        Used for reporting root feature importance.
        """
        feature_report = {}

        for feat in cls.FEATURE_NAMES:
            values = sorted(list(set([d[feat] for d in dataset])))
            best_gain = 0.0
            best_threshold = None

            if len(values) > 1:
                # Generate candidate thresholds (midpoints between consecutive distinct values)
                candidates = [(values[i] + values[i + 1]) / 2.0 for i in range(len(values) - 1)]
                # If too many candidate thresholds, subsample evenly up to 50 for efficiency
                if len(candidates) > 50:
                    step = len(candidates) // 50
                    candidates = candidates[::step]
            elif len(values) == 1:
                candidates = [values[0]]
            else:
                candidates = []

            for t in candidates:
                gain, left, right = cls.calculate_split_gain(dataset, feat, t, parent_entropy)
                if gain > best_gain:
                    best_gain = gain
                    best_threshold = t

            feature_report[feat] = {
                'gain': round(best_gain, 4),
                'best_threshold': round(best_threshold, 4) if best_threshold is not None else (round(values[0], 4) if values else 0.0),
                'feature_label': feat.replace('_', ' ').title()
            }

        # Sort feature report by Information Gain descending
        sorted_gains = dict(sorted(feature_report.items(), key=lambda item: item[1]['gain'], reverse=True))
        rank = 1
        for k in sorted_gains:
            sorted_gains[k]['rank'] = rank
            rank += 1

        return sorted_gains

    @classmethod
    def find_best_split(cls, dataset, parent_entropy):
        """
        Finds the single best feature and threshold split across all candidate features.
        """
        best_gain = -1.0
        best_feature = None
        best_threshold = None
        best_left = []
        best_right = []

        for feat in cls.FEATURE_NAMES:
            values = sorted(list(set([d[feat] for d in dataset])))
            if len(values) <= 1:
                continue

            candidates = [(values[i] + values[i + 1]) / 2.0 for i in range(len(values) - 1)]
            if len(candidates) > 50:
                step = len(candidates) // 50
                candidates = candidates[::step]

            for t in candidates:
                gain, left, right = cls.calculate_split_gain(dataset, feat, t, parent_entropy)
                if gain > best_gain and left and right:
                    best_gain = gain
                    best_feature = feat
                    best_threshold = t
                    best_left = left
                    best_right = right

        return {
            'feature': best_feature,
            'threshold': round(best_threshold, 4) if best_threshold is not None else None,
            'information_gain': round(max(best_gain, 0.0), 4),
            'left': best_left,
            'right': best_right
        }

    @classmethod
    def build_tree(cls, dataset, depth=0, max_depth=3, node_counter=None):
        """
        Recursively constructs the Decision Tree.
        """
        if node_counter is None:
            node_counter = [0]

        node_id = f"node_{node_counter[0]}"
        node_counter[0] += 1

        targets = [d['target'] for d in dataset]
        n_samples = len(dataset)

        # Count occurrences of class labels
        value_counts = {
            'High': targets.count('High'),
            'Medium': targets.count('Medium'),
            'Low': targets.count('Low')
        }

        # Majority class prediction
        prediction = max(value_counts, key=value_counts.get) if n_samples > 0 else 'Medium'
        node_entropy = cls.calculate_entropy(targets)

        # Check stopping criteria: pure node, max depth reached, or insufficient samples
        if node_entropy == 0.0 or depth >= max_depth or n_samples < 5:
            return {
                'node_id': node_id,
                'is_leaf': True,
                'prediction': prediction,
                'entropy': node_entropy,
                'samples': n_samples,
                'value_counts': value_counts,
                'depth': depth
            }

        split = cls.find_best_split(dataset, node_entropy)

        # If no valid split found or gain is zero
        if not split['feature'] or split['information_gain'] <= 0.0001 or not split['left'] or not split['right']:
            return {
                'node_id': node_id,
                'is_leaf': True,
                'prediction': prediction,
                'entropy': node_entropy,
                'samples': n_samples,
                'value_counts': value_counts,
                'depth': depth
            }

        left_node = cls.build_tree(split['left'], depth + 1, max_depth, node_counter)
        right_node = cls.build_tree(split['right'], depth + 1, max_depth, node_counter)

        return {
            'node_id': node_id,
            'is_leaf': False,
            'feature': split['feature'],
            'feature_label': split['feature'].replace('_', ' ').title(),
            'threshold': split['threshold'],
            'gain': split['information_gain'],
            'entropy': node_entropy,
            'samples': n_samples,
            'value_counts': value_counts,
            'prediction': prediction,
            'depth': depth,
            'left': left_node,
            'right': right_node
        }

    @classmethod
    def predict_sample(cls, node, sample):
        """
        Traverses Decision Tree to predict demand category for a given sample.
        """
        if node.get('is_leaf'):
            return node.get('prediction', 'Medium')

        feat = node['feature']
        thresh = node['threshold']

        if sample.get(feat, 0) <= thresh:
            return cls.predict_sample(node['left'], sample)
        else:
            return cls.predict_sample(node['right'], sample)

    @classmethod
    def run_pipeline(cls):
        """
        Fetches historical monthly demand data from fact_demand + dim_time,
        reads notify_me_count directly from fact_demand,
        constructs supervised transition pairs (Month m -> Month m+1),
        trains a manual Decision Tree Classifier, and generates genuine next-month
        demand predictions (High, Medium, Low) for all catalog products based on their
        latest historical month metrics.
        """
        cursor = connection.cursor()
        
        # Determine latest month in historical data (from fact_demand + dim_time)
        cursor.execute("""
            SELECT dt.year, dt.month, dt.month_name
            FROM fact_demand fd
            JOIN dim_time dt ON fd.time_key = dt.time_key
            WHERE dt.year IS NOT NULL AND dt.month IS NOT NULL
            ORDER BY dt.year DESC, dt.month DESC
            LIMIT 1
        """)
        latest_time_row = cursor.fetchone()

        MONTH_NAMES = [
            "January", "February", "March", "April", "May", "June", 
            "July", "August", "September", "October", "November", "December"
        ]

        if latest_time_row:
            latest_year, latest_month, latest_month_name = latest_time_row
            if latest_month == 12:
                next_month_num = 1
                next_year = latest_year + 1
            else:
                next_month_num = latest_month + 1
                next_year = latest_year
            next_month_name = MONTH_NAMES[next_month_num - 1]
            next_forecast_period = f"{next_month_name} {next_year}"
            latest_month_period = f"{latest_month_name} {latest_year}"
        else:
            next_month_name = "October"
            next_year = 2026
            next_forecast_period = "October 2026"
            latest_month_period = "September 2026"

        # 1. Fetch historical demand observations (notify_me_count comes directly from fact_demand)
        query = """
            SELECT 
                fd.product_key,
                COALESCE(dp.product_name, CONCAT('Product #', fd.product_key)) as product_name,
                COALESCE(dc.category_name, 'General Catalog') as category_name,
                dt.month_start,
                COALESCE(p.base_price, dp.selling_price, 0) as base_price,
                fd.units_sold,
                fd.cart_quantity,
                fd.wishlist_count,
                fd.discount_amount,
                COALESCE(fd.notify_me_count, 0) as notify_me_count
            FROM fact_demand fd
            JOIN dim_time dt ON fd.time_key = dt.time_key
            LEFT JOIN dim_product dp ON fd.product_key = dp.product_key
            LEFT JOIN products p ON dp.product_id = p.product_id
            LEFT JOIN dim_category dc ON fd.category_key = dc.category_key
            ORDER BY fd.product_key ASC, dt.month_start ASC
        """
        cursor.execute(query)
        rows = cursor.fetchall()

        if not rows:
            return {
                'success': False,
                'error': 'No historical records found in fact_demand table.'
            }

        # 2. Group records by product
        from collections import defaultdict
        product_records = defaultdict(list)
        for r in rows:
            p_key = r[0]
            product_records[p_key].append({
                'product_key': p_key,
                'product_name': r[1],
                'category_name': r[2],
                'month_start': r[3],
                'base_price': float(r[4] or 0),
                'units_sold': float(r[5] or 0),
                'cart_quantity': float(r[6] or 0),
                'wishlist_count': float(r[7] or 0),
                'discount_amount': float(r[8] or 0),
                'discount_percentage': (
                    min(100.0, max(0.0, float(r[8] or 0) / float(r[4]) * 100))
                    if r[4] and float(r[4]) > 0 else 0.0
                ),
                'notify_me_count': float(r[9] or 0)
            })

        # 3. Build supervised training transition pairs: X_m -> Y_{m+1}
        training_pairs = []
        for p_key, recs in product_records.items():
            recs_sorted = sorted(recs, key=lambda x: x['month_start'])
            for i in range(len(recs_sorted) - 1):
                curr_rec = recs_sorted[i]
                next_rec = recs_sorted[i+1]
                training_pairs.append({
                    'product_key': p_key,
                    'product_name': curr_rec['product_name'],
                    'category_name': curr_rec['category_name'],
                    'units_sold': curr_rec['units_sold'],
                    'cart_quantity': curr_rec['cart_quantity'],
                    'wishlist_count': curr_rec['wishlist_count'],
                    'discount_percentage': curr_rec['discount_percentage'],
                    'notify_me_count': curr_rec['notify_me_count'],
                    'next_units_sold': next_rec['units_sold']
                })

        # 4. Categorize Next-Month Target Demand (Low, Medium, High)
        low_max = 2.0
        medium_max = 6.0
        
        for p in training_pairs:
            u = p['next_units_sold']
            if u <= low_max:
                p['target'] = 'Low'
            elif u <= medium_max:
                p['target'] = 'Medium'
            else:
                p['target'] = 'High'

        targets = [p['target'] for p in training_pairs]
        total_training_samples = len(training_pairs)

        # 5. Calculate Root Entropy
        root_entropy = cls.calculate_entropy(targets)

        # 6. Calculate Information Gain for EACH feature at Root
        feature_gains = cls.calculate_feature_gains_report(training_pairs, root_entropy)

        # 7. Determine Best Split at Root
        best_split_info = cls.find_best_split(training_pairs, root_entropy)
        
        best_split_summary = {
            'feature': best_split_info['feature'],
            'feature_label': best_split_info['feature'].replace('_', ' ').title() if best_split_info['feature'] else 'N/A',
            'threshold': best_split_info['threshold'],
            'information_gain': best_split_info['information_gain'],
            'explanation': f"The optimal root split is on '{best_split_info['feature'].replace('_', ' ').title()}' at threshold <= {best_split_info['threshold']}, yielding the maximum Information Gain of {best_split_info['information_gain']} bits." if best_split_info['feature'] else "No valid split found."
        }

        # 8. Construct Manual Decision Tree
        decision_tree = cls.build_tree(training_pairs, depth=0, max_depth=3)

        # 9. Generate Genuine Next-Month Demand Predictions for all catalog products
        cursor.execute("""
            SELECT
                dp.product_key,
                dp.product_name,
                COALESCE(dc.category_name, 'General Catalog'),
                COALESCE(dp.size, ''),
                COALESCE(dp.color, ''),
                COALESCE(p.base_price, dp.selling_price, 0)
            FROM dim_product dp
            LEFT JOIN products p ON dp.product_id = p.product_id
            LEFT JOIN dim_category dc ON dp.category_id = dc.category_id
            ORDER BY dp.product_key ASC
        """)
        catalog_rows = cursor.fetchall()

        product_predictions = []
        high_count = 0
        med_count = 0
        low_count = 0

        for cat_row in catalog_rows:
            p_key = cat_row[0]
            p_name = cat_row[1]
            c_name = cat_row[2]
            p_size = cat_row[3]
            p_color = cat_row[4]
            base_price = float(cat_row[5] or 0)

            if p_key in product_records and product_records[p_key]:
                recs_sorted = sorted(product_records[p_key], key=lambda x: x['month_start'])
                latest_rec = recs_sorted[-1]
                latest_units = round(latest_rec['units_sold'], 2)
                latest_cart = round(latest_rec['cart_quantity'], 2)
                latest_wishlist = round(latest_rec['wishlist_count'], 2)
                latest_discount_amount = latest_rec['discount_amount']
                latest_discount = round(latest_rec['discount_percentage'], 2)
                latest_notify = round(latest_rec['notify_me_count'], 2)
                sample = {
                    'units_sold': latest_rec['units_sold'],
                    'cart_quantity': latest_rec['cart_quantity'],
                    'wishlist_count': latest_rec['wishlist_count'],
                    'discount_percentage': latest_rec['discount_percentage'],
                    'notify_me_count': latest_rec['notify_me_count']
                }
            else:
                latest_units = 0.0
                latest_cart = 0.0
                latest_wishlist = 0.0
                latest_discount_amount = 0.0
                latest_discount = 0.0
                latest_notify = 0.0
                sample = {
                    'units_sold': 0.0,
                    'cart_quantity': 0.0,
                    'wishlist_count': 0.0,
                    'discount_percentage': 0.0,
                    'notify_me_count': 0.0
                }

            pred_demand = cls.predict_sample(decision_tree, sample)
            if pred_demand == 'High':
                high_count += 1
            elif pred_demand == 'Medium':
                med_count += 1
            else:
                low_count += 1

            product_predictions.append({
                'product_key': p_key,
                'product_name': p_name,
                'category_name': c_name,
                'size': p_size,
                'color': p_color,
                'base_price': base_price,
                'latest_historical_month': latest_month_period,
                'latest_units_sold': latest_units,
                'latest_cart_quantity': latest_cart,
                'latest_wishlist_count': latest_wishlist,
                'latest_discount_amount': latest_discount_amount,
                'latest_discount_percentage': latest_discount,
                'latest_notify_me_count': latest_notify,
                'units_sold': latest_units,
                'cart_quantity': latest_cart,
                'wishlist_count': latest_wishlist,
                'discount_percentage': latest_discount,
                'notify_me_count': latest_notify,
                'next_month': next_month_name,
                'next_forecast_period': next_forecast_period,
                'predicted_demand': pred_demand
            })

        total_products = len(product_predictions)

        # Calculate accuracy score on historical transition dataset
        transition_matches = sum(1 for p in training_pairs if cls.predict_sample(decision_tree, p) == p['target'])
        accuracy_percentage = round((transition_matches / total_training_samples) * 100, 2) if total_training_samples > 0 else 100.0

        # Total row count from fact_demand for metadata
        cursor.execute("SELECT COUNT(*) FROM fact_demand")
        fact_demand_total_rows = cursor.fetchone()[0]

        return {
            'success': True,
            'metadata': {
                'module_name': 'Demand Forecasting & Prediction',
                'algorithm': 'Manual Decision Tree Classifier (Entropy & Information Gain)',
                'latest_historical_month': latest_month_period,
                'next_forecast_month': next_month_name,
                'next_forecast_period': next_forecast_period,
                'total_historical_rows': fact_demand_total_rows,
                'total_training_pairs': total_training_samples,
                'total_products_analyzed': total_products,
                'accuracy_percentage': accuracy_percentage
            },
            'summary': {
                'total_products': total_products,
                'latest_historical_month': latest_month_period,
                'next_forecast_month': next_month_name,
                'next_forecast_period': next_forecast_period,
                'root_entropy': root_entropy,
                'demand_cutoffs': {
                    'low_max': low_max,
                    'medium_max': medium_max
                },
                'predicted_distribution': {
                    'High': high_count,
                    'Medium': med_count,
                    'Low': low_count
                },
                'actual_distribution': {
                    'High': targets.count('High'),
                    'Medium': targets.count('Medium'),
                    'Low': targets.count('Low')
                }
            },
            'entropy': {
                'root_entropy': root_entropy,
                'formula': 'H(S) = - sum( p_i * log2(p_i) )',
                'description': f"Root dataset entropy is {root_entropy} bits across 3 target next-month demand classes (High, Medium, Low)."
            },
            'information_gains': feature_gains,
            'best_split': best_split_summary,
            'decision_tree': decision_tree,
            'product_predictions': product_predictions
        }

    @classmethod
    def calculate_feature_gains_report(cls, dataset, root_entropy):
        return cls.evaluate_feature_gains(dataset, root_entropy)
