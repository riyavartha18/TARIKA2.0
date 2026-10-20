from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from revenue_forecasting.services import get_selling_price_map


class SellingPriceMapTests(SimpleTestCase):
    @patch('revenue_forecasting.services.connection')
    def test_uses_dim_product_selling_price(self, mock_connection):
        cursor = MagicMock()
        mock_connection.cursor.return_value.__enter__.return_value = cursor
        cursor.fetchall.return_value = [(12, 1999)]

        self.assertEqual(get_selling_price_map(), {12: 1999})
        query = cursor.execute.call_args.args[0]
        self.assertIn('dp.selling_price', query)
        self.assertNotIn(' p.selling_price', query)