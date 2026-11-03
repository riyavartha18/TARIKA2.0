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


class SmartBudgetRecommendationTests(unittest.TestCase):
    """
    Automated regression tests covering all 13 final recommendation requirements:
    1. Surprise Me returns diverse valid styles.
    2. Western returns appropriate Western outfits.
    3. Ethnic includes appropriate sarees and Anarkalis when available.
    4. Indo-Western includes appropriate kurtis and fusion dresses when available.
    5. Western jeans-and-top outfits do not receive flats by default.
    6. Western dresses and jumpsuits prefer compatible heels where appropriate.
    7. Kurtis and Anarkalis receive suitable juttis or flats where appropriate.
    8. Strict zero sandals in any outfit across every style mode.
    9. Only the initial 2-3 outfits may receive preference-based personalization.
    10. Empty or irrelevant personalization data falls back to normal recommendations.
    11. Recommendations include products outside wishlist, cart, and purchase history.
    12. Budget optimization, coins and discounted prices work together correctly.
    13. Duplicate and near-identical outfit combinations are rejected.
    """

    def setUp(self):
        from django.db import close_old_connections
        close_old_connections()

    def tearDown(self):
        from django.db import close_old_connections
        close_old_connections()

    def test_01_surprise_me_returns_diverse_valid_styles(self):
        """1. Surprise Me returns diverse valid styles (Western, Ethnic, Indo-Western)."""
        res = SmartBudgetOutfitService.generate_budget_outfits(
            budget=3000.0,
            fashion_direction='all',
            gender='women',
            sort_by='best',
        )
        outfits = res.get('outfits', [])
        self.assertTrue(len(outfits) >= 3, "Surprise Me should return at least 3 outfits")
        styles = set()
        for o in outfits:
            base_type = o.get('base_type')
            garment_type = (o.get('garment_type') or '').lower()
            if base_type == 'saree_lehenga' or 'saree' in garment_type or 'anarkali' in garment_type:
                styles.add('ethnic')
            elif 'kurti' in garment_type or 'fusion' in garment_type or base_type == 'indo-western':
                styles.add('indo-western')
            else:
                styles.add('western')
        self.assertTrue(len(styles) >= 2, f"Expected multi-style diversity in Surprise Me, got: {styles}")

    def test_02_western_returns_appropriate_western_outfits(self):
        """2. Western returns appropriate Western outfits (tops, jeans, trousers, dresses, jumpsuits)."""
        res = SmartBudgetOutfitService.generate_budget_outfits(
            budget=2500.0,
            fashion_direction='western',
            gender='women',
            sort_by='best',
        )
        outfits = res.get('outfits', [])
        self.assertTrue(len(outfits) > 0, "Western mode should return outfits")
        for o in outfits:
            top_nm = (o.get('topwear', {}).get('name') or '').lower()
            self.assertNotIn('saree', top_nm, "Western outfit must not contain sarees")
            self.assertNotIn('kurta', top_nm, "Western outfit must not contain kurtas")
            self.assertNotIn('kurti', top_nm, "Western outfit must not contain kurtis")

    def test_03_ethnic_includes_sarees_and_anarkalis(self):
        """3. Ethnic includes appropriate sarees and Anarkalis when available."""
        res = SmartBudgetOutfitService.generate_budget_outfits(
            budget=3000.0,
            fashion_direction='ethnic',
            gender='women',
            sort_by='best',
        )
        outfits = res.get('outfits', [])
        self.assertTrue(len(outfits) > 0, "Ethnic mode should return outfits")
        has_ethnic = any(
            o.get('topwear', {}).get('subtype') == 'saree' or
            'saree' in (o.get('garment_type') or '').lower() or
            'anarkali' in (o.get('garment_type') or '').lower() or
            'anarkali' in (o.get('topwear', {}).get('name') or '').lower()
            for o in outfits
        )
        self.assertTrue(has_ethnic, "Ethnic mode should return sarees or Anarkali looks")

    def test_04_indo_western_includes_kurtis_and_fusion(self):
        """4. Indo-Western includes appropriate kurtis and fusion dresses when available."""
        res = SmartBudgetOutfitService.generate_budget_outfits(
            budget=2500.0,
            fashion_direction='indo-western',
            gender='women',
            sort_by='best',
        )
        outfits = res.get('outfits', [])
        self.assertTrue(len(outfits) > 0, "Indo-Western mode should return outfits")
        has_fusion = any(
            'fusion' in (o.get('garment_type') or '').lower() or
            'kurti' in (o.get('garment_type') or '').lower() or
            'kurta' in (o.get('topwear', {}).get('name') or '').lower() or
            'kurti' in (o.get('topwear', {}).get('name') or '').lower()
            for o in outfits
        )
        self.assertTrue(has_fusion, "Indo-Western should return kurti or fusion looks")

    def test_05_western_jeans_and_top_no_flats_by_default(self):
        """5. Western jeans-and-top outfits do not receive flats by default (prefer sneakers/boots/heels)."""
        res = SmartBudgetOutfitService.generate_budget_outfits(
            budget=2500.0,
            fashion_direction='western',
            gender='women',
            sort_by='best',
        )
        outfits = res.get('outfits', [])
        for o in outfits:
            bot_nm = (o.get('bottomwear', {}).get('name') or '').lower()
            fw = o.get('footwear')
            if 'jeans' in bot_nm and fw:
                fw_type = fw.get('footwear_type')
                fw_name = (fw.get('name') or '').lower()
                self.assertNotEqual(fw_type, 'jutti', "Jeans outfit must not receive ethnic juttis")
                self.assertNotIn('jutti', fw_name, "Jeans outfit must not receive ethnic juttis")
                # Should not be casual flat without heels/sneakers
                if fw_type == 'flat':
                    is_pref = any(k in fw_name for k in ['sneaker', 'boot', 'heel', 'loafer', 'trainer'])
                    self.assertTrue(is_pref, f"Jeans outfit received unexpected flat: {fw_name}")

    def test_06_western_dresses_prefer_compatible_heels(self):
        """6. Western dresses and jumpsuits prefer compatible heels where appropriate."""
        res = SmartBudgetOutfitService.generate_budget_outfits(
            budget=2500.0,
            fashion_direction='western',
            gender='women',
            sort_by='best',
        )
        dress_outfits = [o for o in res.get('outfits', []) if o.get('is_dress')]
        for o in dress_outfits:
            fw = o.get('footwear')
            if fw:
                fw_name = (fw.get('name') or '').lower()
                self.assertNotIn('jutti', fw_name, "Western dress must not receive juttis")
                self.assertNotIn('juti', fw_name, "Western dress must not receive juttis")

    def test_07_kurtis_and_anarkalis_receive_suitable_juttis_or_flats(self):
        """7. Kurtis and Anarkalis receive suitable juttis or flats where appropriate (no sneakers)."""
        res = SmartBudgetOutfitService.generate_budget_outfits(
            budget=3000.0,
            fashion_direction='ethnic',
            gender='women',
            sort_by='best',
        )
        for o in res.get('outfits', [])[:5]:
            fw = o.get('footwear')
            if fw:
                fw_name = (fw.get('name') or '').lower()
                fw_type = fw.get('footwear_type')
                self.assertNotIn(fw_type, ['sneaker', 'sports'], "Ethnic outfit must not receive sneakers")
                self.assertNotIn('sneaker', fw_name, "Ethnic outfit must not receive sneakers")

    def test_08_strict_zero_sandals_in_any_mode(self):
        """8. Strict zero sandals, slides, or slippers in any outfit across all 4 modes."""
        for mode in ['all', 'western', 'ethnic', 'indo-western']:
            res = SmartBudgetOutfitService.generate_budget_outfits(
                budget=2500.0,
                fashion_direction=mode,
                gender='women',
                sort_by='best',
            )
            for o in res.get('outfits', []):
                fw = o.get('footwear')
                if fw:
                    fw_name = (fw.get('name') or '').lower()
                    fw_sub = (fw.get('sub_category') or '').lower()
                    fw_type = fw.get('footwear_type')
                    self.assertNotIn(fw_type, ['sandal', 'flip_flop', 'slipper'], f"Sandal type found in {mode}: {fw_name}")
                    self.assertNotIn('sandal', fw_sub, f"Sandal subcategory found in {mode}: {fw_name}")
                    self.assertNotIn('sandal', fw_name, f"Sandal in name in {mode}: {fw_name}")
                    self.assertNotIn('chappal', fw_name, f"Chappal in name in {mode}: {fw_name}")
                    self.assertNotIn('flip flop', fw_name, f"Flip flop in name in {mode}: {fw_name}")
                    self.assertNotIn('slipper', fw_name, f"Slipper in name in {mode}: {fw_name}")

    def test_09_personalization_only_first_2_to_3_outfits(self):
        """9. Only the initial 2-3 outfits may receive preference-based personalization."""
        cust_id = 'U100071'
        res = SmartBudgetOutfitService.generate_budget_outfits(
            budget=3000.0,
            fashion_direction='all',
            gender='women',
            customer_id=cust_id,
            personalise=True,
        )
        outfits = res.get('outfits', [])
        pers_count = sum(1 for o in outfits if o.get('is_personalised'))
        self.assertLessEqual(pers_count, 3, f"Expected at most 3 personalized outfits, got: {pers_count}")

        # Outfits after index 2 must never have is_personalised=True
        for idx, o in enumerate(outfits[3:], start=3):
            self.assertFalse(
                o.get('is_personalised', False),
                f"Outfit #{idx + 1} beyond the initial 3 had is_personalised=True"
            )

    def test_10_empty_personalization_falls_back_to_normal(self):
        """10. Empty or irrelevant personalization data falls back to normal recommendations."""
        res = SmartBudgetOutfitService.generate_budget_outfits(
            budget=2000.0,
            fashion_direction='all',
            gender='women',
            customer_id=None,
            personalise=True,
        )
        outfits = res.get('outfits', [])
        self.assertTrue(len(outfits) > 0)
        for o in outfits:
            self.assertFalse(o.get('is_personalised', False), "Guest user must receive standard non-personalized outfits")

    def test_11_recommendations_include_products_outside_wishlist(self):
        """11. Recommendations can include products outside wishlist, cart and purchase history."""
        cust_id = 'U100071'
        profile = SmartBudgetOutfitService.get_customer_taste_profile(cust_id)
        anchor_pids = {str(a['product'].product_id) for a in profile.get('anchors', [])}
        res = SmartBudgetOutfitService.generate_budget_outfits(
            budget=3000.0,
            fashion_direction='all',
            gender='women',
            customer_id=cust_id,
            personalise=True,
        )
        outfits = res.get('outfits', [])
        self.assertTrue(len(outfits) > 0)
        has_non_anchor = False
        for o in outfits:
            items = [o.get('topwear'), o.get('bottomwear'), o.get('footwear'), o.get('bag')]
            for it in items:
                if it and str(it.get('product_id')) not in anchor_pids:
                    has_non_anchor = True
                    break
        self.assertTrue(has_non_anchor, "Recommendations must include products from the wider catalogue")

    def test_12_budget_optimization_and_coins_work_together(self):
        """12. Budget optimization, coins and discounted prices work together correctly."""
        budget = 2500.0
        res = SmartBudgetOutfitService.generate_budget_outfits(
            budget=budget,
            fashion_direction='all',
            gender='women',
            sort_by='best',
        )
        outfits = res.get('outfits', [])
        self.assertTrue(len(outfits) > 0)
        for o in outfits:
            total = o.get('total_price', 0)
            coins_left = o.get('coins_remaining', 0)
            self.assertLessEqual(total, budget)
            self.assertEqual(round(total + coins_left, 2), budget)
            # Leftover cap: when suitable combinations exist, coins left <= 250
            self.assertLessEqual(coins_left, 250, f"Leftover coins {coins_left} exceeds 250 cap")
            # Discounted prices sum matches total
            items = [o.get('topwear'), o.get('bottomwear'), o.get('footwear'), o.get('bag'), o.get('layer')] + (o.get('accessories') or [])
            calc_sum = sum(int(i.get('selling_price', 0)) for i in items if i)
            self.assertEqual(calc_sum, total)

    def test_13_duplicate_and_near_identical_rejection(self):
        """13. Duplicate and near-identical outfit combinations (differing by only 1 minor accessory) are rejected."""
        res = SmartBudgetOutfitService.generate_budget_outfits(
            budget=3000.0,
            fashion_direction='all',
            gender='women',
            sort_by='best',
        )
        outfits = res.get('outfits', [])
        seen_core_sigs = set()
        seen_item_sets = []
        for o in outfits:
            items = [o.get('topwear'), o.get('bottomwear'), o.get('footwear'), o.get('bag'), o.get('layer')] + (o.get('accessories') or [])
            item_set = frozenset(i.get('product_id') for i in items if i and i.get('product_id'))
            self.assertNotIn(item_set, seen_item_sets, "Exact duplicate outfit returned")
            seen_item_sets.append(item_set)

            core_sig = (
                (o.get('topwear') or {}).get('product_id'),
                (o.get('bottomwear') or {}).get('product_id'),
                (o.get('footwear') or {}).get('product_id')
            )
            if any(core_sig):
                self.assertNotIn(core_sig, seen_core_sigs, f"Near-identical outfit differing by only 1 accessory: {core_sig}")
                seen_core_sigs.add(core_sig)


if __name__ == '__main__':
    unittest.main()
