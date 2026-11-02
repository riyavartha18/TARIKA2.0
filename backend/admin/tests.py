"""Unit tests for the Product Performance Map classification logic.

SimpleTestCase only: ``build_performance_map`` is a pure function, so the
quadrant math, the data-driven thresholds and the empty states are verified
without a database (per ``test_settings.py`` the suites never touch Neon).
"""

from django.test import SimpleTestCase

from admin.performance_map import (
    QUADRANT_DEFS,
    _merge_display_variants,
    _quadrant_key,
    build_performance_map,
)


def _row(name, product_count, units, revenue, key=None):
    return {
        'sub_category_key': key or name.lower(),
        'sub_category_display': name,
        'product_count': product_count,
        'units_sold': units,
        'revenue': revenue,
        'selling_products': product_count,
        'top_products': [],
    }


# Four subcategories, one per quadrant, so both medians are the mid-points of
# the fixture distribution: units (8+30)/2 = 19, revenue (600+7000)/2 = 3800.
FIXTURE = [
    _row('Star Thing', 5, 40.0, 9000.0, key='star thing'),
    _row('Volume Thing', 4, 30.0, 600.0, key='volume thing'),
    _row('Premium Thing', 3, 8.0, 7000.0, key='premium thing'),
    _row('Weak Thing', 2, 4.0, 300.0, key='weak thing'),
]


class QuadrantThresholdTests(SimpleTestCase):
    def test_thresholds_are_medians_of_the_fixture_not_constants(self):
        payload = build_performance_map(FIXTURE)
        self.assertEqual(payload['thresholds']['sales']['value'], 19.0)
        self.assertEqual(payload['thresholds']['revenue']['value'], 3800.0)

    def test_each_quadrant_receives_the_right_subcategory(self):
        payload = build_performance_map(FIXTURE)
        by_key = {q['key']: q['subcategories'] for q in payload['quadrants']}
        self.assertEqual(by_key['star'], ['Star Thing'])
        self.assertEqual(by_key['volume'], ['Volume Thing'])
        self.assertEqual(by_key['premium'], ['Premium Thing'])
        self.assertEqual(by_key['attention'], ['Weak Thing'])

    def test_quadrant_product_counts_sum_to_the_catalog(self):
        payload = build_performance_map(FIXTURE)
        self.assertEqual(
            sum(q['product_count'] for q in payload['quadrants']),
            payload['summary']['total_products'],
        )
        self.assertEqual(len(payload['quadrants']), len(QUADRANT_DEFS))

    def test_zero_sales_never_counts_as_high_sales(self):
        # A dead subcategory stays on the low side even when the median is 0.
        self.assertEqual(_quadrant_key(0.0, 5000.0, 0.0, 4000.0), 'premium')
        self.assertEqual(_quadrant_key(10.0, 0.0, 5.0, 0.0), 'volume')
        self.assertEqual(_quadrant_key(0.0, 0.0, 0.0, 0.0), 'attention')


class EmptyStateTests(SimpleTestCase):
    def test_no_products_returns_an_empty_state(self):
        payload = build_performance_map([])
        self.assertFalse(payload['data_available'])
        self.assertEqual(payload['points'], [])
        self.assertEqual(payload['quadrants'], [])
        self.assertIn('No catalog products', payload['note'])

    def test_no_delivered_sales_returns_an_empty_state(self):
        payload = build_performance_map([_row('Shoes', 5, 0.0, 0.0)])
        self.assertFalse(payload['data_available'])
        self.assertEqual(payload['thresholds']['sales']['value'], 0.0)
        self.assertIn('No delivered', payload['note'])

    def test_nothing_is_fabricated_when_sales_exist_but_revenue_does_not(self):
        payload = build_performance_map([_row('Shoes', 5, 10.0, 0.0)])
        self.assertFalse(payload['data_available'])
        self.assertEqual(payload['summary']['total_revenue'], 0.0)


class DisplayVariantTests(SimpleTestCase):
    def test_case_variants_merge_into_one_point(self):
        rows = [
            _row('Dresses', 10, 100.0, 1000.0),
            _row('dresses', 2, 5.0, 50.0, key='dresses'),
            _row('Top', 3, 40.0, 900.0),
        ]
        merged = _merge_display_variants(rows)
        self.assertEqual(len(merged), 2)
        dresses = merged['dresses']
        # Metrics add up, and the name kept is the variant that really occurs
        # with the most products.
        self.assertEqual(dresses['product_count'], 12)
        self.assertEqual(dresses['units_sold'], 105.0)
        self.assertEqual(dresses['name'], 'Dresses')

    def test_blank_sub_category_falls_back_to_uncategorized(self):
        merged = _merge_display_variants([_row('', 4, 10.0, 100.0, key='')])
        self.assertEqual(list(merged), ['__uncategorized__'])
        self.assertEqual(merged['__uncategorized__']['name'], 'Uncategorized')


class PointPayloadTests(SimpleTestCase):
    def test_point_carries_revenue_per_unit_and_quadrant(self):
        payload = build_performance_map(FIXTURE)
        star = next(p for p in payload['points'] if p['subcategory'] == 'Star Thing')
        self.assertEqual(star['revenue_per_unit'], 225.0)
        self.assertEqual(star['quadrant'], 'star')
        self.assertEqual(star['product_count'], 5)

    def test_shares_add_up_to_the_totals(self):
        # Each quadrant share is rounded to 1 dp, so the sums only agree to the
        # nearest whole percent.
        payload = build_performance_map(FIXTURE)
        self.assertAlmostEqual(sum(q['revenue_share'] for q in payload['quadrants']), 100.0, places=0)
        self.assertAlmostEqual(sum(q['sales_share'] for q in payload['quadrants']), 100.0, places=0)
