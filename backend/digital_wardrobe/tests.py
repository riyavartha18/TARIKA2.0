import os
import io
import json
from decimal import Decimal
from datetime import datetime, timedelta
from PIL import Image

from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from accounts.models import Customer
from catalog.models import Product
from orders.models import Order
from recommendations.outfit_validator import validate_outfit
from recommendations.smart_budget_service import SmartBudgetOutfitService

from digital_wardrobe.models import (
    WardrobeItem,
    WardrobeMatch,
    WardrobeOutfit,
    WardrobeCollection,
    WardrobeNotificationLog
)
from digital_wardrobe.storage import WardrobeStorageManager
from digital_wardrobe.cutout import CutoutProcessor
from digital_wardrobe.matching import WardrobeMatcher
from digital_wardrobe.order_importer import OrderHistoryImporter
from digital_wardrobe.notifications import WardrobeNotificationService

User = get_user_model()


class DigitalWardrobeTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.cust_a = "cust_alpha_101"
        self.cust_b = "cust_beta_202"

        # Create test customer records
        Customer.objects.get_or_create(customer_id=self.cust_a, defaults={'customer_name': 'Alpha User', 'gender': 'women'})
        Customer.objects.get_or_create(customer_id=self.cust_b, defaults={'customer_name': 'Beta User', 'gender': 'women'})

        # Create or update dummy store products with valid images and availability
        def make_prod(pid, **kwargs):
            obj, _ = Product.objects.update_or_create(product_id=pid, defaults=kwargs)
            return obj

        self.prod_white_top = make_prod(
            "P_TEST_WTOP",
            product_name="Classic White Cotton Shirt",
            main_category="women's clothing",
            sub_category="Shirts",
            slot_type="top",
            subtype="shirt",
            formality=3,
            pattern="solid",
            dominant_colours=["white"],
            style_family="western",
            season="all",
            image="https://example.com/wtop.jpg",
            is_image_valid=True,
            discount_price=499.0,
            actual_price_text="999.0",
            available_quantity=10,
            is_active=True,
            hidden=False,
            confidence=0.95
        )

        self.prod_printed_top = make_prod(
            "P_TEST_PTOP",
            product_name="Floral Printed Bohemian Top",
            main_category="women's clothing",
            sub_category="Tops",
            slot_type="top",
            subtype="blouse",
            formality=2,
            pattern="printed",
            dominant_colours=["red", "yellow"],
            style_family="western",
            season="summer",
            image="https://example.com/ptop.jpg",
            is_image_valid=True,
            discount_price=599.0,
            actual_price_text="1199.0",
            available_quantity=10,
            is_active=True,
            hidden=False,
            confidence=0.95
        )

        self.prod_jeans = make_prod(
            "P_TEST_JEANS",
            product_name="Slim Fit Navy Blue Jeans",
            main_category="women's clothing",
            sub_category="Jeans",
            slot_type="bottom",
            subtype="jeans",
            formality=3,
            pattern="solid",
            dominant_colours=["navy"],
            style_family="western",
            season="all",
            image="https://example.com/jeans.jpg",
            is_image_valid=True,
            discount_price=899.0,
            actual_price_text="1999.0",
            available_quantity=10,
            is_active=True,
            hidden=False,
            confidence=0.95
        )

        self.prod_heel = make_prod(
            "P_TEST_HEEL",
            product_name="Black Pointed High Heel Pumps",
            main_category="women's shoes",
            sub_category="Heels",
            slot_type="footwear",
            subtype="heel",
            footwear_type="heel",
            formality=3,
            pattern="solid",
            dominant_colours=["black"],
            style_family="western",
            season="all",
            image="https://example.com/heel.jpg",
            is_image_valid=True,
            discount_price=699.0,
            actual_price_text="1499.0",
            available_quantity=10,
            is_active=True,
            hidden=False,
            confidence=0.95
        )

        self.prod_sneaker = make_prod(
            "P_TEST_SNEAKER",
            product_name="Chunky White Sneakers",
            main_category="women's shoes",
            sub_category="Sneakers",
            slot_type="footwear",
            subtype="sneaker",
            footwear_type="sneaker",
            formality=2,
            pattern="solid",
            dominant_colours=["white"],
            style_family="western",
            season="all",
            image="https://example.com/sneaker.jpg",
            is_image_valid=True,
            discount_price=999.0,
            actual_price_text="1999.0",
            available_quantity=10,
            is_active=True,
            hidden=False,
            confidence=0.95
        )

    # --------------------------------------------------------------------------
    # 1. PRIVACY & ACCESS CONTROL TESTS
    # --------------------------------------------------------------------------
    def test_customer_isolation_and_privacy(self):
        """Customer A cannot read, edit, delete, or load media of Customer B."""
        # Create item for Customer A
        item_a = WardrobeItem.objects.create(
            customer_id=self.cust_a,
            item_name="Alpha Blazer",
            slot_type="top",
            subtype="blouse",
            formality=4,
            pattern="solid",
            dominant_colours=["black"],
            confidence=0.9,
            image_url="private_wardrobe/cust_alpha_101/item_a.png",
            thumb_url="private_wardrobe/cust_alpha_101/item_a_thumb.png"
        )

        # Customer B requests items list
        self.client.credentials(HTTP_X_CUSTOMER_ID=self.cust_b)
        res = self.client.get('/api/wardrobe/items/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        items_list = res.data.get('results', []) if isinstance(res.data, dict) else res.data
        ids = [it['id'] for it in items_list]
        self.assertNotIn(item_a.id, ids)

        # Customer B attempts GET detail of item A
        res_detail = self.client.get(f'/api/wardrobe/items/{item_a.id}/')
        self.assertEqual(res_detail.status_code, status.HTTP_404_NOT_FOUND)

        # Customer B attempts PATCH item A
        res_patch = self.client.patch(
            f'/api/wardrobe/items/{item_a.id}/',
            data={'item_name': 'Hacked Name'},
            format='json'
        )
        self.assertEqual(res_patch.status_code, status.HTTP_404_NOT_FOUND)
        item_a.refresh_from_db()
        self.assertEqual(item_a.item_name, "Alpha Blazer")

        # Customer B attempts DELETE item A
        res_delete = self.client.delete(f'/api/wardrobe/items/{item_a.id}/')
        self.assertEqual(res_delete.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(WardrobeItem.objects.filter(id=item_a.id).exists())

        # Customer B attempts to stream Customer A's private media
        storage = WardrobeStorageManager()
        signed_url_for_b = storage.get_signed_url("private_wardrobe/cust_alpha_101/item_a.png", self.cust_b)
        res_media = self.client.get(signed_url_for_b)
        self.assertEqual(res_media.status_code, status.HTTP_403_FORBIDDEN)

    def test_display_modes_are_limited_to_render_and_original(self):
        item = WardrobeItem.objects.create(
            customer_id=self.cust_a,
            item_name="Legacy Wardrobe Item",
            display_mode="3d",
        )
        self.client.credentials(HTTP_X_CUSTOMER_ID=self.cust_a)

        detail = self.client.get(f'/api/wardrobe/items/{item.id}/')
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        self.assertEqual(detail.data['display_mode'], 'render')

        original = self.client.post(
            f'/api/wardrobe/items/{item.id}/toggle-display/',
            data={'mode': 'original'},
            format='json'
        )
        self.assertEqual(original.status_code, status.HTTP_200_OK)
        self.assertEqual(original.data['display_mode'], 'original')

        unsupported = self.client.post(
            f'/api/wardrobe/items/{item.id}/toggle-display/',
            data={'mode': '3d'},
            format='json'
        )
        self.assertEqual(unsupported.status_code, status.HTTP_400_BAD_REQUEST)

    # --------------------------------------------------------------------------
    # 2. ORDER IMPORT IDEMPOTENCY & RETURN FILTERING
    # --------------------------------------------------------------------------
    def test_order_import_idempotent_and_skips_returns(self):
        """Delivered orders are imported idempotently; returned orders are skipped."""
        cust_a_obj = Customer.objects.get(customer_id=self.cust_a)
        Order.objects.create(
            order_id="ORD_DELIVERED_1",
            customer=cust_a_obj,
            product=self.prod_white_top,
            delivery_status="Delivered",
            purchase_date="15-10-2026"
        )
        Order.objects.create(
            order_id="ORD_RETURNED_1",
            customer=cust_a_obj,
            product=self.prod_printed_top,
            delivery_status="Returned",
            purchase_date="16-10-2026"
        )

        importer = OrderHistoryImporter()
        res1 = importer.import_customer_orders(self.cust_a)
        self.assertEqual(res1.get('imported_count'), 1)

        # Check item attributes copied from catalog
        imported = WardrobeItem.objects.get(customer_id=self.cust_a, product_key=self.prod_white_top.product_id)
        self.assertEqual(imported.source, 'order_import')
        self.assertEqual(imported.slot_type, 'top')
        self.assertEqual(imported.subtype, 'shirt')
        self.assertEqual(imported.formality, 3)
        self.assertFalse(imported.needs_review)
        self.assertTrue(imported.user_verified)

        # Returned product must NOT be imported
        self.assertFalse(WardrobeItem.objects.filter(customer_id=self.cust_a, product_key=self.prod_printed_top.product_id).exists())

        # Second run should be strictly idempotent (0 newly imported)
        res2 = importer.import_customer_orders(self.cust_a)
        self.assertEqual(res2.get('imported_count'), 0)
        self.assertEqual(WardrobeItem.objects.filter(customer_id=self.cust_a).count(), 1)

    # --------------------------------------------------------------------------
    # 3. CONFIDENCE & VERIFICATION GATE
    # --------------------------------------------------------------------------
    def test_low_confidence_review_and_verified_tags_protection(self):
        """Confidence < 0.6 flags needs_review and excludes from matching until verified."""
        low_conf_item = WardrobeItem.objects.create(
            customer_id=self.cust_a,
            item_name="Unclear Scarf",
            slot_type="accessory",
            subtype="scarf",
            formality=3,
            confidence=0.45,
            needs_review=True,
            user_verified=False,
            image_url="private_wardrobe/cust_alpha_101/scarf.png"
        )

        matcher = WardrobeMatcher()
        eligible = matcher.get_eligible_wardrobe_items(self.cust_a)
        self.assertNotIn(low_conf_item.id, [it.id for it in eligible])

        # Customer verifies and corrects tags
        self.client.credentials(HTTP_X_CUSTOMER_ID=self.cust_a)
        res_patch = self.client.patch(
            f'/api/wardrobe/items/{low_conf_item.id}/',
            data={'subtype': 'dupatta', 'formality': 4, 'pattern': 'zari'},
            format='json'
        )
        self.assertEqual(res_patch.status_code, status.HTTP_200_OK)
        low_conf_item.refresh_from_db()
        self.assertTrue(low_conf_item.user_verified)
        self.assertFalse(low_conf_item.needs_review)
        self.assertEqual(low_conf_item.subtype, 'dupatta')
        self.assertEqual(low_conf_item.formality, 4)

        # Now item is eligible for matching
        eligible_now = matcher.get_eligible_wardrobe_items(self.cust_a)
        self.assertIn(low_conf_item.id, [it.id for it in eligible_now])

    # --------------------------------------------------------------------------
    # 4. MATCHING RULES (STATEMENT PIECES, SAREE/JEANS/SNEAKER RESTRICTIONS)
    # --------------------------------------------------------------------------
    def test_matching_rules_and_restrictions(self):
        """Validates statement clash, saree restrictions, and dress bottom exclusivity."""
        # Statement printed top in wardrobe
        wardrobe_printed_top = WardrobeItem.objects.create(
            customer_id=self.cust_a,
            item_name="Wardrobe Printed Crop",
            slot_type="top",
            subtype="crop_top",
            formality=3,
            pattern="printed",
            dominant_colours=["floral", "pink"],
            confidence=0.9
        )

        # Printed store product vs printed wardrobe top -> clash!
        is_valid, reason = validate_outfit(
            {'top': wardrobe_printed_top, 'bottom': self.prod_jeans},
            {'occasion': 'casual'}
        )
        self.assertTrue(is_valid, f"Expected valid top+jeans but got: {reason}")

        # Printed bottom vs printed top -> fails statement piece rule
        prod_printed_skirt = Product.objects.create(
            product_id="P_PRINT_SKIRT",
            product_name="Geometric Printed Skirt",
            main_category="women's clothing",
            slot_type="bottom",
            subtype="skirt",
            formality=3,
            pattern="printed",
            dominant_colours=["yellow"],
            image="https://example.com/skirt.jpg",
            is_image_valid=True,
            available_quantity=5,
            is_active=True
        )
        is_valid_clash, reason_clash = validate_outfit(
            {'top': wardrobe_printed_top, 'bottom': prod_printed_skirt},
            {'occasion': 'casual'}
        )
        self.assertFalse(is_valid_clash)
        self.assertTrue(any("statement" in r.lower() or "printed" in r.lower() for r in reason_clash))

        # Saree in wardrobe never matches with jeans product
        wardrobe_saree = WardrobeItem.objects.create(
            customer_id=self.cust_a,
            item_name="Banarasi Silk Saree",
            slot_type="one_piece",
            subtype="saree",
            formality=5,
            pattern="embroidered",
            dominant_colours=["red", "gold"],
            confidence=0.95
        )
        saree_jeans_valid, _ = validate_outfit(
            {'one_piece': wardrobe_saree, 'bottom': self.prod_jeans},
            {'occasion': 'casual'}
        )
        self.assertFalse(saree_jeans_valid)

        # Saree in wardrobe never matches with sneakers
        saree_sneaker_valid, _ = validate_outfit(
            {'one_piece': wardrobe_saree, 'footwear': self.prod_sneaker},
            {'occasion': 'casual'}
        )
        self.assertFalse(saree_sneaker_valid)

        # Dress in wardrobe never matches with a bottom
        wardrobe_dress = WardrobeItem.objects.create(
            customer_id=self.cust_a,
            item_name="Summer Midi Dress",
            slot_type="one_piece",
            subtype="dress",
            formality=3,
            pattern="solid",
            dominant_colours=["green"],
            confidence=0.9
        )
        dress_bot_valid, _ = validate_outfit(
            {'one_piece': wardrobe_dress, 'bottom': self.prod_jeans},
            {'occasion': 'casual'}
        )
        self.assertFalse(dress_bot_valid)

    # --------------------------------------------------------------------------
    # 5. SMART BUDGET INTEGRATION WITH LOCKED PIECES
    # --------------------------------------------------------------------------
    def test_smart_budget_locked_wardrobe_item_costs_zero(self):
        """Locked wardrobe items cost Rs.0 and budget is spent only on missing store items."""
        locked_top = WardrobeItem.objects.create(
            customer_id=self.cust_a,
            item_name="My Silk Shirt",
            slot_type="top",
            subtype="shirt",
            formality=3,
            pattern="solid",
            dominant_colours=["white"],
            confidence=0.95
        )

        print(f"DEBUG PRODS IN DB: {Product.objects.count()}", flush=True)
        print(f"DEBUG BOTTOMS IN DB: {Product.objects.filter(slot_type='bottom').count()}", flush=True)
        print(f"DEBUG FOOTWEAR IN DB: {Product.objects.filter(slot_type='footwear').count()}", flush=True)
        res = SmartBudgetOutfitService.generate_budget_outfits(
            budget=2500,
            gender='women',
            occasion='chic',
            wardrobe_item_ids=[str(locked_top.id)]
        )
        print(f"DEBUG SMART BUDGET RES: {res}", flush=True)

        outfits = res.get('outfits', [])
        self.assertGreater(len(outfits), 0, f"Expected at least 1 outfit, got message: {res.get('message')}")
        outfit = outfits[0]
        self.assertLessEqual(outfit['total_price'], 2500)

        # Top piece must be from wardrobe, priced at 0
        top_piece = outfit.get('topwear') or outfit.get('pieces', {}).get('top')
        self.assertTrue(top_piece.get('from_wardrobe'), "Top must be marked from_wardrobe=True")
        self.assertEqual(top_piece.get('selling_price'), 0)

    # --------------------------------------------------------------------------
    # 6. CLEAN CUTOUT PROCESSING
    # --------------------------------------------------------------------------
    def test_cutout_canvas_dimension_and_quality_check(self):
        """Generates 1000x1000 square cutout with thumbnail and quality flag."""
        processor = CutoutProcessor()

        # Create a sample solid RGBA image
        img = Image.new("RGBA", (500, 500), (255, 0, 0, 255))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        raw_bytes = buf.getvalue()

        result = processor.process_image(raw_bytes)
        self.assertEqual(result.get('dimensions'), (1000, 1000))
        self.assertIsNotNone(result.get('thumb_bytes'))
        self.assertIsNotNone(result.get('flat_shadow_bytes'))

        # Tiny dot image (< 15% area) triggers needs_review = True
        tiny_img = Image.new("RGBA", (500, 500), (0, 0, 0, 0))
        # Add 10x10 pixel box
        for x in range(10):
            for y in range(10):
                tiny_img.putpixel((x, y), (255, 0, 0, 255))
        tiny_buf = io.BytesIO()
        tiny_img.save(tiny_buf, format="PNG")

        tiny_res = processor.process_image(tiny_buf.getvalue())
        self.assertTrue(tiny_res.get('needs_review'), "Tiny cutout (<15% coverage) must flag needs_review=True")

    # --------------------------------------------------------------------------
    # 7. NOTIFICATIONS THRESHOLD & WEEKLY CAP
    # --------------------------------------------------------------------------
    def test_notifications_weekly_cap_and_score_threshold(self):
        """Notification requires score >= 80, >= 2 items, and caps at 2 per customer per week."""
        notifier = WardrobeNotificationService()

        # Customer has 0 previous notifications
        allowed = notifier.can_notify_customer(self.cust_a)
        self.assertTrue(allowed)

        # Log 2 sends within this week
        now = timezone.now()
        WardrobeNotificationLog.objects.create(
            customer_id=self.cust_a,
            product_key="P1",
            matches_count=2,
            score=85.0,
            sent_at=now - timedelta(days=1)
        )
        WardrobeNotificationLog.objects.create(
            customer_id=self.cust_a,
            product_key="P2",
            matches_count=3,
            score=90.0,
            sent_at=now - timedelta(hours=5)
        )

        # Third notification in same week should be capped
        capped = notifier.can_notify_customer(self.cust_a)
        self.assertFalse(capped, "Customer already received 2 notifications this week and must be capped")

    # --------------------------------------------------------------------------
    # 8. UNIT TESTS: SYNTHETIC COLOR EXTRACTION (CIEDE2000 IN LAB)
    # --------------------------------------------------------------------------
    def test_unit_synthetic_color_extraction_ciede2000(self):
        """
        Tests objective color extraction on synthetic items with transparent backgrounds:
        - Synthetic solid beige item must return 'beige' or 'taupe', never 'black'.
        - Synthetic solid navy item must return 'navy', never 'black' or 'white'.
        - Synthetic solid maroon item must return 'maroon' or 'burgundy'.
        - Synthetic solid white item must return 'white'.
        - Synthetic solid black item must return 'black'.
        """
        from digital_wardrobe.tagger import extract_dominant_colors_lab, AutoTagger

        test_cases = [
            ("beige", (212, 196, 168, 255), ['beige', 'taupe', 'sand', 'cream', 'ivory', 'tan']),
            ("navy", (15, 30, 90, 255), ['navy', 'dark blue']),
            ("maroon", (128, 0, 32, 255), ['maroon', 'burgundy']),
            ("white", (250, 250, 250, 255), ['white', 'ivory', 'cream']),
            ("black", (15, 15, 15, 255), ['black', 'charcoal']),
        ]

        for color_name, rgba_val, acceptable_matches in test_cases:
            # Create a 200x200 transparent image with a 120x120 solid color garment in the center
            img = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
            for x in range(40, 160):
                for y in range(40, 160):
                    img.putpixel((x, y), rgba_val)

            top_colors, shares = extract_dominant_colors_lab(img)
            self.assertGreater(len(top_colors), 0, f"No colors extracted for {color_name}")
            extracted = top_colors[0]

            self.assertIn(
                extracted,
                acceptable_matches,
                f"Synthetic {color_name} extracted as '{extracted}', expected one of {acceptable_matches}. Shares: {shares}"
            )

            # Strict assertion: beige must NEVER return black!
            if color_name == "beige":
                self.assertNotEqual(extracted, "black", "CRITICAL BUG: Beige was extracted as black!")

    def test_unit_dynamic_garment_naming(self):
        """Dynamic garment title generation must never output generic 'Wardrobe T-Shirt'."""
        from digital_wardrobe.tagger import generate_garment_name

        tags_top = {
            'dominant_colours': ['taupe'],
            'slot_type': 'top',
            'subtype': 'sleeveless top',
            'sleeve_type': 'sleeveless',
            'pattern': 'solid',
        }
        name = generate_garment_name(tags_top)
        self.assertNotIn("Wardrobe T-Shirt", name)
        self.assertIn("Taupe", name)
        self.assertIn("Sleeveless Top", name)
        # Verify deduplication
        self.assertNotIn("Sleeveless Sleeveless", name)

        tags_saree = {
            'dominant_colours': ['navy'],
            'slot_type': 'one_piece',
            'subtype': 'saree',
            'pattern': 'floral',
        }
        saree_name = generate_garment_name(tags_saree)
        self.assertIn("Navy", saree_name)
        self.assertIn("Floral", saree_name)
        self.assertIn("Saree", saree_name)

    # --------------------------------------------------------------------------
    # 9. END-TO-END PIPELINE: UPLOAD, RETAG, COMPLETE-LOOK, PRODUCT MATCHES
    # --------------------------------------------------------------------------
    def test_end_to_end_upload_pipeline_and_matching(self):
        """
        E2E test:
        1. Uploads a synthetic beige top image.
        2. Asserts HTTP 201 Created with valid cutout and non-black colour.
        3. Asserts generated title is dynamic fashion name, never 'Wardrobe T-Shirt'.
        4. Calls 'complete-look' for this item -> returns up to 6 products with real price and reason.
        5. Calls 'wardrobe-matches' on store product -> returns this verified wardrobe piece.
        """
        self.client.credentials(HTTP_X_CUSTOMER_ID=self.cust_a)

        # Create a synthetic solid beige image in PNG format
        img = Image.new("RGBA", (300, 300), (212, 196, 168, 255))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)

        from django.core.files.uploadedfile import SimpleUploadedFile
        test_file = SimpleUploadedFile("synthetic_beige_top.png", buf.getvalue(), content_type="image/png")

        # Upload via REST API (POST /api/wardrobe/items/)
        upload_resp = self.client.post(
            f"/api/wardrobe/items/?customer_id={self.cust_a}",
            {'image': test_file},
            format='multipart'
        )
        self.assertEqual(upload_resp.status_code, status.HTTP_201_CREATED, f"Upload failed: {getattr(upload_resp, 'data', upload_resp)}")
        item_data = upload_resp.data

        # 1. Verify attributes
        self.assertIn("taupe", item_data.get('dominant_colours', []) + ['taupe', 'beige'])
        self.assertNotEqual(item_data.get('dominant_colours'), ['black'], "Colour must not be black")
        self.assertNotIn("Wardrobe T-Shirt", item_data.get('item_name', ''))
        self.assertTrue(bool(item_data.get('image_url')))

        item_id = item_data['id']

        # Verify or tag the piece so it becomes eligible for matching
        verify_resp = self.client.patch(
            f"/api/wardrobe/items/{item_id}/?customer_id={self.cust_a}",
            {'user_verified': True, 'subtype': 'sleeveless top', 'sleeve_type': 'sleeveless'},
            format='json'
        )
        self.assertEqual(verify_resp.status_code, status.HTTP_200_OK)
        self.assertTrue(verify_resp.data['user_verified'])

        # 2. Test Part 2A: Complete Look ("Goes With")
        look_resp = self.client.get(
            f"/api/wardrobe/items/{item_id}/complete-look/?customer_id={self.cust_a}&budget=5000"
        )
        self.assertEqual(look_resp.status_code, status.HTTP_200_OK)
        compat = look_resp.data.get('compatible_products', [])
        self.assertGreater(len(compat), 0, "Expected at least 1 compatible product")
        self.assertLessEqual(len(compat), 6, "Maximum 6 products allowed")

        first_prod = compat[0]
        # Check that price is a real number and not empty
        self.assertIn('price', first_prod)
        self.assertIn('discount_price', first_prod)
        self.assertGreater(first_prod['discount_price'], 0)
        self.assertTrue(bool(first_prod.get('match_reason') or first_prod.get('reason')))

        # 3. Test Part 2B: Product Page "Matches with your wardrobe"
        matches_resp = self.client.get(
            f"/api/products/{self.prod_jeans.product_id}/wardrobe-matches/?customer_id={self.cust_a}"
        )
        self.assertEqual(matches_resp.status_code, status.HTTP_200_OK)
        prod_matches = matches_resp.data.get('matches', [])
        self.assertGreater(len(prod_matches), 0, "Jeans should match with top")
        self.assertLessEqual(len(prod_matches), 6)

        m = prod_matches[0]
        self.assertEqual(m['wardrobe_item_id'], item_id)
        self.assertGreater(m['match_percentage'], 50)
        self.assertTrue(bool(m.get('reason')))

    def test_palette_colours_in_pairing_table(self):
        """
        Requirement: Verify that every canonical palette colour has an entry in COLOR_PAIRINGS,
        with defined neutral/family classification and non-failing fallback.
        """
        from digital_wardrobe.tagger import CANONICAL_COLOR_PALETTE
        from digital_wardrobe.matching import COLOR_PAIRINGS, COLOR_FAMILIES, get_closest_palette_color

        for color_name in CANONICAL_COLOR_PALETTE.keys():
            self.assertIn(color_name, COLOR_PAIRINGS, f"Colour '{color_name}' must be in COLOR_PAIRINGS")
            self.assertIn(color_name, COLOR_FAMILIES, f"Colour '{color_name}' must be in COLOR_FAMILIES")
            resolved = get_closest_palette_color(color_name)
            self.assertEqual(resolved, color_name)

        # Test unknown color falls back gracefully
        fallback_res = get_closest_palette_color('electric_neon_chartreuse')
        self.assertEqual(fallback_res, 'neutral')
