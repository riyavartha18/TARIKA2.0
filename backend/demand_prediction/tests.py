from django.test import SimpleTestCase
from demand_prediction import engine
from demand_prediction.engine import DecisionTreeEngine
from demand_prediction import inventory_metrics as im


class InventoryVelocityClassificationTest(SimpleTestCase):
    """The transparent, configurable tier rules for the Admin analysis."""

    def test_zero_sales_is_never_fast_moving(self):
        # A product with stock but no sales in the window is NON MOVING, and
        # days_of_stock is reported as None (∞ / No Sales), never 0.
        movement, avg, days = im.classify(stock=500, units=0)
        self.assertEqual(movement, im.MOVEMENT_NON_MOVING)
        self.assertEqual(avg, 0.0)
        self.assertIsNone(days)

    def test_fast_moving_low_days_of_stock(self):
        # 30 units / 30 days = 1/day; 10 stock -> 10 days <= 15 -> FAST MOVING.
        movement, avg, days = im.classify(stock=10, units=30)
        self.assertEqual(avg, 1.0)
        self.assertEqual(days, 10.0)
        self.assertEqual(movement, im.MOVEMENT_FAST)

    def test_normal_and_slow_bands(self):
        # avg 1/day: 40 stock -> 40 days (16-60) NORMAL.
        self.assertEqual(im.classify(stock=40, units=30)[0], im.MOVEMENT_NORMAL)
        # 120 stock -> 120 days (61-180) SLOW.
        self.assertEqual(im.classify(stock=120, units=30)[0], im.MOVEMENT_SLOW)
        # 400 stock -> 400 days (>180) NON MOVING.
        self.assertEqual(im.classify(stock=400, units=30)[0], im.MOVEMENT_NON_MOVING)

    def test_out_of_stock_with_sales_is_flagged_urgent(self):
        # Zero stock but genuine sales => needs replenishment (FAST MOVING),
        # and is never mislabelled NON MOVING just because stock is empty.
        movement, _avg, days = im.classify(stock=0, units=12)
        self.assertEqual(movement, im.MOVEMENT_FAST)
        self.assertEqual(days, 0.0)

    def test_thresholds_are_configurable_constants(self):
        # The documented defaults are the ones the SQL and Python share.
        self.assertEqual(im.SALES_WINDOW_DAYS, 30)
        self.assertEqual((im.FAST_MAX_DAYS, im.NORMAL_MAX_DAYS, im.SLOW_MAX_DAYS),
                         (15, 60, 180))
        self.assertEqual(
            list(im.MOVEMENT_LABELS),
            ['FAST MOVING', 'NORMAL', 'SLOW', 'NON MOVING'],
        )


class DemandPredictionEngineTest(SimpleTestCase):
    databases = {'default'}

    def test_feature_names_are_real_demand_indicators(self):
        """ID3 features must be demand indicators; stock/target are excluded."""
        self.assertEqual(
            set(DecisionTreeEngine.FEATURE_NAMES),
            {'wishlist_count', 'cart_count'},
        )
        self.assertNotIn('available_quantity', DecisionTreeEngine.FEATURE_NAMES)
        self.assertNotIn('units_sold', DecisionTreeEngine.FEATURE_NAMES)
        self.assertNotIn('purchase_count', DecisionTreeEngine.FEATURE_NAMES)

    def test_weighted_entropy_matches_manual_value(self):
        """Weighted entropy equals the unweighted case when counts are 1."""
        samples = [
            {'target': 'High', 'count': 1},
            {'target': 'High', 'count': 1},
            {'target': 'Low', 'count': 1},
            {'target': 'Low', 'count': 1},
        ]
        self.assertEqual(DecisionTreeEngine.calculate_entropy(samples), 1.0)

    def test_weighted_entropy_collapses_duplicates(self):
        """A row repeated by count behaves identically to repeated rows."""
        repeated = [{'target': 'High'}, {'target': 'High'}, {'target': 'Low'}]
        weighted = [{'target': 'High', 'count': 2}, {'target': 'Low', 'count': 1}]
        self.assertEqual(
            DecisionTreeEngine.calculate_entropy(repeated),
            DecisionTreeEngine.calculate_entropy(weighted),
        )

    def test_build_tree_and_predict(self):
        """ID3 builds a tree and predicts cleanly on a small dataset."""
        dataset = [
            {'wishlist_count': 0.0, 'cart_count': 0.0, 'target': 'Low', 'count': 40},
            {'wishlist_count': 10.0, 'cart_count': 20.0, 'target': 'High', 'count': 40},
            {'wishlist_count': 5.0, 'cart_count': 8.0, 'target': 'Medium', 'count': 20},
        ]
        tree = DecisionTreeEngine.build_tree(dataset, depth=0, max_depth=3)
        high, _ = DecisionTreeEngine.explain_prediction(
            tree, {'wishlist_count': 10.0, 'cart_count': 20.0}
        )
        self.assertEqual(high, 'High')

    def test_tree_to_sql_case_roundtrip(self):
        """The tree serialises to a CASE expression with one param per node."""
        dataset = [
            {'wishlist_count': 0.0, 'cart_count': 0.0, 'target': 'Low', 'count': 40},
            {'wishlist_count': 10.0, 'cart_count': 20.0, 'target': 'High', 'count': 40},
        ]
        tree = DecisionTreeEngine.build_tree(dataset, depth=0, max_depth=3)
        sql, params = engine.tree_to_sql_case(tree)
        self.assertIn('CASE', sql)
        self.assertTrue("'High'" in sql and "'Low'" in sql)
        # One numeric parameter is bound per internal (non-leaf) node.
        internal_nodes = sql.count('CASE')
        self.assertEqual(len(params), internal_nodes)
        for p in params:
            self.assertIsInstance(p, float)

    def test_recommended_action_distinguishes_stock_from_demand(self):
        """Action text references the real available_quantity, not demand."""
        high_out_of_stock = engine.recommended_action('High', 0, 50)
        self.assertIn('restock', high_out_of_stock.lower())
        self.assertNotIn('undefined', high_out_of_stock.lower())

    def test_run_pipeline_contract(self):
        """Full pipeline returns the shape downstream consumers expect, or a
        clean failure when the warehouse tables are unavailable."""
        try:
            results = engine.run_pipeline()
        except Exception:
            self.fail('run_pipeline must handle DB access defensively')
        self.assertIn('success', results)
        if results.get('success'):
            self.assertIn('product_predictions', results)
            for pred in results['product_predictions'][:5]:
                self.assertIn(pred['predicted_demand'], ['High', 'Medium', 'Low'])
