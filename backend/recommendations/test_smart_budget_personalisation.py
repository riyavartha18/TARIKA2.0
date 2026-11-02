import os
import sys
import django

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

import unittest
from decimal import Decimal
from recommendations.smart_budget_service import SmartBudgetOutfitService
from recommendations.outfit_validator import validate_outfit
from catalog.models import Product
from orders.models import Order
from cart.models import WishlistItem, CartItem


class SmartBudgetPersonalisationTests(unittest.TestCase):
    """
    Automated regression tests verifying all requirements for:
    1. Smart Budget Stylist Leftover Optimization
    2. Personalised First Outfits in Surprise Me
    """

    def test_leftover_never_negative(self):
        """Test that for all tested budgets, leftover is strictly non-negative (total <= budget)."""
        for b in [1000, 2000, 3000, 5000]:
            res = SmartBudgetOutfitService.generate_budget_outfits(
                budget=float(b),
                fashion_direction='all',
                gender='women',
                sort_by='best',
            )
            outfits = res.get('outfits', [])
            self.assertTrue(len(outfits) > 0, f"Expected outfits for budget {b}")
            for o in outfits:
                total = o.get('total_price', 0)
                coins_left = o.get('coins_remaining', 0)
                self.assertLessEqual(total, b, f"Outfit total {total} exceeds budget {b}")
                self.assertGreaterEqual(coins_left, 0, f"Coins remaining {coins_left} is negative")
                self.assertEqual(round(total + coins_left, 2), float(b))

    def test_gate_never_relaxed(self):
        """Test that every returned outfit strictly passes validate_outfit."""
        res = SmartBudgetOutfitService.generate_budget_outfits(
            budget=3000.0,
            fashion_direction='all',
            gender='women',
            sort_by='best',
        )
        outfits = res.get('outfits', [])
        self.assertTrue(len(outfits) > 0)
        for o in outfits:
            is_op = o.get('is_dress') or o.get('base_type') in ('one_piece', 'saree_lehenga')
            pieces = {
                'one_piece': o.get('topwear') if is_op else None,
                'top': None if is_op else o.get('topwear'),
                'bottom': None if is_op else o.get('bottomwear'),
                'footwear': o.get('footwear'),
                'bag': o.get('bag'),
                'layer': o.get('layer'),
            }
            if o.get('accessories'):
                pieces['accessories'] = o.get('accessories')

            valid, reasons = validate_outfit(
                pieces=pieces,
                user_prefs={'occasion': o.get('occasion', 'casual'), 'gender': 'women', 'budget': 3000.0},
            )
            self.assertTrue(valid, f"Outfit failed validate_outfit: {reasons}")

    def test_ethnic_at_3000_plus_returns_sarees(self):
        """Test that Ethnic direction at Rs.3000+ returns sarees."""
        res = SmartBudgetOutfitService.generate_budget_outfits(
            budget=3000.0,
            fashion_direction='ethnic',
            gender='women',
            occasion='festive',
            sort_by='best',
        )
        outfits = res.get('outfits', [])
        self.assertTrue(len(outfits) > 0)
        saree_outfits = [o for o in outfits if o.get('topwear', {}).get('subtype') == 'saree']
        self.assertTrue(len(saree_outfits) > 0, "Expected saree outfits in Ethnic at Rs.3,000+")

    def test_5000_does_not_return_outfits_under_3000(self):
        """Test that for Rs.5000, outfits utilize the budget and do not return under Rs.3000."""
        res = SmartBudgetOutfitService.generate_budget_outfits(
            budget=5000.0,
            fashion_direction='western',
            gender='women',
            sort_by='best',
        )
        outfits = res.get('outfits', [])
        self.assertTrue(len(outfits) > 0)
        for o in outfits:
            total = o.get('total_price', 0)
            self.assertGreaterEqual(
                total, 3000,
                f"Outfit total {total} is under Rs.3000 for a Rs.5000 budget"
            )

    def test_already_purchased_products_never_appear(self):
        """Test that products customer already bought are strictly excluded from recommendations."""
        cust_id = 'U100047'
        profile = SmartBudgetOutfitService.get_customer_taste_profile(cust_id)
        purchased_pids = profile.get('purchased_pids', set())
        self.assertTrue(len(purchased_pids) > 0, "Customer U100047 has purchases")
        
        res = SmartBudgetOutfitService.generate_budget_outfits(
            budget=3000.0,
            fashion_direction='all',
            gender='women',
            customer_id=cust_id,
            personalise=True,
        )
        outfits = res.get('outfits', [])
        self.assertTrue(len(outfits) > 0)
        for o in outfits:
            for slot in ['topwear', 'bottomwear', 'footwear', 'bag', 'layer']:
                item = o.get(slot)
                if item and item.get('product_id'):
                    self.assertNotIn(
                        item.get('product_id'), purchased_pids,
                        f"Purchased product {item.get('product_id')} appeared for customer {cust_id}"
                    )
            for acc in o.get('accessories', []):
                if acc and acc.get('product_id'):
                    self.assertNotIn(
                        acc.get('product_id'), purchased_pids,
                        f"Purchased accessory {acc.get('product_id')} appeared for customer {cust_id}"
                    )

    def test_customer_isolation(self):
        """Test that customer A's taste profile is strictly isolated from customer B."""
        profile_a = SmartBudgetOutfitService.get_customer_taste_profile('U100047')
        profile_b = SmartBudgetOutfitService.get_customer_taste_profile('U100071')
        profile_none = SmartBudgetOutfitService.get_customer_taste_profile('GUEST_999999')
        
        self.assertNotEqual(profile_a.get('purchased_pids'), profile_b.get('purchased_pids'))
        self.assertNotEqual(profile_a.get('anchors'), profile_b.get('anchors'))
        self.assertEqual(len(profile_none.get('purchased_pids', set())), 0)
        self.assertEqual(len(profile_none.get('anchors', [])), 0)

    def test_wishlist_anchor_price_counted_in_total(self):
        """Test that when a personalised outfit is built around an anchor, its price is counted in total."""
        cust_id = 'U100071'
        res = SmartBudgetOutfitService.generate_budget_outfits(
            budget=3000.0,
            fashion_direction='all',
            gender='women',
            customer_id=cust_id,
            personalise=True,
        )
        outfits = res.get('outfits', [])
        anchor_outfits = [o for o in outfits if 'wishlist' in (o.get('personalisation_reason') or '').lower()]
        for o in anchor_outfits:
            items = [o.get('topwear'), o.get('bottomwear'), o.get('footwear'), o.get('bag'), o.get('layer')] + (o.get('accessories') or [])
            calc_sum = sum(float(i.get('selling_price') or i.get('discount_price') or i.get('price') or 0) for i in items if i)
            self.assertEqual(round(calc_sum, 2), round(o.get('total_price', 0), 2))
            self.assertLessEqual(o.get('total_price', 0), 3000)


if __name__ == '__main__':
    unittest.main()
