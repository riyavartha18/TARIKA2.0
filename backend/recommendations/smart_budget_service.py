import logging
import json
import math
from datetime import datetime
from decimal import Decimal
from collections import Counter, defaultdict
from django.db.models import Q

from catalog.models import Product
from orders.models import Order
from cart.models import WishlistItem, CartItem
from .models import ProductRecommendation
from .outfit_validator import (
    validate_outfit,
    are_colors_clashing,
    OCCASION_RULES,
    ALLOWED_STYLE_PAIRS,
    NEUTRAL_COLORS,
    COLOR_CLASH_PAIRS,
)

logger = logging.getLogger(__name__)


def get_effective_product_price(p):
    """Calculates effective selling price."""
    if not p:
        return 0.0
    if getattr(p, 'from_wardrobe', False) or getattr(p, '__class__', None).__name__ == 'WardrobeItem':
        return 0.0
    try:
        disc = getattr(p, 'discount_price', None)
        if disc is not None and float(disc) > 0:
            return float(disc)
    except (ValueError, TypeError):
        pass

    try:
        base = getattr(p, 'base_price', None)
        if base is not None and float(base) > 0:
            return float(base)
    except (ValueError, TypeError):
        pass

    return 0.0


def serialize_catalog_product(p):
    """Unified serialization for frontend ProductCard & Outfit components."""
    if not p:
        return None
    if getattr(p, 'from_wardrobe', False):
        img = getattr(p, 'flat_image_url', getattr(p, 'thumb_url', getattr(p, 'image_url', ''))) or ''
        return {
            'product_id': f"w_{p.id}",
            'id': f"w_{p.id}",
            'product_name': getattr(p, 'item_name', 'Wardrobe Item'),
            'name': getattr(p, 'item_name', 'Wardrobe Item'),
            'selling_price': 0,
            'discount_price': 0.0,
            'base_price': 0,
            'actual_price': 0.0,
            'image': img,
            'primary_image': img,
            'images': [img] if img else [],
            'main_category': 'digital_wardrobe',
            'sub_category': getattr(p, 'subtype', 'other'),
            'is_active': True,
            'is_image_valid': True,
            'total_stock': 1,
            'from_wardrobe': True,
            'slot_type': getattr(p, 'slot_type', None),
            'subtype': getattr(p, 'subtype', 'other'),
            'formality': getattr(p, 'formality', 3),
            'pattern': getattr(p, 'pattern', 'solid'),
            'dominant_colours': getattr(p, 'dominant_colours', []),
            'style_family': getattr(p, 'style_family', 'western'),
            'season': getattr(p, 'season', 'all'),
            'footwear_type': getattr(p, 'footwear_type', None),
            'accessory_type': getattr(p, 'accessory_type', None),
            'includes_blouse': bool(getattr(p, 'includes_blouse', False)),
            'includes_dupatta': bool(getattr(p, 'includes_dupatta', False)),
            'metal_tone': getattr(p, 'metal_tone', None),
            'confidence': float(getattr(p, 'confidence', 1.0) or 1.0),
            'hidden': False,
            'product_url': '',
        }
    from catalog.serializers import sanitize_product_image_url
    eff_price = get_effective_product_price(p) or 0.0
    clean_image = sanitize_product_image_url(getattr(p, 'image', None))

    dom_cols = getattr(p, 'dominant_colours', [])
    if isinstance(dom_cols, str):
        try:
            dom_cols = json.loads(dom_cols)
        except Exception:
            dom_cols = [c.strip() for c in dom_cols.replace('[', '').replace(']', '').replace('"', '').split(',') if c.strip()]
    elif not isinstance(dom_cols, list):
        dom_cols = []

    return {
        'product_id': p.product_id,
        'id': p.product_id,
        'product_name': p.product_name,
        'name': p.product_name,
        'selling_price': int(round(eff_price)),
        'discount_price': float(p.discount_price) if (p.discount_price and p.discount_price > 0) else eff_price,
        'base_price': int(round(float(p.base_price))) if p.base_price else int(round(eff_price)),
        'actual_price': float(p.base_price) if p.base_price else eff_price,
        'image': clean_image or '',
        'primary_image': clean_image or '',
        'images': [clean_image] if clean_image else [],
        'main_category': p.main_category,
        'sub_category': p.sub_category,
        'is_active': (p.available_quantity or 0) > 0,
        'is_image_valid': getattr(p, 'is_image_valid', True),
        'total_stock': int(p.available_quantity or 0),
        'slot_type': getattr(p, 'slot_type', None),
        'subtype': getattr(p, 'subtype', 'other'),
        'formality': getattr(p, 'formality', 3),
        'pattern': getattr(p, 'pattern', 'solid'),
        'dominant_colours': dom_cols,
        'style_family': getattr(p, 'style_family', 'western'),
        'season': getattr(p, 'season', 'all'),
        'footwear_type': getattr(p, 'footwear_type', None),
        'accessory_type': getattr(p, 'accessory_type', None),
        'includes_blouse': bool(getattr(p, 'includes_blouse', False)),
        'includes_dupatta': bool(getattr(p, 'includes_dupatta', False)),
        'metal_tone': (
            getattr(p, 'metal_tone', None)
            if getattr(p, 'metal_tone', None) and getattr(p, 'metal_tone', None) != 'unknown'
            else ('gold' if any(w in (p.product_name or '').lower() for w in ['gold', 'golden', 'zari', 'kundan'])
                  else ('silver' if any(w in (p.product_name or '').lower() for w in ['silver', 'oxidised', 'oxidized', 'rhodium'])
                        else 'unknown'))
        ),
        'confidence': float(getattr(p, 'confidence', 1.0) or 1.0),
        'hidden': bool(getattr(p, 'hidden', False)),
        'product_url': getattr(p, 'product_url', None) or getattr(p, 'url', None) or '',
        'url': getattr(p, 'product_url', None) or getattr(p, 'url', None) or '',
    }


class SmartBudgetOutfitService:
    """
    Intelligent Budget Outfit Engine:
      1. Dynamic budget-fitting search targeting leftover <= Rs.250 (or <= 5% of budget).
      2. 4-step leftover reducer:
         a) Upgrade to pricier compatible piece in the same slot.
         b) Add layers (jacket, blazer, shrug, cardigan).
         c) Add accessories (bag, jewellery, watch, belt, sunglasses, scarf, hair acc).
         d) Use pricier bases (dresses, jumpsuits, co-ords, sarees, lehengas).
      3. Expensive products allowed (>= 60% of budget up to 100% of budget).
      4. Ethnic: All eligible sarees in catalogue used; sarees appear in Ethnic and Surprise Me.
      5. Hard compatibility gate (validate_outfit) NEVER relaxed.
      6. Personalised first outfits in Surprise Me for logged-in customers.
      7. Hard exclusion of already-purchased products.
      8. Wishlist and cart items used as anchor pieces inside budget.
    """

    COLOR_SYNONYMS = {
        'black': ['black', 'noir', 'charcoal', 'jet black'],
        'white': ['white', 'ivory', 'off-white', 'snow'],
        'beige': ['beige', 'cream', 'khaki', 'tan', 'nude', 'camel'],
        'pink': ['pink', 'rose', 'blush', 'magenta', 'fuchsia', 'salmon'],
        'maroon': ['maroon', 'burgundy', 'wine', 'crimson', 'red'],
        'navy': ['navy', 'blue', 'indigo', 'azure', 'sky blue', 'cobalt'],
        'green': ['green', 'olive', 'emerald', 'mint', 'sage', 'teal'],
        'yellow': ['yellow', 'mustard', 'ochre', 'gold'],
        'purple': ['purple', 'violet', 'lavender', 'plum', 'lilac'],
        'brown': ['brown', 'chocolate', 'coffee', 'mocha'],
    }

    OCCASION_MAP = {
        'casual': ['casual', 'cotton', 'regular', 'tee', 't-shirt', 'jeans', 'relaxed', 'printed', 'sneakers', 'flat', 'denim'],
        'formal': ['formal', 'office', 'work', 'blazer', 'trouser', 'trousers', 'shirt', 'classic', 'crepe', 'solid', 'suit'],
        'party': ['party', 'cocktail', 'sequin', 'velvet', 'heels', 'metallic', 'shimmer', 'evening', 'satin', 'flared', 'glam'],
        'festive': ['festive', 'embroidery', 'kurta', 'kurti', 'saree', 'silk', 'zari', 'traditional', 'anarkali', 'ethnic', 'chanderi'],
        'college': ['denim', 'graphic', 'crop', 'sneakers', 'hoodie', 'joggers', 't-shirt', 'street', 'college'],
        'traditional': ['ethnic', 'printed', 'bandhani', 'cotton', 'silk', 'kurta', 'kurti', 'saree', 'embroidered', 'zari'],
        'chic': ['chic', 'stylish', 'trendy', 'crop', 'high waist', 'flared', 'blazer', 'crepe'],
        'elegant': ['elegant', 'dress', 'gown', 'satin', 'lace', 'heels', 'georgette', 'maxi'],
        'streetwear': ['oversized', 'graphic', 'hoodie', 'cargo', 'jogger', 'denim', 'sneakers', 'street'],
    }

    EXPANSION_PRODUCT_KEYS = [f"P10000{i}" for i in range(1, 10)] + [f"P1000{i}" for i in range(10, 41)]

    INNERWEAR_KEYWORDS = [
        'bra', 'panty', 'panties', 'brief', 'briefs', 'shapewear', 'petticoat',
        'boyshorts', 'camisole', 'innerwear', 'nightwear', 'nightdress', 'nighty',
        'pyjama set', 'pajama set', 'boxer', 'underwear'
    ]

    CRAFT_JUNK_KEYWORDS = [
        'stopper', 'earring back', 'earring plug', 'rakhi', 'findings', 'safety pin',
        'sewing', 'pech', 'push button', 'screw back', 'keychain', 'shoelace',
        'hair band', 'hair bands', 'hair tie', 'hair ties', 'scrunchie', 'scrunchies',
        'ponytail holder', 'elastic cloth', 'rubber band', 'raw material',
        'ring sizer', 'ring sizers', 'ring mandrel', 'ring size adjuster', 'ring adjuster',
        'invisible ring sizer', 'ring tool', 'fevicol', 'all fix', 'fevikwik', 'glue',
        'sandpaper', 'pliers', 'wire cutter', 'glue gun'
    ]

    FOOTWEAR_JUNK_KEYWORDS = [
        'heel grip', 'heel grips', 'heel pad', 'heel pads', 'insole', 'insoles',
        'shoe insert', 'shoe inserts', 'crep protect', 'cleaner', 'whitener',
        'shoe horn', 'toe shield', 'toe shields', 'cushion pad', 'orthotic insole',
        'school shoes', 'school uniform', 'watch strap', 'watch straps', 'watch band',
        'leather strap', 'leather watch', 'crease protector', 'shoe tree', 'shoe trees',
        'cobbler', 'nail', 'nails', 'screw', 'screws', 'shoe repair', 'sole protector',
        'sole protectors', 'fevicol', 'all fix', 'fevikwik', 'glue',
        'arch support', 'orthopedic', 'diabetic', 'heel pain', 'foot cure', 'pain relief'
    ]

    BAG_JUNK_KEYWORDS = [
        'claw clip', 'claw clips', 'hair clip', 'hair clips', 'hair claw', 'clutcher',
        'hair clutches', 'wallet chain', 'pants chain', 'jeans chain', 'pant chain',
        'clutch back', 'earring', 'earrings', 'hoop', 'jewel pouch', 'purse pouch',
        'jewellery zip', 'jewel zip', 'jewellery pouch', 'pouch for necklace',
        'dress with sling bag', 'set with purse', 'with purse',
        'makeup bag', 'makeup pouch', 'cosmetic bag', 'cosmetic pouch', 'toiletry bag',
        'toiletry pouch', 'pencil pouch', 'kit pouch', 'organizer pouch', 'shagun pouch'
    ]

    TIER_METADATA = [
        ('Most Popular', 'Most Popular Look', 'Highest aesthetic harmony score & runway-ready coordination.'),
        ('Best Match', 'Best Match Look', 'Maximum budget efficiency with effortless daily elegance.'),
        ('Atelier Pick', 'Atelier Curated Look', 'Contrasting color palette for versatile wardrobe rotation.'),
        ('Weekend Chic', 'Weekend Chic Look', 'Relaxed, contemporary silhouette ideal for brunches and casual meetups.'),
        ('Signature Luxe', 'Signature Luxe Look', 'Elevated statement aesthetic designed for evening occasions.'),
        ('Modern Minimal', 'Modern Minimal Look', 'Clean tonal balance with timeless wardrobe staples.')
    ]

    @classmethod
    def get_customer_taste_profile(cls, customer_id):
        """
        Extracts customer taste profile from orders, wishlist, and cart.
        Applies time decay exp(-lambda * t) and penalizes returned orders.
        """
        if not customer_id:
            return None

        orders = list(Order.objects.filter(customer_id=customer_id).select_related('product'))
        wishlist = list(WishlistItem.objects.filter(customer_id=customer_id).select_related('product'))
        cart = list(CartItem.objects.filter(customer_id=customer_id).select_related('product'))

        purchased_pids = set()
        for o in orders:
            if o.product_id:
                purchased_pids.add(str(o.product_id).strip())

        color_weights = defaultdict(float)
        style_weights = defaultdict(float)
        subtype_weights = defaultdict(float)
        price_points = []

        now = datetime.now()

        for o in orders:
            p = o.product
            if not p:
                continue
            p_name = (p.product_name or '').lower()
            p_cat = (p.main_category or '').lower()
            if "men" in p_cat and "women" not in p_cat:
                continue
            if any(m in p_name for m in ["men's", "mens ", "for men"]):
                continue

            weight = 1.0
            if o.purchase_date:
                try:
                    dt = datetime.strptime(o.purchase_date.strip(), '%d-%m-%Y')
                    days_ago = max(0, (now - dt).days)
                    weight = math.exp(-0.005 * min(days_ago, 365))
                except Exception:
                    weight = 0.8

            status = (o.delivery_status or '').lower()
            if 'return' in status or 'cancel' in status:
                weight = -0.5 * abs(weight)

            if o.final_price and o.final_price > 0 and weight > 0:
                price_points.append(float(o.final_price))

            cols = cls._detect_item_colors(p)
            for c in cols:
                c = str(c).lower().strip()
                if c:
                    color_weights[c] += weight

            sf = getattr(p, 'style_family', None) or 'western'
            style_weights[sf] += weight

            sub = getattr(p, 'subtype', None) or getattr(p, 'slot_type', None)
            if sub:
                subtype_weights[sub] += weight

        anchor_candidates = []
        seen_anchors = set()
        for item in wishlist + cart:
            p = item.product
            if not p:
                continue
            pid = str(p.product_id).strip()
            if pid in purchased_pids or pid in seen_anchors:
                continue
            p_name = (p.product_name or '').lower()
            p_cat = (p.main_category or '').lower()
            if ("men" in p_cat and "women" not in p_cat) or any(m in p_name for m in ["men's", "mens ", "for men"]):
                continue
            seen_anchors.add(pid)
            source = 'wishlist' if isinstance(item, WishlistItem) else 'cart'
            anchor_candidates.append({'product': p, 'source': source})

        top_colors = [c for c, w in sorted(color_weights.items(), key=lambda x: x[1], reverse=True) if w > 0][:3]
        top_styles = [s for s, w in sorted(style_weights.items(), key=lambda x: x[1], reverse=True) if w > 0][:2]
        top_subtypes = [t for t, w in sorted(subtype_weights.items(), key=lambda x: x[1], reverse=True) if w > 0][:3]
        avg_price = sum(price_points) / len(price_points) if price_points else 1500.0

        return {
            'customer_id': customer_id,
            'purchased_pids': purchased_pids,
            'top_colors': top_colors,
            'top_styles': top_styles,
            'top_subtypes': top_subtypes,
            'avg_price': avg_price,
            'anchors': anchor_candidates,
            'has_profile': bool(top_colors or top_styles or anchor_candidates)
        }

    @classmethod
    def _detect_item_colors(cls, item):
        """Extracts dominant colors from product (dict or model instance)."""
        if not item:
            return []
        if isinstance(item, dict):
            cols = item.get('dominant_colours', [])
        else:
            cols = getattr(item, 'dominant_colours', [])
        if isinstance(cols, list):
            return [str(c).lower().strip() for c in cols if c]
        if isinstance(cols, str):
            try:
                parsed = json.loads(cols)
                if isinstance(parsed, list):
                    return [str(c).lower().strip() for c in parsed if c]
            except Exception:
                pass
            return [c.strip().lower() for c in cols.replace('[', '').replace(']', '').replace('"', '').split(',') if c.strip()]
        return []

    @classmethod
    def _matches_color(cls, item, target_color):
        if not item or not target_color:
            return False
        target = target_color.lower().strip()
        synonyms = cls.COLOR_SYNONYMS.get(target, [target])
        if isinstance(item, dict):
            name = (item.get('product_name') or item.get('name') or '').lower()
        else:
            name = (getattr(item, 'product_name', None) or getattr(item, 'name', '') or '').lower()
        if any(s in name for s in synonyms):
            return True
        item_cols = cls._detect_item_colors(item)
        if any(s in item_cols for s in synonyms) or target in item_cols:
            return True
        return False

    @classmethod
    def _calculate_score_and_breakdown(
        cls,
        pieces,
        budget,
        occasion,
        style,
        preferred_color,
        rules_map=None
    ):
        """
        Builds honest, evidence-based harmony score with heavy budget utilization weight.
        """
        breakdown = {
            'formality_harmony': 0,
            'style_coherence': 0,
            'color_harmony': 0,
            'occasion_fit': 0,
            'budget_efficiency': 0,
            'apriori_lift': 0
        }
        notes = []

        all_items = [p for p in [pieces.get('one_piece'), pieces.get('top'), pieces.get('bottom'), pieces.get('layer'), pieces.get('footwear'), pieces.get('bag')] + pieces.get('accessories', []) if p]

        # 1. Formality Harmony (10 to 20 pts)
        formalities = [getattr(it, 'formality', 3) for it in all_items if getattr(it, 'formality', None) is not None]
        if formalities:
            gap = max(formalities) - min(formalities)
            if gap == 0:
                breakdown['formality_harmony'] = 20
                notes.append("Consistent formality level across all pieces")
            elif gap == 1:
                breakdown['formality_harmony'] = 15
                notes.append("Close formality coordination")
            else:
                breakdown['formality_harmony'] = 8
        else:
            breakdown['formality_harmony'] = 12

        # 2. Style Family Coherence (10 to 20 pts)
        styles = [getattr(it, 'style_family', 'western') for it in all_items if getattr(it, 'style_family', None)]
        if styles and len(set(styles)) == 1:
            family = styles[0].title()
            breakdown['style_coherence'] = 20
            notes.append(f"Unified {family} aesthetic profile")
        elif 'ethnic' in styles and 'western' in styles:
            breakdown['style_coherence'] = 16
            notes.append("Curated Indo-Western contemporary fusion")
        else:
            breakdown['style_coherence'] = 12

        # 3. Color Palette Harmony & Preference (10 to 20 pts)
        all_cols = set()
        for it in all_items:
            for c in cls._detect_item_colors(it):
                if c: all_cols.add(c)

        matched_color = False
        if preferred_color:
            major_pieces = [pieces.get('one_piece'), pieces.get('top'), pieces.get('bottom')]
            for mp in major_pieces:
                if mp and cls._matches_color(mp, preferred_color):
                    matched_color = True
                    break
            if matched_color:
                breakdown['color_harmony'] += 10
                notes.append(f"Featuring your requested {preferred_color.title()} hue")

        has_neutral = bool(all_cols & NEUTRAL_COLORS)
        non_neutrals = all_cols - NEUTRAL_COLORS
        if has_neutral and non_neutrals:
            breakdown['color_harmony'] += 10
            notes.append("Anchored with versatile neutral tones")
        elif len(all_cols) <= 2:
            breakdown['color_harmony'] += 8
            notes.append("Refined cohesive tonal balance")
        else:
            breakdown['color_harmony'] += 5

        breakdown['color_harmony'] = min(20, breakdown['color_harmony'])

        # 4. Occasion Setting Fit (10 to 18 pts)
        occ_rules = OCCASION_RULES.get(occasion.lower(), {})
        fw = pieces.get('footwear')
        fw_type = getattr(fw, 'footwear_type', None) if fw else None
        if fw and fw_type in occ_rules.get('allowed_footwear', set()):
            breakdown['occasion_fit'] = 18
            notes.append(f"Footwear well-suited for {occasion.title()}")
        else:
            occ_kws = cls.OCCASION_MAP.get(occasion.lower(), [])
            all_text = " ".join([getattr(it, 'product_name', '') for it in all_items]).lower()
            if any(kw in all_text for kw in occ_kws):
                breakdown['occasion_fit'] = 15
                notes.append(f"Silhouette tailored for {occasion.title()}")
            else:
                breakdown['occasion_fit'] = 10

        # 5. Budget Utilization & Value (10 to 25 pts) - TARGET: leftover <= Rs.250 or <= 5%
        def get_p(item):
            if not item: return 0.0
            if getattr(item, 'from_wardrobe', False) or getattr(item, '__class__', None).__name__ == 'WardrobeItem':
                return 0.0
            return float(getattr(item, 'selling_price', None) or getattr(item, 'discount_price', None) or getattr(item, 'base_price', 0.0) or 0.0)
        total_cost = sum(get_p(it) for it in all_items)
        rem_budget = float(budget) - total_cost
        target_rem = max(250.0, float(budget) * 0.05)
        if 0 <= rem_budget <= target_rem:
            breakdown['budget_efficiency'] = 25
            notes.append(f"Optimal budget utilization (₹{int(round(rem_budget))} remaining)")
        elif 0 <= rem_budget <= target_rem * 2:
            breakdown['budget_efficiency'] = 18
            notes.append("High budget utilization")
        elif total_cost / float(budget) >= 0.70:
            breakdown['budget_efficiency'] = 12
        else:
            breakdown['budget_efficiency'] = 5

        # 6. Apriori Basket Lift (0 to 5 pts)
        if rules_map and len(all_items) >= 2:
            item_names = [getattr(it, 'product_name', '') for it in all_items if getattr(it, 'product_name', None)]
            max_lift = 1.0
            for i in range(len(item_names)):
                for j in range(len(item_names)):
                    if i != j:
                        pair_lift = rules_map.get((item_names[i], item_names[j]), 1.0)
                        if pair_lift > max_lift:
                            max_lift = pair_lift
            if max_lift > 1.0:
                breakdown['apriori_lift'] = min(int(round(max_lift * 2)), 5)
                notes.append(f"Frequently paired ({max_lift:.1f}x lift)")

        raw_score = sum(breakdown.values())
        final_score = max(55, min(95, raw_score))

        verdict = " · ".join(notes[:3]) if notes else "Complementary coordinated look"
        return final_score, breakdown, verdict, matched_color

    @classmethod
    def generate_budget_outfits(
        cls,
        budget=2000,
        gender='women',
        occasion='casual',
        style='chic',
        preferred_color=None,
        fashion_direction='all',
        sort_by='best',
        limit=100,
        **kwargs
    ):
        """
        Main entry point for generating budget outfits.
        """
        try:
            budget_float = float(budget)
        except (ValueError, TypeError):
            budget_float = 2000.0

        gender_clean = 'women' if 'women' in str(gender).lower() or 'female' in str(gender).lower() else 'men'
        direction_clean = str(fashion_direction).strip().lower() if fashion_direction else 'all'
        pref_color_clean = str(preferred_color).strip().lower() if preferred_color and str(preferred_color).strip().lower() != 'all' else None
        occasion_clean = str(occasion).strip().lower()
        style_clean = str(style).strip().lower()

        # Customer personalisation resolution
        customer_id = kwargs.get('customer_id')
        personalise_flag = kwargs.get('personalise', True)
        if isinstance(personalise_flag, str):
            personalise_flag = personalise_flag.lower() in ('true', '1')

        taste_profile = None
        purchased_pids = set()
        if customer_id and personalise_flag:
            taste_profile = cls.get_customer_taste_profile(customer_id)
            if taste_profile:
                purchased_pids = taste_profile.get('purchased_pids', set())

        # Base filter
        base_filter = (
            Q(is_image_valid=True) &
            ~Q(image__isnull=True) &
            ~Q(image='') &
            Q(hidden=False) &
            Q(is_active=True) &
            Q(confidence__gte=0.6) &
            Q(slot_type__isnull=False) &
            Q(available_quantity__gt=0) &
            Q(discount_price__gt=0)
        )

        inner_q = Q()
        for kw in cls.INNERWEAR_KEYWORDS:
            inner_q |= Q(product_name__icontains=kw)

        craft_q = Q()
        for kw in cls.CRAFT_JUNK_KEYWORDS:
            craft_q |= Q(product_name__icontains=kw)

        if gender_clean == 'women':
            gender_q = (
                Q(main_category="women's clothing") |
                Q(main_category="women's shoes") |
                (Q(main_category='stores') & Q(sub_category__in=['Handbags', 'Potli Bags', 'Dupattas', 'Jewellery', 'Bags'])) |
                (Q(main_category='accessories') & Q(sub_category__in=['Handbags', 'Potli Bags', 'Dupattas', 'Jewellery', 'Bags']))
            )
            men_noise = (
                Q(product_name__icontains="men's") |
                Q(product_name__icontains=" mens ") |
                Q(product_name__istartswith="mens ") |
                Q(product_name__icontains=" men ") |
                Q(product_name__istartswith="men ") |
                Q(product_name__iendswith=" men") |
                Q(product_name__icontains="for men") |
                Q(product_name__icontains="boys'") |
                Q(product_name__icontains="for boys") |
                Q(product_name__icontains="gents") |
                Q(product_name__icontains="school shoes") |
                (Q(sub_category__icontains='men') & ~Q(sub_category__icontains='women')) |
                (Q(main_category__icontains='men') & ~Q(main_category__icontains='women'))
            ) & ~Q(product_name__icontains="women")
            candidate_pool = Product.objects.filter(base_filter, gender_q).exclude(inner_q).exclude(craft_q).exclude(men_noise)
        else:
            gender_q = (Q(main_category__icontains='men') | Q(main_category__icontains='accessories')) & ~Q(main_category__icontains='women')
            candidate_pool = Product.objects.filter(base_filter, gender_q).exclude(inner_q).exclude(craft_q)

        # STRICT ORDERS RULE: Never recommend a product the customer already bought
        if purchased_pids:
            candidate_pool = candidate_pool.exclude(product_id__in=purchased_pids)

        # Separate items by slot_type
        top_qs = candidate_pool.filter(slot_type='top', discount_price__lte=budget_float)
        bottom_qs = candidate_pool.filter(slot_type='bottom', discount_price__lte=budget_float)
        op_qs = candidate_pool.filter(slot_type='one_piece', discount_price__lte=budget_float)

        # Footwear with junk exclusion
        fw_junk_q = Q()
        for kw in cls.FOOTWEAR_JUNK_KEYWORDS:
            fw_junk_q |= Q(product_name__icontains=kw)

        sandal_keywords = [
            'sandal', 'sandals', 'sandle', 'sandles', 'sendal', 'sendel', 'sendle',
            'slide', 'slides', 'chappal', 'chappals', 'chappl',
            'flip flop', 'flipflop', 'slipper', 'slippers', 'toe ring', 'thong', 'strappy flat'
        ]
        sandal_q = (
            Q(footwear_type__in=['sandal', 'flip_flop', 'slipper']) |
            Q(sub_category__in=['Sandals', 'Fashion Sandals', 'Slippers']) |
            Q(sub_category__icontains='sandal') |
            Q(sub_category__icontains='sandle')
        )
        for kw in sandal_keywords:
            sandal_q |= Q(product_name__icontains=kw)

        if gender_clean == 'women':
            fw_qs = Product.objects.filter(
                base_filter,
                main_category="women's shoes",
                discount_price__lte=budget_float
            ).exclude(fw_junk_q).exclude(sandal_q)
            if purchased_pids:
                fw_qs = fw_qs.exclude(product_id__in=purchased_pids)
        else:
            fw_qs = candidate_pool.filter(
                slot_type='footwear',
                discount_price__lte=budget_float
            ).exclude(fw_junk_q).exclude(sandal_q)

        # Bags
        bag_junk_q = Q()
        for kw in cls.BAG_JUNK_KEYWORDS:
            bag_junk_q |= Q(product_name__icontains=kw)
        bag_qs = candidate_pool.filter(slot_type='bag', discount_price__lte=budget_float).exclude(bag_junk_q).exclude(subtype='pouch')
        if gender_clean == 'women':
            bag_qs = bag_qs.exclude(Q(product_name__icontains=" men ") | Q(product_name__istartswith="men ") | Q(sub_category__icontains="men"))
            acc_qs = candidate_pool.filter(slot_type='accessory', discount_price__lte=budget_float).exclude(
                Q(product_name__icontains=" men ") | Q(product_name__istartswith="men ") | Q(sub_category__icontains="men")
            )
        else:
            acc_qs = candidate_pool.filter(slot_type='accessory', discount_price__lte=budget_float)

        # Outerwear / Layers (Jackets, blazers, shrugs, cardigans)
        layer_kws = ['jacket', 'blazer', 'shrug', 'cardigan', 'coat']
        layer_q = Q()
        for k in layer_kws:
            layer_q |= Q(product_name__icontains=k) | Q(subtype__icontains=k)
        layer_qs = candidate_pool.filter(layer_q, discount_price__lte=budget_float)

        # Occasion Footwear filtering
        occ_rules = OCCASION_RULES.get(occasion_clean, {})
        blocked_fw = occ_rules.get('blocked_footwear', set())
        if blocked_fw:
            fw_qs = fw_qs.exclude(footwear_type__in=blocked_fw)
        if occasion_clean in ('sportswear', 'activewear', 'sports'):
            fw_qs = fw_qs.filter(footwear_type='sneaker')

        # Direction-based candidate querysets
        op_dresses = op_qs.exclude(subtype__in=['saree', 'lehenga_set'])
        op_sarees = op_qs.filter(subtype='saree').exclude(
            Q(product_name__icontains='crop top') | Q(product_name__icontains='top') |
            Q(product_name__icontains='t-shirt') | Q(product_name__icontains='shirt')
        )
        op_lehenga_sets = op_qs.filter(subtype='lehenga_set')
        skirt_lehengas = bottom_qs.filter(subtype='lehenga_skirt')
        choli_qs = top_qs.filter(Q(subtype='choli') | Q(product_name__icontains='blouse') | Q(product_name__icontains='choli'))

        # Occasion restrictions: Lehengas are NEVER allowed for Casual, College, or Streetwear
        if occasion_clean in ('casual', 'college', 'streetwear'):
            op_lehenga_sets = op_lehenga_sets.none()
            skirt_lehengas = skirt_lehengas.none()
            op_sarees = op_sarees.filter(formality__lte=3)

        color_q = Q()
        if pref_color_clean:
            color_syns = cls.COLOR_SYNONYMS.get(pref_color_clean, [pref_color_clean])
            for cs in color_syns:
                color_q |= Q(product_name__icontains=cs) | Q(dominant_colours__icontains=cs)

        def item_price(it):
            if not it: return 0.0
            return float(get_effective_product_price(it) or 0.0)

        def dedup_items(lst):
            seen = set()
            out = []
            for x in lst:
                pid = getattr(x, 'product_id', getattr(x, 'id', None))
                if pid and pid not in seen:
                    seen.add(pid)
                    out.append(x)
            return out

        # Fast batched retrieval across active slots (sampling premium and budget tiers)
        raw_tops = dedup_items(list(top_qs.order_by('-discount_price')[:60]) + list(top_qs.order_by('discount_price')[:60]))
        top_kurtas = [t for t in raw_tops if getattr(t, 'subtype', '') == 'kurta' or any(k in (getattr(t, 'product_name', '') or '').lower() for k in ('kurta', 'kurti', 'chikankari'))]
        top_western = [t for t in raw_tops if t not in top_kurtas and getattr(t, 'subtype', '') != 'choli']
        cholis = [t for t in raw_tops if getattr(t, 'subtype', '') == 'choli' or 'blouse' in (getattr(t, 'product_name', '') or '').lower() or 'choli' in (getattr(t, 'product_name', '') or '').lower()]
        tops = raw_tops

        raw_bots = dedup_items(list(bottom_qs.order_by('-discount_price')[:60]) + list(bottom_qs.order_by('discount_price')[:60]))
        bot_ethnic = [b for b in raw_bots if getattr(b, 'subtype', '') in ('palazzo', 'salwar', 'sharara') or any(k in (getattr(b, 'product_name', '') or '').lower() for k in ('palazzo', 'salwar', 'sharara'))]
        bot_western = [b for b in raw_bots if b not in bot_ethnic and getattr(b, 'subtype', '') != 'lehenga_skirt']
        lehenga_skirts = [b for b in raw_bots if getattr(b, 'subtype', '') == 'lehenga_skirt']
        bottoms = [b for b in raw_bots if getattr(b, 'subtype', '') != 'lehenga_skirt']

        raw_ops = dedup_items(list(op_qs.order_by('-discount_price')[:60]) + list(op_qs.order_by('discount_price')[:60]))
        one_pieces = [o for o in raw_ops if getattr(o, 'subtype', '') not in ('saree', 'lehenga_set')]
        op_lehenga_sets = [o for o in raw_ops if getattr(o, 'subtype', '') == 'lehenga_set']
        lehenga_sets = op_lehenga_sets

        # Use ALL eligible sarees in catalogue
        sarees = list(op_sarees.order_by('-discount_price')[:80])

        layer_kws = ['jacket', 'blazer', 'shrug', 'cardigan', 'coat']
        layer_q = Q()
        for k in layer_kws:
            layer_q |= Q(product_name__icontains=k) | Q(subtype__icontains=k)
        layers_pool = dedup_items(list(candidate_pool.filter(layer_q, discount_price__lte=budget_float).order_by('-discount_price')[:20]) + list(candidate_pool.filter(layer_q, discount_price__lte=budget_float).order_by('discount_price')[:20]))

        raw_fws = dedup_items(list(fw_qs.order_by('-discount_price')[:50]) + list(fw_qs.order_by('discount_price')[:50]))
        def is_western_heel(f):
            nm = (getattr(f, 'product_name', '') or '').lower()
            return getattr(f, 'footwear_type', '') == 'heel' or any(k in nm for k in ['heel', 'stiletto', 'pump', 'wedge', 'block heel', 'kitten heel'])
        heels_desc = [f for f in raw_fws if is_western_heel(f)]
        fallback_fw = [f for f in raw_fws if not is_western_heel(f)]
        fw_western = heels_desc + fallback_fw
        fw_ethnic = [f for f in raw_fws if getattr(f, 'footwear_type', '') in ('jutti', 'flat', 'heel') or any(k in (getattr(f, 'product_name', '') or '').lower() for k in ('juti', 'jutti', 'mojari', 'belly', 'bellies', 'heel'))] or raw_fws
        fw_indo_western = raw_fws

        raw_bags = dedup_items(list(bag_qs.order_by('-discount_price')[:30]) + list(bag_qs.order_by('discount_price')[:30]))
        bag_western = [b for b in raw_bags if 'potli' not in (getattr(b, 'product_name', '') or '').lower()]
        bag_ethnic = [b for b in raw_bags if any(k in (getattr(b, 'product_name', '') or '').lower() for k in ('potli', 'clutch', 'ethnic'))] or raw_bags
        bag_all = raw_bags

        raw_accs = dedup_items(list(acc_qs.order_by('-discount_price')[:60]) + list(acc_qs.order_by('discount_price')[:60]))
        necklaces = [a for a in raw_accs if any(k in (getattr(a, 'product_name', '') or '').lower() for k in ('necklace', 'choker', 'chain', 'pendant', 'haar', 'mangalsutra'))]
        earrings = [a for a in raw_accs if any(k in (getattr(a, 'product_name', '') or '').lower() for k in ('earring', 'earrings', 'jhumk', 'stud', 'hoop', 'dangler', 'drop'))]
        bangles = [a for a in raw_accs if any(k in (getattr(a, 'product_name', '') or '').lower() for k in ('bangle', 'bangles', 'bracelet', 'bracelets', 'kada', 'cuff'))]
        watches = [a for a in raw_accs if any(k in (getattr(a, 'product_name', '') or '').lower() for k in ('watch', 'wrist watch'))]
        belts = [a for a in raw_accs if any(k in (getattr(a, 'product_name', '') or '').lower() for k in ('belt', 'waist belt'))]
        sunglasses = [a for a in raw_accs if any(k in (getattr(a, 'product_name', '') or '').lower() for k in ('sunglass', 'sunglasses', 'shades'))]
        scarves = [a for a in raw_accs if any(k in (getattr(a, 'product_name', '') or '').lower() for k in ('scarf', 'stole', 'dupatta'))]

        # Locked Wardrobe pieces
        wardrobe_item_ids = kwargs.get('wardrobe_item_ids') or []
        if isinstance(wardrobe_item_ids, str):
            wardrobe_item_ids = [w.strip() for w in wardrobe_item_ids.split(',') if w.strip()]

        locked_wardrobe_items = []
        if wardrobe_item_ids:
            try:
                from digital_wardrobe.models import WardrobeItem
                raw_w_items = list(WardrobeItem.objects.filter(id__in=wardrobe_item_ids, is_active=True))
                for wi in raw_w_items:
                    setattr(wi, 'from_wardrobe', True)
                    setattr(wi, 'product_id', f"w_{wi.id}")
                    setattr(wi, 'product_name', wi.item_name)
                    setattr(wi, 'name', wi.item_name)
                    setattr(wi, 'discount_price', 0.0)
                    setattr(wi, 'base_price', 0.0)
                    setattr(wi, 'selling_price', 0.0)
                    locked_wardrobe_items.append(wi)
            except Exception as e:
                logger.warning(f"Error loading wardrobe items for budget stylist: {e}")

        if locked_wardrobe_items:
            w_tops = [w for w in locked_wardrobe_items if w.slot_type == 'top']
            w_bots = [w for w in locked_wardrobe_items if w.slot_type == 'bottom']
            w_ops = [w for w in locked_wardrobe_items if w.slot_type == 'one_piece']
            w_fws = [w for w in locked_wardrobe_items if w.slot_type == 'footwear']
            w_bags = [w for w in locked_wardrobe_items if w.slot_type == 'bag']
            w_accs = [w for w in locked_wardrobe_items if w.slot_type == 'accessory']

            if w_tops: tops = w_tops
            if w_bots: bottoms = w_bots
            if w_ops:
                one_pieces = [w for w in w_ops if w.subtype != 'saree'] or w_ops
                sarees = [w for w in w_ops if w.subtype == 'saree'] or sarees
            if w_fws:
                fw_western = w_fws; fw_ethnic = w_fws; fw_indo_western = w_fws
            if w_bags:
                bag_western = w_bags; bag_ethnic = w_bags; bag_all = w_bags
            if w_accs:
                necklaces = [a for a in w_accs if a.accessory_type == 'necklace'] or w_accs
                earrings = [a for a in w_accs if a.accessory_type == 'earrings'] or w_accs
                bangles = [a for a in w_accs if a.accessory_type in ('bangles', 'bracelet')] or w_accs

        # Target leftover bound
        target_leftover = max(250.0, budget_float * 0.05)

        # Accessory Knapsack Optimizer (selects combination to leave <= target_leftover)
        def select_best_accessories(rem_b, outfit_style='western', current_pieces=None):
            if rem_b < 25:
                return []
            cand_acc_pools = [
                ('necklace', necklaces),
                ('earrings', earrings),
                ('bangles', bangles),
                ('watch', watches),
                ('sunglasses', sunglasses),
                ('belt', belts),
                ('scarf', scarves),
            ]

            selected = []
            curr_rem = rem_b

            for acc_type, pool in cand_acc_pools:
                if curr_rem <= target_leftover:
                    break
                best_item = None
                for it in pool:
                    ip = item_price(it)
                    if ip <= curr_rem:
                        best_item = it
                        break
                if best_item:
                    selected.append(best_item)
                    curr_rem -= item_price(best_item)

            return selected

        # -------------------------------------------------------------
        # BUILD CANDIDATE BASES
        # -------------------------------------------------------------
        clothing_bases = []

        # ANCHORS from customer's wishlist/cart (if logged in & personalise=True)
        used_anchor_ids = set()
        if taste_profile and taste_profile.get('anchors') and direction_clean == 'all':
            for anchor_info in taste_profile['anchors']:
                anchor_prod = anchor_info['product']
                a_id = getattr(anchor_prod, 'product_id', getattr(anchor_prod, 'id', None))
                if a_id in used_anchor_ids:
                    continue
                ap = item_price(anchor_prod)
                if ap > budget_float:
                    continue

                slot = getattr(anchor_prod, 'slot_type', None)
                sub = getattr(anchor_prod, 'subtype', 'other')
                style_fam = getattr(anchor_prod, 'style_family', 'western')
                source_label = anchor_info['source']

                if slot == 'one_piece':
                    clothing_bases.append({
                        'base_type': 'saree_lehenga' if sub in ('saree', 'lehenga_set') else 'one_piece',
                        'style_mode': 'ethnic' if style_fam == 'ethnic' else 'western',
                        'item': anchor_prod,
                        'top': None,
                        'bottom': None,
                        'subtype': sub,
                        'price': ap,
                        'role': 'Saree' if sub == 'saree' else ('Lehenga set' if sub == 'lehenga_set' else 'Dress'),
                        'notes': f"Built around your {source_label} item",
                        'is_anchor': True,
                        'anchor_source': source_label,
                        'anchor_product': anchor_prod
                    })
                    used_anchor_ids.add(a_id)
                elif slot == 'top':
                    for b in bottoms[:10]:
                        bp = item_price(b)
                        if ap + bp <= budget_float:
                            clothing_bases.append({
                                'base_type': 'two_piece',
                                'style_mode': 'ethnic' if style_fam == 'ethnic' else 'western',
                                'top': anchor_prod,
                                'bottom': b,
                                'item': None,
                                'subtype': 'two_piece',
                                'price': ap + bp,
                                'role': 'Top + Bottom',
                                'notes': f"Built around your {source_label} item",
                                'is_anchor': True,
                                'anchor_source': source_label,
                                'anchor_product': anchor_prod
                            })
                            used_anchor_ids.add(a_id)
                            break
                elif slot == 'bottom':
                    for t in tops[:10]:
                        tp = item_price(t)
                        if ap + tp <= budget_float:
                            clothing_bases.append({
                                'base_type': 'two_piece',
                                'style_mode': 'ethnic' if style_fam == 'ethnic' else 'western',
                                'top': t,
                                'bottom': anchor_prod,
                                'item': None,
                                'subtype': 'two_piece',
                                'price': ap + tp,
                                'role': 'Top + Bottom',
                                'notes': f"Built around your {source_label} item",
                                'is_anchor': True,
                                'anchor_source': source_label,
                                'anchor_product': anchor_prod
                            })
                            used_anchor_ids.add(a_id)
                            break

        # BASE 1: TWO-PIECE WESTERN / INDO-WESTERN
        if direction_clean in ('all', 'western', 'indo-western', 'ethnic'):
            b1_count = 0
            top_base_usage = Counter()
            bot_base_usage = Counter()
            for t in tops:
                t_id = getattr(t, 'product_id', getattr(t, 'id', None))
                if top_base_usage[t_id] >= 3:
                    continue
                tp = item_price(t)
                if tp >= budget_float:
                    continue
                t_sub = getattr(t, 'subtype', 'other')
                t_style = getattr(t, 'style_family', 'western')
                t_form = getattr(t, 'formality', 3) or 3
                t_pat = getattr(t, 'pattern', 'solid')
                t_cols = cls._detect_item_colors(t)
                t_name = (getattr(t, 'product_name', '') or '').lower()
                is_kurta_top = t_sub == 'kurta' or any(k in t_name for k in ('kurta', 'kurti', 'chikankari', 'anarkali'))

                if direction_clean == 'western' and (is_kurta_top or t_style != 'western'):
                    continue
                if direction_clean == 'ethnic' and not is_kurta_top and t_style != 'ethnic':
                    continue
                if direction_clean == 'indo-western' and not is_kurta_top and t_style != 'western':
                    continue

                for b in bottoms:
                    b_id = getattr(b, 'product_id', getattr(b, 'id', None))
                    if bot_base_usage[b_id] >= 3:
                        continue
                    bp = item_price(b)
                    if tp + bp > budget_float:
                        continue
                    b_sub = getattr(b, 'subtype', 'other')
                    b_style = getattr(b, 'style_family', 'western')
                    b_form = getattr(b, 'formality', 3) or 3
                    b_pat = getattr(b, 'pattern', 'solid')
                    b_cols = cls._detect_item_colors(b)
                    b_name = (getattr(b, 'product_name', '') or '').lower()
                    is_ethnic_bottom = (
                        b_sub in ('palazzo', 'salwar', 'churidar', 'dhoti', 'sharara', 'lehenga_skirt') or
                        any(k in b_name for k in ('palazzo', 'salwar', 'churidar', 'dhoti', 'sharara', 'ethnic'))
                    )
                    is_western_bottom = (
                        not is_ethnic_bottom and (
                            b_sub in ('jeans', 'skirt', 'shorts', 'trousers', 'cargo', 'pants', 'leggings') or
                            b_style == 'western'
                        )
                    )

                    if direction_clean == 'western' and not is_western_bottom:
                        continue
                    if direction_clean == 'ethnic' and not is_ethnic_bottom and b_style != 'ethnic':
                        continue
                    if direction_clean == 'indo-western':
                        if is_kurta_top and not is_western_bottom:
                            continue
                        if not is_kurta_top and not is_ethnic_bottom:
                            continue

                    if abs(t_form - b_form) > 1:
                        continue
                    if t_pat == 'embellished' and b_pat == 'embellished':
                        continue
                    if t_cols and b_cols and are_colors_clashing(t_cols, b_cols):
                        continue

                    outfit_mode = 'ethnic' if (is_kurta_top and is_ethnic_bottom) else ('indo-western' if (is_kurta_top or is_ethnic_bottom) else 'western')
                    role_name = (
                        'Kurti + Palazzo' if (is_kurta_top and is_ethnic_bottom) else
                        ('Kurti + Denim Fusion' if (is_kurta_top and 'jeans' in b_name) else
                         ('Kurti + Bottom' if is_kurta_top else
                          ('Top + Palazzo Fusion' if is_ethnic_bottom else 'Top + Bottom')))
                    )

                    clothing_bases.append({
                        'base_type': 'two_piece',
                        'style_mode': outfit_mode,
                        'top': t,
                        'bottom': b,
                        'item': None,
                        'subtype': 'two_piece',
                        'price': tp + bp,
                        'role': role_name,
                        'notes': None
                    })
                    top_base_usage[t_id] += 1
                    bot_base_usage[b_id] += 1
                    b1_count += 1
                    if top_base_usage[t_id] >= 3:
                        break
                    if b1_count >= 80:
                        break
                if b1_count >= 80:
                    break

        # BASE 2: ONE-PIECE (Dresses, Jumpsuits) - Including expensive bases up to 100% of budget
        if direction_clean in ('all', 'dresses', 'western'):
            b2_count = 0
            for op in one_pieces:
                p = item_price(op)
                if p > budget_float:
                    continue
                nm = (getattr(op, 'product_name', None) or getattr(op, 'name', '') or '').lower()
                clothing_bases.append({
                    'base_type': 'one_piece',
                    'style_mode': 'western',
                    'item': op,
                    'top': None,
                    'bottom': None,
                    'subtype': 'one_piece',
                    'price': p,
                    'role': 'Jumpsuit' if any(k in nm for k in ('jumpsuit', 'romper', 'playsuit')) else 'Dress',
                    'notes': None
                })
                b2_count += 1
                if b2_count >= 50:
                    break

        # BASE 3: SAREE / LEHENGA (Ethnic) - Using ALL eligible sarees in catalogue & lehengas
        if direction_clean in ('all', 'ethnic'):
            b3_count = 0
            for s in sarees:
                sp = item_price(s)
                if sp > budget_float:
                    continue
                inc_blouse = getattr(s, 'includes_blouse', False)
                if inc_blouse:
                    clothing_bases.append({
                        'base_type': 'saree_lehenga',
                        'style_mode': 'ethnic',
                        'item': s,
                        'top': None,
                        'bottom': None,
                        'subtype': 'saree',
                        'price': sp,
                        'role': 'Saree',
                        'notes': 'Blouse piece included'
                    })
                    b3_count += 1
                else:
                    for choli in cholis[:3]:
                        cp = item_price(choli)
                        if sp + cp <= budget_float:
                            clothing_bases.append({
                                'base_type': 'saree_lehenga',
                                'style_mode': 'ethnic',
                                'item': s,
                                'top': choli,
                                'bottom': None,
                                'subtype': 'saree',
                                'price': sp + cp,
                                'role': 'Saree',
                                'notes': 'Paired with matching blouse'
                            })
                            b3_count += 1
                            if b3_count >= 50:
                                break
                if b3_count >= 50:
                    break

            if occasion_clean not in ('casual', 'college', 'streetwear'):
                for ls in lehenga_sets:
                    lsp = item_price(ls)
                    if lsp <= budget_float:
                        clothing_bases.append({
                            'base_type': 'saree_lehenga',
                            'style_mode': 'ethnic',
                            'item': ls,
                            'top': None,
                            'bottom': None,
                            'subtype': 'lehenga_set',
                            'price': lsp,
                            'role': 'Lehenga set',
                            'notes': 'Dupatta included'
                        })
                        b3_count += 1
                        if b3_count >= 30:
                            break

        if not clothing_bases:
            return {
                'success': False,
                'message': f"No matching clothing pieces found under budget Rs.{budget_float:.0f}. Try increasing your budget or selecting 'Surprise Me'.",
                'budget': int(budget_float),
                'outfits': []
            }

        # Apriori rules
        all_product_names = [getattr(it, 'product_name', '') for it in (tops + bottoms + one_pieces + sarees) if getattr(it, 'product_name', None)]
        rules_map = {}
        if all_product_names:
            rules_qs = ProductRecommendation.objects.filter(
                product__in=all_product_names[:50],
                frequently_bought_with__in=all_product_names[:50]
            ).values('product', 'frequently_bought_with', 'lift')
            for r in rules_qs:
                rules_map[(r['product'], r['frequently_bought_with'])] = float(r['lift']) if r['lift'] else 1.0

        user_prefs = {
            'budget': budget_float,
            'occasion': occasion_clean,
            'style': style_clean,
            'preferred_color': pref_color_clean,
            'gender': gender_clean,
            'category_direction': direction_clean,
        }

        # -------------------------------------------------------------
        # ASSEMBLE CANDIDATE OUTFITS WITH 4-STEP LEFTOVER REDUCER
        # -------------------------------------------------------------
        candidate_outfits = []

        for base in clothing_bases:
            base_p = base['price']
            smode = base.get('style_mode', 'western')
            is_saree_or_lehenga = base.get('subtype') in ('saree', 'lehenga_set')

            if smode == 'western':
                cur_fw_pool = fw_western
                cur_bag_pool = bag_western
            elif smode == 'ethnic':
                cur_fw_pool = fw_ethnic
                cur_bag_pool = bag_ethnic
            else:
                cur_fw_pool = fw_indo_western
                cur_bag_pool = bag_all

            # Filter footwear (prioritize heels for western, then higher priced to utilize budget)
            eligible_fw = [f for f in cur_fw_pool if base_p + item_price(f) <= budget_float]
            if smode == 'western':
                def western_fw_sort_key(f):
                    is_heel = getattr(f, 'footwear_type', '') == 'heel' or any(
                        k in (getattr(f, 'product_name', '') or '').lower()
                        for k in ['heel', 'stiletto', 'pump', 'wedge', 'block heel', 'kitten heel']
                    )
                    return (1 if is_heel else 0, item_price(f))
                test_fws = sorted(eligible_fw, key=western_fw_sort_key, reverse=True)[:3] if eligible_fw else [None]
            else:
                test_fws = sorted(eligible_fw, key=lambda f: item_price(f), reverse=True)[:3] if eligible_fw else [None]

            for fw in test_fws:
                fw_p = item_price(fw)
                cur_p = base_p + fw_p
                if cur_p > budget_float:
                    continue

                eligible_bags = [b for b in cur_bag_pool if cur_p + item_price(b) <= budget_float]
                test_bags = sorted(eligible_bags, key=lambda b: item_price(b), reverse=True)[:2] if eligible_bags else [None]

                for bg in test_bags:
                    bg_p = item_price(bg)
                    subtotal = cur_p + bg_p
                    if subtotal > budget_float:
                        continue

                    # Current pieces before reducer
                    pieces_now = {
                        'one_piece': base.get('item'),
                        'top': base.get('top'),
                        'bottom': base.get('bottom'),
                        'layer': None,
                        'footwear': fw,
                        'bag': bg,
                        'accessories': []
                    }

                    rem = budget_float - subtotal

                    # --- 4-STEP LEFTOVER REDUCTION PIPELINE ---
                    # Step a: Upgrade to pricier compatible piece in same slot (already sampled top prices above)
                    # Step b: Add layers (jacket, blazer, shrug, cardigan) when compatible and leftover > target_leftover
                    chosen_layer = None
                    if rem > target_leftover and not is_saree_or_lehenga and layers_pool:
                        for lyr in layers_pool[:8]:
                            lp = item_price(lyr)
                            if lp <= rem:
                                test_pieces = dict(pieces_now)
                                test_pieces['layer'] = lyr
                                p_ok, _ = validate_outfit(test_pieces, user_prefs)
                                if p_ok:
                                    chosen_layer = lyr
                                    rem -= lp
                                    pieces_now['layer'] = lyr
                                    break

                    # Step c: Add accessories (one per type: jewellery, watch, belt, sunglasses, scarf)
                    matching_accs = select_best_accessories(rem, outfit_style=smode, current_pieces=pieces_now)
                    pieces_now['accessories'] = matching_accs
                    acc_cost = sum(item_price(a) for a in matching_accs)
                    total_cost = (budget_float - rem) + acc_cost

                    if total_cost > budget_float:
                        continue

                    # HARD COMPATIBILITY GATE (validate_outfit)
                    passed, reasons = validate_outfit(pieces_now, user_prefs)
                    if not passed:
                        if not hasattr(cls, '_printed_fails'):
                            cls._printed_fails = 0
                        if cls._printed_fails < 5:
                            print(f"GATE FAIL [{cls._printed_fails}]: {reasons}")
                            cls._printed_fails += 1
                        continue

                    coins_left = max(0, int(budget_float - total_cost))

                    # Honest remaining budget note if unable to find pieces to reach target
                    notes_rem = None
                    if coins_left > target_leftover:
                        notes_rem = "We could not find more matching pieces to use the remaining budget."

                    # Personalisation tag logic
                    is_pers = False
                    pers_reason = None
                    if taste_profile:
                        if base.get('is_anchor'):
                            is_pers = True
                            pers_reason = f"Built around your {base.get('anchor_source')} item"
                        else:
                            # Check if matches customer's preferred colors or style
                            top_cols = taste_profile.get('top_colors', [])
                            top_styles = taste_profile.get('top_styles', [])
                            matched_c = [c for c in top_cols if any(cls._matches_color(it, c) for it in [pieces_now.get('one_piece'), pieces_now.get('top'), pieces_now.get('bottom')])]
                            if matched_c:
                                is_pers = True
                                cols_str = " & ".join(c.title() for c in matched_c[:2])
                                pers_reason = f"Matches the {cols_str} you often buy"
                            elif smode in top_styles:
                                is_pers = True
                                pers_reason = f"Curated for your preferred {smode.title()} style"

                    candidate_outfits.append({
                        'base_type': base['base_type'],
                        'base_meta': base,
                        'pieces': pieces_now,
                        'total_price': int(round(total_cost)),
                        'coins_remaining': coins_left,
                        'budget': int(budget_float),
                        'completeness': 'full' if (fw and bg) else ('core' if (fw or bg or matching_accs) else 'basic'),
                        'notes_remaining': notes_rem,
                        'is_personalised': is_pers,
                        'personalisation_reason': pers_reason,
                    })

                    if coins_left <= target_leftover:
                        break
                if candidate_outfits and candidate_outfits[-1]['coins_remaining'] <= target_leftover:
                    break

        # Calculate styling scores & breakdown
        scored_outfits = []
        for o in candidate_outfits:
            pieces = o['pieces']
            score, breakdown, verdict, matched_col = cls._calculate_score_and_breakdown(
                pieces=pieces,
                budget=budget_float,
                occasion=occasion_clean,
                style=style_clean,
                preferred_color=pref_color_clean,
                rules_map=rules_map
            )
            o['styling_score'] = score
            o['score_breakdown'] = breakdown
            o['style_verdict'] = verdict
            o['matched_preferred_color'] = matched_col
            scored_outfits.append(o)

        # -------------------------------------------------------------
        # RANKING & DIVERSITY FILTERING
        # -------------------------------------------------------------
        # Rank:
        # 1. Quality / Styling Harmony first
        # 2. Budget utilization: heavy bonus for remaining budget <= target_leftover
        # 3. Requested color matching
        def outfit_rank_key(o):
            rem = o['coins_remaining']
            util_bonus = (2000 - rem) if (0 <= rem <= target_leftover) else (-rem)
            col_bonus = 500 if o.get('matched_preferred_color') else 0
            pers_bonus = 300 if o.get('is_personalised') else 0
            return (o['styling_score'] * 10 + util_bonus + col_bonus + pers_bonus)

        scored_outfits.sort(key=outfit_rank_key, reverse=True)

        # Separate personalised vs non-personalised for "Surprise Me" placement
        # First 3-4 outfits personalised (aiming ~half anchors, ~half taste profile)
        pers_anchor_outfits = [o for o in scored_outfits if o.get('is_personalised') and o.get('base_meta', {}).get('is_anchor')]
        pers_taste_outfits = [o for o in scored_outfits if o.get('is_personalised') and not o.get('base_meta', {}).get('is_anchor')]
        normal_outfits = [o for o in scored_outfits if not o.get('is_personalised')]

        assembled_order = []
        if direction_clean == 'all' and (pers_anchor_outfits or pers_taste_outfits):
            # Take up to 2 anchors, up to 2 taste profile
            picked_anchors = pers_anchor_outfits[:2]
            picked_taste = pers_taste_outfits[:2]
            if len(picked_anchors) + len(picked_taste) < 4:
                # Fill remaining up to 4 from whichever has more
                if len(picked_anchors) < 2 and len(pers_taste_outfits) > 2:
                    picked_taste = pers_taste_outfits[:4 - len(picked_anchors)]
                elif len(picked_taste) < 2 and len(pers_anchor_outfits) > 2:
                    picked_anchors = pers_anchor_outfits[:4 - len(picked_taste)]
            assembled_order = picked_anchors + picked_taste + normal_outfits + pers_anchor_outfits[2:] + pers_taste_outfits[2:]
        else:
            assembled_order = scored_outfits

        # Apply DIVERSITY RULES:
        # 1. Single product appears in AT MOST 3 outfits
        # 2. No two outfits identical (share >= 2 primary garments)
        curated_outfits = []
        seen_outfit_item_sets = []
        product_appearance_count = Counter()

        for cand in assembled_order:
            if len(curated_outfits) >= 50:
                break

            p = cand['pieces']
            all_items = [p.get('one_piece'), p.get('top'), p.get('bottom'), p.get('layer'), p.get('footwear'), p.get('bag')] + (p.get('accessories') or [])
            item_ids = [getattr(it, 'product_id', getattr(it, 'id', None)) for it in all_items if it]
            item_set = set(item_ids)

            # Rule: Single product in at most 3 outfits
            if any(product_appearance_count[pid] >= 3 for pid in item_ids):
                continue

            # Rule: No two outfits identical
            if item_set in seen_outfit_item_sets:
                continue

            # Garment diversity: primary base garment appears at most once across looks
            primary_id = getattr(p.get('one_piece') or p.get('top'), 'product_id', None)
            if primary_id and product_appearance_count[primary_id] >= 1:
                continue

            # Accept outfit
            curated_outfits.append(cand)
            seen_outfit_item_sets.append(item_set)
            for pid in item_ids:
                product_appearance_count[pid] += 1

        # Fallback: If strict diversity leaves fewer than 6 outfits, allow candidate outfits respecting the <= 3 limit
        if len(curated_outfits) < 6:
            for cand in assembled_order:
                if len(curated_outfits) >= 12:
                    break
                if cand in curated_outfits:
                    continue
                p = cand['pieces']
                all_items = [p.get('one_piece'), p.get('top'), p.get('bottom'), p.get('layer'), p.get('footwear'), p.get('bag')] + (p.get('accessories') or [])
                item_ids = [getattr(it, 'product_id', getattr(it, 'id', None)) for it in all_items if it]
                item_set = set(item_ids)
                if any(product_appearance_count[pid] >= 3 for pid in item_ids):
                    continue
                # Reject exact duplicate outfits
                if item_set in seen_outfit_item_sets:
                    continue
                curated_outfits.append(cand)
                seen_outfit_item_sets.append(item_set)
                for pid in item_ids:
                    product_appearance_count[pid] += 1

        # Sarees in Surprise Me / Ethnic: Ensure sarees appear whenever occasion allows
        if direction_clean in ('all', 'ethnic') and occasion_clean not in ('sportswear', 'activewear'):
            has_saree = any(o['base_type'] == 'saree_lehenga' for o in curated_outfits)
            if not has_saree:
                for cand in assembled_order:
                    if cand['base_type'] == 'saree_lehenga':
                        curated_outfits.insert(min(2, len(curated_outfits)), cand)
                        break

        # Serialize final outfit objects
        print(f"DEBUG: clothing_bases={len(clothing_bases)}, candidate_outfits={len(candidate_outfits)}, curated_outfits={len(curated_outfits)}")
        serialized_outfits = []
        for idx, o in enumerate(curated_outfits):
            p = o['pieces']
            base_meta = o['base_meta']
            tier_info = cls.TIER_METADATA[min(idx, len(cls.TIER_METADATA) - 1)]
            badge, tier_name, tier_desc = tier_info

            op_ser = serialize_catalog_product(p.get('one_piece'))
            top_ser = serialize_catalog_product(p.get('top'))
            bot_ser = serialize_catalog_product(p.get('bottom'))
            layer_ser = serialize_catalog_product(p.get('layer'))
            fw_ser = serialize_catalog_product(p.get('footwear'))
            bag_ser = serialize_catalog_product(p.get('bag'))
            acc_ser = [serialize_catalog_product(a) for a in p.get('accessories', [])]

            blouse_ser = None
            if op_ser and top_ser:
                primary_garment = op_ser
                blouse_ser = top_ser
            elif op_ser:
                primary_garment = op_ser
            else:
                primary_garment = top_ser

            is_one_piece = op_ser is not None

            # Total price is exact sum of all included serialized items
            total_cost = sum(
                item['selling_price'] for item in [primary_garment, blouse_ser, bot_ser, layer_ser, fw_ser, bag_ser] if item and 'selling_price' in item
            ) + sum(
                acc['selling_price'] for acc in (acc_ser or []) if acc and 'selling_price' in acc
            )
            if total_cost > int(budget_float):
                print(f"DEBUG REJECT: total_cost={total_cost} > budget_float={budget_float}")
                continue

            coins_left = max(0, int(budget_float - total_cost))

            # Missing pieces suggestions
            missing = []
            if not fw_ser:
                missing.append({
                    'slot': 'footwear',
                    'label': 'Footwear',
                    'text': 'Add footwear to complete this look',
                })
            if not bag_ser:
                missing.append({
                    'slot': 'bag',
                    'label': 'Bag',
                    'text': 'Add a handbag or clutch to complete this look',
                })

            serialized_outfits.append({
                'id': f"outfit_{idx + 1}_{int(total_cost)}",
                'base_type': o.get('base_type', 'two_piece'),
                'completeness': o['completeness'],
                'badge': badge,
                'tier': tier_name,
                'tier_desc': tier_desc,
                'is_dress': is_one_piece,
                'garment_type': base_meta.get('role', 'Top'),
                'topwear': primary_garment,
                'blouse': blouse_ser,
                'bottomwear': bot_ser,
                'layer': layer_ser,
                'footwear': fw_ser,
                'bag': bag_ser,
                'accessories': acc_ser,
                'total_price': total_cost,
                'budget': int(budget_float),
                'savings': coins_left,
                'coins_remaining': coins_left,
                'styling_score': o['styling_score'],
                'score_breakdown': o['score_breakdown'],
                'style_verdict': o['style_verdict'],
                'matched_preferred_color': bool(o.get('matched_preferred_color', False)),
                'notes': base_meta.get('notes'),
                'notes_remaining': o.get('notes_remaining'),
                'is_personalised': o.get('is_personalised', False),
                'personalisation_reason': o.get('personalisation_reason'),
                'missing_pieces': missing,
            })

        # Apply sort_by order if explicitly requested
        if sort_by == 'price_low':
            serialized_outfits.sort(key=lambda o: o['total_price'])
        elif sort_by == 'price_high':
            serialized_outfits.sort(key=lambda o: o['total_price'], reverse=True)
        elif sort_by == 'score':
            serialized_outfits.sort(key=lambda o: o['styling_score'], reverse=True)

        if limit and limit > 0:
            serialized_outfits = serialized_outfits[:limit]

        count = len(serialized_outfits)
        msg = f"We found {count} looks that genuinely suit your budget" if count < 6 else f"Curated {count} complete looks tailored to your budget"

        return {
            'success': True,
            'message': msg,
            'budget': int(budget_float),
            'gender': gender_clean,
            'occasion': occasion_clean,
            'style': style_clean,
            'preferred_color': pref_color_clean,
            'category_direction': direction_clean,
            'total_candidates_analyzed': len(scored_outfits),
            'total_outfits': count,
            'outfits': serialized_outfits
        }
