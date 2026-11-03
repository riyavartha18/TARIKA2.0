from django.test import SimpleTestCase
from demand_prediction import engine, views
from demand_prediction.engine import DecisionTreeEngine
from demand_prediction import inventory_metrics as im


class InventoryVelocityClassificationTest(SimpleTestCase):
    """Movement is classified from ACTUAL sales quantity, not from stock."""

    # Tier cuts for a distribution: FAST > 4 units, NORMAL > 2, SLOW <= 2.
    FAST_CUT, NORMAL_CUT = 4.0, 2.0

    def test_zero_sales_is_always_not_moving(self):
        # Any zero-sales product is NOT MOVING regardless of stock, and its
        # days_of_stock is None ("No Sales") when it still holds stock.
        for stock in (0, 500):
            movement, avg, days = im.classify(0, self.FAST_CUT, self.NORMAL_CUT, stock=stock)
            self.assertEqual(movement, im.MOVEMENT_NOT)
            self.assertEqual(avg, 0.0)
        self.assertIsNone(im.classify(0, self.FAST_CUT, self.NORMAL_CUT, stock=500)[2])
        self.assertEqual(im.classify(0, self.FAST_CUT, self.NORMAL_CUT, stock=0)[2], 0.0)

    def test_higher_sales_never_lands_in_a_lower_tier(self):
        # As sales quantity grows, the tier rank only stays or improves
        # (lower rank number = higher movement tier); it never regresses.
        prev_rank = 99
        for units in range(0, 15):
            movement, _avg, _d = im.classify(units, self.FAST_CUT, self.NORMAL_CUT, stock=100)
            rank = im.MOVEMENT_RANK[movement]
            self.assertLessEqual(rank, prev_rank)
            prev_rank = rank

    def test_bands_by_sales_quantity(self):
        self.assertEqual(im.classify(10, self.FAST_CUT, self.NORMAL_CUT)[0], im.MOVEMENT_FAST)
        self.assertEqual(im.classify(3, self.FAST_CUT, self.NORMAL_CUT)[0], im.MOVEMENT_NORMAL)
        self.assertEqual(im.classify(2, self.FAST_CUT, self.NORMAL_CUT)[0], im.MOVEMENT_SLOW)
        self.assertEqual(im.classify(1, self.FAST_CUT, self.NORMAL_CUT)[0], im.MOVEMENT_SLOW)

    def test_stock_never_moves_a_product_up_a_tier(self):
        # Same sales, wildly different stock => same movement tier.
        low = im.classify(10, self.FAST_CUT, self.NORMAL_CUT, stock=1)[0]
        high = im.classify(10, self.FAST_CUT, self.NORMAL_CUT, stock=99999)[0]
        self.assertEqual(low, high)

    def test_avg_daily_and_days_of_stock_edges(self):
        # avg daily = units / 30 (2 dp); zero stock with sales => 0 days.
        _m, avg, days = im.classify(30, self.FAST_CUT, self.NORMAL_CUT, stock=0)
        self.assertEqual(avg, 1.0)
        self.assertEqual(days, 0.0)

    def test_tier_labels_and_display_priority(self):
        self.assertEqual(
            list(im.MOVEMENT_LABELS),
            ['FAST MOVING', 'NORMAL MOVING', 'SLOW MOVING', 'NOT MOVING'],
        )
        self.assertEqual(
            [im.MOVEMENT_RANK[l] for l in im.MOVEMENT_LABELS], [0, 1, 2, 3],
        )
        self.assertEqual(im.SALES_WINDOW_DAYS, 30)


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


class DemandSellingPriceSQLTest(SimpleTestCase):
    """The product-fetch selling price must be computed from the columns that
    actually exist (no `initial_price`) and never go negative."""

    def test_selling_price_does_not_reference_missing_initial_price(self):
        sql = views._SELLING_PRICE_SQL
        self.assertNotIn('initial_price', sql)

    def test_selling_price_subtracts_discount_from_parsed_actual_price(self):
        sql = views._SELLING_PRICE_SQL
        self.assertIn('d.actual_price', sql)
        self.assertIn('d.discount_price', sql)
        # Floored at 0 so a discount can never produce a negative price.
        self.assertTrue(sql.startswith('GREATEST(0,'))
