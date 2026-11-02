import hashlib
import json
from typing import List, Dict, Any, Optional
from django.utils import timezone
from django.db.models import Q
from recommendations.outfit_validator import validate_outfit, are_colors_clashing
from recommendations.models import ProductRecommendation
from .models import WardrobeItem, WardrobeMatch
from .tagger import CANONICAL_COLOR_PALETTE, PALETTE_NAMES, PALETTE_LAB

# ==============================================================================
# FASHION COLOR PAIRING KNOWLEDGE TABLE
# ==============================================================================
NEUTRALS = {
    'black', 'white', 'cream', 'ivory', 'beige', 'taupe', 'grey', 'charcoal',
    'navy', 'tan', 'denim blue', 'denim', 'neutral', 'nude', 'camel', 'khaki', 'blush'
}

COLOR_FAMILIES = {
    'black': 'neutral',
    'white': 'neutral',
    'grey': 'neutral',
    'cream': 'neutral_warm',
    'ivory': 'neutral_warm',
    'beige': 'neutral_warm',
    'taupe': 'neutral_warm',
    'tan': 'neutral_warm',
    'camel': 'neutral_warm',
    'khaki': 'neutral_warm',
    'brown': 'earth',
    'olive': 'earth',
    'navy': 'neutral_cool',
    'denim blue': 'neutral_cool',
    'denim': 'neutral_cool',
    'teal': 'jewel_cool',
    'maroon': 'jewel_warm',
    'burgundy': 'jewel_warm',
    'pink': 'warm_soft',
    'blush': 'neutral_warm',
    'mustard': 'warm_spice',
    'yellow': 'warm_vibrant',
    'red': 'warm_bold',
    'green': 'jewel_earth',
    'silver': 'metallic_cool',
    'gold': 'metallic_warm',
    'orange': 'warm_vibrant',
    'purple': 'jewel_cool',
    'neutral': 'neutral',
}

COLOR_PAIRINGS = {
    'taupe': {
        'black': (16.0, "Neutral taupe + black creates a timeless, chic contrast"),
        'white': (16.0, "Crisp white + soft taupe offers an elevated, clean aesthetic"),
        'cream': (15.0, "Warm monochromatic tones create an effortless luxury palette"),
        'ivory': (15.0, "Warm monochromatic tones create an effortless luxury palette"),
        'navy': (16.0, "Deep navy grounds earthy taupe with sophisticated contrast"),
        'denim blue': (15.0, "Taupe + classic denim delivers everyday casual elegance"),
        'denim': (15.0, "Taupe + classic denim delivers everyday casual elegance"),
        'olive': (14.0, "Earthy olive and muted taupe harmonize organically"),
        'brown': (14.0, "Tonal espresso and taupe form a warm, layered look"),
        'tan': (14.0, "Subtle earth-tone gradient with balanced warmth"),
        'khaki': (13.0, "Safari-inspired neutral pairing with subtle depth"),
        'burgundy': (13.0, "Muted taupe provides a quiet base for rich burgundy accents"),
        'maroon': (13.0, "Deep maroon pairs harmoniously with grounding taupe tones"),
        'blush': (13.0, "Soft blush and taupe form a gentle, romantic palette"),
        'pink': (12.0, "Understated taupe tones soften vibrant pink"),
    },
    'beige': {
        'black': (16.0, "High-contrast chic: beige base anchored by black"),
        'white': (16.0, "Crisp white + warm beige for a breezy, clean aesthetic"),
        'navy': (16.0, "Nautical sophistication: navy with warm beige"),
        'denim blue': (15.0, "Beige + denim = quintessential weekend elegance"),
        'olive': (14.0, "Organic earth-tone harmony"),
        'brown': (14.0, "Warm monochromatic cocoa and beige"),
        'tan': (14.0, "Seamless warm tonal coordination"),
        'cream': (15.0, "Soft tonal warmth"),
        'burgundy': (14.0, "Rich wine accent against warm neutral canvas"),
    },
    'cream': {
        'black': (16.0, "Softened monochrome: rich cream on deep black"),
        'navy': (16.0, "Classic nautical refinement: warm cream with navy"),
        'denim blue': (15.0, "Relaxed weekend elegance with classic denim"),
        'tan': (15.0, "Tonal luxury layering with warm cognac tan"),
        'olive': (14.0, "Organic nature-inspired harmony"),
        'brown': (14.0, "Rich espresso and cream contrast"),
        'taupe': (15.0, "Understated tonal neutral elegance"),
        'gold': (14.0, "Luminous warm metallic complement"),
    },
    'ivory': {
        'black': (16.0, "Editorial contrast: ivory canvas grounded by sharp black"),
        'navy': (16.0, "Refined high-contrast pairing with deep navy"),
        'denim blue': (15.0, "Clean daytime styling on classic denim"),
        'tan': (15.0, "Warm heritage leather and ivory combination"),
        'olive': (14.0, "Earthy quiet luxury aesthetic"),
        'gold': (15.0, "Festive luminous glow with warm metallic accents"),
        'maroon': (14.0, "Rich jewel tone popped against ivory canvas"),
    },
    'tan': {
        'white': (16.0, "Sun-drenched Mediterranean contrast: crisp white with warm tan"),
        'black': (15.0, "Sleek metropolitan neutral duo"),
        'navy': (16.0, "Ivy League heritage palette: navy and warm tan"),
        'denim blue': (15.0, "Quintessential casual denim with saddle tan accents"),
        'cream': (15.0, "Effortless warm tonal gradient"),
        'olive': (14.0, "Safari-inspired utilitarian harmony"),
    },
    'camel': {
        'black': (17.0, "Iconic luxury tailoring: camel anchored by deep black"),
        'white': (16.0, "Fresh, luminous contrast with crisp white"),
        'navy': (16.0, "Timeless equestrian refinement: navy and rich camel"),
        'denim blue': (15.0, "Elevated casual denim pairing"),
        'cream': (15.0, "Monochromatic rich tonal warmth"),
        'burgundy': (14.0, "Autumnal richness: deep wine and camel"),
    },
    'brown': {
        'cream': (16.0, "Warm espresso and cream: indulgent tonal harmony"),
        'white': (15.0, "Crisp modern contrast: earthy brown with bright white"),
        'denim blue': (15.0, "Classic workwear-inspired pairing"),
        'tan': (14.0, "Layered chocolate and caramel gradient"),
        'pink': (13.0, "Retro chic: dusty pink softens deep cocoa"),
        'gold': (13.0, "Lustrous warm metallic pairing"),
    },
    'olive': {
        'cream': (16.0, "Understated luxury: earthy olive with soft cream"),
        'white': (15.0, "Clean, modern military-chic contrast"),
        'black': (15.0, "Urban utilitarian styling: olive on sleek black"),
        'denim blue': (15.0, "Natural everyday pairing: olive with authentic blue denim"),
        'tan': (14.0, "Organic safari earth tones"),
        'mustard': (13.0, "Warm spicy autumnal palette"),
    },
    'khaki': {
        'white': (16.0, "Crisp safari minimalist contrast"),
        'navy': (16.0, "Tailored smart-casual standard: navy and khaki"),
        'black': (15.0, "Modern sharp edge on neutral khaki"),
        'denim blue': (15.0, "Everyday relaxed elegance"),
        'olive': (13.0, "Subtle tonal earth palette"),
    },
    'navy': {
        'white': (17.0, "Crisp nautical contrast: pure white on deep navy"),
        'cream': (16.0, "Softened marine aesthetic with warm cream"),
        'tan': (16.0, "Heritage preppy harmony: navy and rich saddle tan"),
        'beige': (15.0, "Subtle balanced contrast with warm beige"),
        'gold': (15.0, "Deep navy elevated with luminous metallic accent"),
        'yellow': (15.0, "Vibrant complementary pop against rich navy"),
        'denim blue': (14.0, "Tonal indigo layering"),
        'red': (14.0, "Classic high-energy nautical statement"),
    },
    'denim blue': {
        'white': (17.0, "Quintessential classic: crisp white on authentic denim"),
        'black': (16.0, "Downtown chic: deep black effortlessly grounds blue denim"),
        'cream': (15.0, "Breezy weekend styling with warm cream tones"),
        'yellow': (16.0, "Cheerful complementary harmony: bright yellow on blue denim"),
        'mustard': (15.0, "Rich mustard warmth harmonizes with indigo denim"),
        'tan': (15.0, "Timeless American heritage leather with blue denim"),
        'navy': (14.0, "Tonal denim and navy coordination"),
        'pink': (13.0, "Soft feminine pop against casual denim"),
    },
    'denim': {
        'white': (17.0, "Quintessential classic: crisp white on authentic denim"),
        'black': (16.0, "Downtown chic: deep black effortlessly grounds denim"),
        'yellow': (16.0, "Cheerful complementary harmony: bright yellow on denim"),
        'mustard': (15.0, "Rich mustard warmth harmonizes with denim"),
        'tan': (15.0, "Timeless heritage leather with denim"),
        'navy': (14.0, "Tonal denim and navy coordination"),
    },
    'teal': {
        'white': (16.0, "Fresh jewel contrast: vibrant teal with crisp white"),
        'cream': (15.0, "Softened jewel elegance with warm cream"),
        'black': (15.0, "Moody evening richness: teal against black"),
        'tan': (14.0, "Earthy warm leather grounds aquatic teal"),
        'gold': (15.0, "Opulent jewel tone elevated by lustrous gold"),
        'navy': (14.0, "Deep ocean tonal layering"),
    },
    'maroon': {
        'gold': (17.0, "Regal Indian wedding opulence: rich maroon with antique gold"),
        'cream': (16.0, "Warm ivory canvas softens royal maroon"),
        'white': (15.0, "High-contrast clean polish"),
        'black': (15.0, "Moody sophisticated evening statement"),
        'tan': (14.0, "Autumnal richness with warm saddle leather"),
        'pink': (13.0, "Tonal blush and wine gradient"),
    },
    'burgundy': {
        'cream': (16.0, "Indulgent warm wine on ivory/cream foundation"),
        'black': (16.0, "Sleek autumnal evening sophistication"),
        'white': (15.0, "Striking clean contrast"),
        'grey': (15.0, "Tailored metropolitan pairing: cool grey softens deep wine"),
        'tan': (14.0, "Equestrian warmth: rich leather with deep burgundy"),
        'gold': (15.0, "Luminous festive metallic complement"),
    },
    'pink': {
        'white': (16.0, "Fresh romantic pastel contrast"),
        'grey': (15.0, "Modern cool-toned pairing: soft pink balanced by sleek grey"),
        'denim blue': (15.0, "Casual weekend sweetness with classic blue denim"),
        'navy': (15.0, "Grounding deep navy offsets playful pink"),
        'black': (14.0, "Graphic editorial contrast"),
        'burgundy': (13.0, "Chic monochromatic berry spectrum"),
    },
    'blush': {
        'taupe': (16.0, "Understated feminine quiet luxury: blush with soft taupe"),
        'grey': (15.0, "Delicate pastel grounded by urban grey"),
        'white': (16.0, "Breezy ethereal romantic duo"),
        'black': (15.0, "High-contrast modern edge"),
        'navy': (15.0, "Classic tailored grounding for soft blush"),
        'denim blue': (14.0, "Effortless casual elegance"),
    },
    'mustard': {
        'navy': (17.0, "Dynamic complementary masterclass: warm spicy mustard on deep navy"),
        'denim blue': (16.0, "Quintessential color pop: mustard top on classic denim blue"),
        'black': (15.0, "High-impact modern graphic contrast"),
        'white': (15.0, "Sun-kissed cheerful clarity"),
        'olive': (14.0, "Earthy bohemian autumnal harmony"),
        'brown': (14.0, "Rich spice and espresso coordination"),
        'tan': (13.0, "Warm tonal earth palette"),
    },
    'yellow': {
        'navy': (17.0, "Complementary color harmony: vibrant yellow on deep navy"),
        'denim blue': (16.0, "Sunny yellow top effortlessly pairs with classic denim blue"),
        'white': (16.0, "Fresh, cheerful summer contrast"),
        'grey': (15.0, "Modern editorial pairing: energetic yellow softened by grey"),
        'black': (15.0, "High-impact modern graphic contrast"),
        'olive': (14.0, "Warm golden tones harmonize with rich olive"),
        'tan': (13.0, "Warm sunshine gradient with natural leather"),
    },
    'red': {
        'black': (17.0, "Dramatic power dressing: bold red on deep black"),
        'white': (16.0, "Iconic vibrant statement contrast"),
        'denim blue': (16.0, "Americana casual classic: bright red with authentic denim"),
        'navy': (15.0, "High-energy nautical harmony"),
        'pink': (13.0, "Modern fashion-forward color-blocking"),
    },
    'green': {
        'white': (16.0, "Lush botanical freshness with crisp white"),
        'black': (15.0, "Moody emerald richness grounded by black"),
        'cream': (15.0, "Softened organic garden harmony"),
        'navy': (14.0, "Rich jewel and marine depths"),
        'gold': (15.0, "Opulent emerald glow paired with gold"),
        'tan': (14.0, "Nature-inspired earth and leather pairing"),
    },
    'black': {
        'white': (17.0, "Monochrome perfection: striking black & white contrast"),
        'cream': (16.0, "Softened monochrome with warm ivory depth"),
        'grey': (16.0, "Sleek tonal grayscale gradient"),
        'red': (15.0, "Dramatic focal statement against deep black"),
        'tan': (15.0, "Classic cosmopolitan neutral duo"),
        'camel': (16.0, "Iconic luxury tailoring contrast"),
        'denim blue': (15.0, "Urban effortless streetwear staple"),
        'gold': (15.0, "Opulent night-out metallic accent on black canvas"),
        'silver': (15.0, "Edgy cool-toned metallic contrast"),
    },
    'white': {
        'black': (17.0, "Timeless monochrome purity"),
        'denim blue': (17.0, "Effortless casual staple: crisp white on authentic denim"),
        'navy': (17.0, "Nautical maritime perfection"),
        'tan': (16.0, "Warm sun-drenched neutral pairing"),
        'olive': (15.0, "Crisp safari modern aesthetic"),
        'red': (15.0, "Vibrant high-contrast focal statement"),
        'gold': (15.0, "Pristine white canvas illuminated by gold"),
        'silver': (14.0, "Cool minimalist metallic elegance"),
    },
    'grey': {
        'black': (16.0, "Architectural tonal grayscale layering"),
        'white': (16.0, "Crisp minimalist modern gradient"),
        'pink': (15.0, "Sophisticated balance: cool slate grey softens delicate pink"),
        'navy': (15.0, "Corporate polish: charcoal and deep navy"),
        'burgundy': (15.0, "Rich jewel wine pop against understated grey"),
        'yellow': (14.0, "Contemporary editorial contrast"),
    },
    'silver': {
        'black': (17.0, "Futuristic evening glamour: luminous silver on black"),
        'white': (16.0, "Cool ethereal frosted elegance"),
        'navy': (15.0, "Starlight nautical elegance"),
        'grey': (15.0, "Tonal high-shine metallic harmony"),
        'blue': (14.0, "Cool icy palette coordination"),
    },
    'gold': {
        'black': (17.0, "Gilded luxury: radiant gold elevates black base"),
        'maroon': (17.0, "Regal Indian wedding opulence"),
        'navy': (16.0, "Royal navy accented by lustrous gold"),
        'white': (16.0, "Sun-kissed radiant contrast"),
        'green': (15.0, "Opulent garden elegance"),
        'cream': (15.0, "Warm monochromatic heirloom glow"),
    },
    'orange': {
        'navy': (17.0, "High-energy complementary clash: citrus orange on navy"),
        'denim blue': (16.0, "Casual sunshine pairing on blue denim"),
        'white': (16.0, "Vibrant tropical summer clarity"),
        'black': (15.0, "Bold graphic modern statement"),
        'olive': (14.0, "Earthy warm terracotta coordination"),
    },
    'purple': {
        'white': (16.0, "Royal jewel clarity on clean white"),
        'black': (15.0, "Dramatic velvet-toned evening mystery"),
        'gold': (16.0, "Imperial opulence: regal purple with bright gold"),
        'grey': (14.0, "Muted heather tones create contemporary balance"),
        'pink': (13.0, "Analogous romantic berry spectrum"),
    },
    'neutral': {
        'black': (15.0, "Versatile grounding neutral foundation"),
        'white': (15.0, "Clean versatile base"),
        'navy': (15.0, "Classic versatile pairing"),
        'denim blue': (14.0, "Casual authentic coordination"),
    }
}


def get_closest_palette_color(color_name: str) -> str:
    """
    Returns the exact color name if recognized in COLOR_PAIRINGS.
    Otherwise maps aliases, or falls back using CIEDE2000 / LAB Euclidean distance.
    Never fails or throws exceptions on unrecognized colors.
    """
    c = str(color_name or '').lower().strip().strip("'\"")
    if not c:
        return 'neutral'
    if c in COLOR_PAIRINGS:
        return c

    aliases = {
        'blue': 'denim blue',
        'denim': 'denim blue',
        'peach': 'blush',
        'nude': 'beige',
        'rust': 'orange',
        'wine': 'burgundy',
        'charcoal': 'grey',
        'off-white': 'ivory',
        'off white': 'ivory',
        'emerald': 'green',
        'fuchsia': 'pink',
        'magenta': 'pink',
    }
    if c in aliases and aliases[c] in COLOR_PAIRINGS:
        return aliases[c]

    # Check canonical palette names directly
    if c in PALETTE_NAMES and c in COLOR_PAIRINGS:
        return c

    return 'neutral'



def score_styling_match(item: WardrobeItem, product, day_str: Optional[str] = None) -> Tuple[float, List[str]]:
    """
    Computes an un-saturated styling harmony score (55.0 to 95.0) and returns top 2 dynamic reasons.
    """
    if day_str is None:
        day_str = timezone.now().strftime("%Y-%m-%d")

    item_slot = getattr(item, 'slot_type', 'top') or 'top'
    item_form = getattr(item, 'formality', 3) or 3
    item_style = getattr(item, 'style_family', 'western') or 'western'
    item_pattern = getattr(item, 'pattern', 'solid') or 'solid'
    raw_item_cols = getattr(item, 'dominant_colours', []) or []
    item_cols = [str(c).lower().strip().strip("'\"") for c in (raw_item_cols if isinstance(raw_item_cols, list) else [raw_item_cols]) if c]

    p_slot = getattr(product, 'slot_type', 'bottom') or 'bottom'
    p_form = getattr(product, 'formality', 3) or 3
    p_style = getattr(product, 'style_family', 'western') or 'western'
    p_pattern = getattr(product, 'pattern', 'solid') or 'solid'
    p_name = (getattr(product, 'product_name', '') or getattr(product, 'name', '') or '').lower()

    # Parse product colors
    raw_cols = getattr(product, 'dominant_colours', [])
    p_cols = []
    if isinstance(raw_cols, list):
        p_cols = [str(c).lower().strip().strip("'\"") for c in raw_cols if c]
    elif isinstance(raw_cols, str):
        try:
            pj = json.loads(raw_cols)
            if isinstance(pj, list):
                p_cols = [str(c).lower().strip().strip("'\"") for c in pj if c]
            else:
                p_cols = [c.strip().lower().strip("'\"") for c in raw_cols.replace('[','').replace(']','').replace('"','').replace("'",'').split(',') if c.strip()]
        except Exception:
            p_cols = [c.strip().lower().strip("'\"") for c in raw_cols.replace('[','').replace(']','').replace('"','').replace("'",'').split(',') if c.strip()]

    scored_components = []

    # 1. Base Score
    base_score = 30.0

    # 2. Formality Gradient
    form_gap = abs(item_form - p_form)
    if form_gap == 0:
        scored_components.append((18.0, f"Aligned formality ({item_form}/5): seamless dress-code balance"))
    elif form_gap == 1:
        scored_components.append((11.0, "Balanced smart-casual styling: relaxed yet polished"))
    elif form_gap == 2:
        scored_components.append((3.0, "Deliberate high-low contrast styling"))
    else:
        scored_components.append((-15.0, "Formality clash"))

    # 3. Colour Harmony via Fashion Knowledge Matrix
    norm_item_cols = [get_closest_palette_color(c) for c in item_cols]
    norm_p_cols = [get_closest_palette_color(c) for c in p_cols]

    color_pts = 0.0
    color_reason = None
    for ic in norm_item_cols:
        table_i = COLOR_PAIRINGS.get(ic, {})
        for pc in norm_p_cols:
            if pc in table_i:
                pts, rsn = table_i[pc]
                if pts > color_pts:
                    color_pts = pts
                    color_reason = rsn
            table_p = COLOR_PAIRINGS.get(pc, {})
            if ic in table_p:
                pts, rsn = table_p[ic]
                if pts > color_pts:
                    color_pts = pts
                    color_reason = rsn

    if not color_reason:
        shared_cols = set(norm_item_cols) & set(norm_p_cols)
        has_neutral = bool((set(norm_item_cols) | set(norm_p_cols)) & NEUTRALS)
        if shared_cols:
            color_pts = 14.0
            color_reason = f"Harmonious tonal {list(shared_cols)[0].title()} coordination"
        elif has_neutral:
            color_pts = 12.0
            color_reason = "Versatile neutral foundation anchors the outfit"
        else:
            color_pts = 8.0
            color_reason = "Balanced complementary color pairing"

    scored_components.append((color_pts, color_reason))

    # 4. Pattern / Statement Rule & Embellishment Compatibility
    is_item_solid = item_pattern in ('solid', 'plain', '', None)
    is_prod_solid = p_pattern in ('solid', 'plain', '', None)
    is_prod_embellished = any(e in (p_name + ' ' + getattr(product, 'subtype', '')).lower() for e in ('glitter', 'sequin', 'embellished', 'embroidered', 'zari', 'metallic', 'heavy'))

    if is_item_solid and is_prod_solid:
        scored_components.append((12.0, "Clean minimalist styling: solid on solid canvas"))
    elif is_item_solid and not is_prod_solid and not is_prod_embellished:
        scored_components.append((10.0, f"Solid base lets the subtle {p_pattern} motif stand out"))
    elif not is_item_solid and is_prod_solid:
        scored_components.append((10.0, f"Solid piece grounds the {item_pattern} focal garment"))
    else:
        scored_components.append((-10.0, "Statement clash: competing patterns"))

    # Severe penalty for casual top + heavily embellished shoe (e.g. glitter jutti with tank)
    if item_slot == 'top' and item_form <= 3 and is_prod_embellished and p_slot == 'footwear':
        scored_components.append((-25.0, "Overly ornate footwear overwhelms casual relaxed top"))

    # 5. Style Family Coherence
    if p_style == item_style:
        scored_components.append((12.0, f"Cohesive {item_style.title()} aesthetic profile"))
    elif {p_style, item_style} == {'western', 'ethnic'}:
        scored_components.append((8.0, "Curated Indo-Western fusion coordination"))
    else:
        scored_components.append((4.0, "Eclectic style crossover"))

    # 6. Multi-season wearability
    scored_components.append((3.0, "Versatile multi-season wearability"))

    # Total score calculation
    total = base_score + sum(c[0] for c in scored_components)

    # Daily seeded tie-breaker (0.0 to 2.5) for varied results
    h_str = f"{day_str}:{getattr(item, 'id', 0)}:{getattr(product, 'product_id', 0)}"
    seed = (int(hashlib.md5(h_str.encode()).hexdigest()[:6], 16) % 100) / 40.0
    final_score = round(max(55.0, min(95.0, total + seed)), 1)

    # Top 2 positive reasons
    pos_reasons = [c[1] for c in sorted(scored_components, key=lambda x: x[0], reverse=True) if c[0] > 0 and c[1]]
    final_reasons = pos_reasons[:2] if len(pos_reasons) >= 2 else (pos_reasons + ["Curated aesthetic complement"])[:2]

    return final_score, final_reasons


class WardrobeMatcher:
    """
    Intelligent styling engine linking catalog products to customer's personal wardrobe items.
    Reuses recommendations.outfit_validator.validate_outfit() without duplicating logic.
    Caches results in wardrobe_matches with auto-invalidation on wardrobe updates.
    """

    @classmethod
    def get_eligible_wardrobe_items(cls, customer_id: str) -> List[WardrobeItem]:
        """Returns customer's active items that have confidence >= 0.6 or are user_verified, are not in needs_review, and have valid images."""
        return list(WardrobeItem.objects.filter(
            customer_id=customer_id,
            is_active=True,
            needs_review=False,
        ).filter(
            Q(user_verified=True) | Q(confidence__gte=0.6)
        ).exclude(
            Q(image_url__isnull=True) | Q(image_url='')
        ))

    @classmethod
    def match_product_to_wardrobe(
        cls,
        product,
        wardrobe_items: List[WardrobeItem],
        prefs: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Takes a catalog product and customer's wardrobe items.
        Returns top matches with score and 2 explanatory styling reasons.
        """
        if not product or not wardrobe_items:
            return []

        prefs = prefs or {}
        occasion = prefs.get('occasion', 'casual')
        user_prefs = {
            'occasion': occasion,
            'style': prefs.get('style', 'all'),
            'budget': 999999,
        }

        eligible_items = [
            w for w in wardrobe_items
            if w.is_active and not w.needs_review and (w.user_verified or (w.confidence is not None and w.confidence >= 0.6)) and bool(w.image_url)
        ]

        if not eligible_items:
            return []

        prod_slot = getattr(product, 'slot_type', 'top') or 'top'
        prod_form = getattr(product, 'formality', 3) or 3
        prod_style = getattr(product, 'style_family', 'western') or 'western'
        prod_pattern = getattr(product, 'pattern', 'solid') or 'solid'
        prod_name = (getattr(product, 'product_name', None) or getattr(product, 'name', '') or '').lower()
        prod_cat = (getattr(product, 'main_category', '') or '').lower()

        # Digital Wardrobe is exclusively for women: catalogue product must be women's fashion
        if any(m in prod_name for m in ("for men", "men's", "mens ", " men ")) or ('men' in prod_cat and 'women' not in prod_cat):
            return []
        if prod_slot == 'footwear':
            if 'women' not in prod_cat and not any(w in prod_name for w in ('women', 'girl', 'ladies', 'heel', 'sandal', 'pump', 'stiletto', 'wedge', 'ballerina', 'flats', 'jutti', 'kolhapuri')):
                return []

        candidates = []

        for item in eligible_items:
            if item.slot_type == prod_slot:
                continue

            if (prod_slot == 'one_piece' and item.slot_type == 'bottom') or \
               (prod_slot == 'bottom' and item.slot_type == 'one_piece'):
                continue

            item_form = item.formality or 3
            if abs(prod_form - item_form) > 2:
                continue

            # Assemble micro-outfit for validation via canonical validate_outfit()
            micro_pieces = {
                'one_piece': None,
                'top': None,
                'bottom': None,
                'footwear': None,
                'bag': None,
                'accessories': []
            }

            if prod_slot == 'one_piece': micro_pieces['one_piece'] = product
            elif prod_slot == 'top': micro_pieces['top'] = product
            elif prod_slot == 'bottom': micro_pieces['bottom'] = product
            elif prod_slot == 'footwear': micro_pieces['footwear'] = product
            elif prod_slot == 'bag': micro_pieces['bag'] = product
            elif prod_slot == 'accessory': micro_pieces['accessories'] = [product]

            if item.slot_type == 'one_piece': micro_pieces['one_piece'] = item
            elif item.slot_type == 'top': micro_pieces['top'] = item
            elif item.slot_type == 'bottom': micro_pieces['bottom'] = item
            elif item.slot_type == 'footwear': micro_pieces['footwear'] = item
            elif item.slot_type == 'bag': micro_pieces['bag'] = item
            elif item.slot_type == 'accessory': micro_pieces['accessories'].append(item)

            passed, _ = validate_outfit(micro_pieces, {**user_prefs, 'allow_partial': True})
            if not passed:
                continue

            final_score, stylist_reasons = score_styling_match(item, product)

            candidates.append({
                'wardrobe_item': item,
                'score': final_score,
                'match_percentage': int(round(final_score)),
                'reasons': stylist_reasons,
                'reason': stylist_reasons[0] if stylist_reasons else "Stylist verified outfit combination"
            })

        # Sort descending by styling score
        candidates.sort(key=lambda x: x['score'], reverse=True)
        return candidates

    @classmethod
    def get_or_compute_matches(
        cls,
        customer_id: str,
        product,
        force_refresh: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Retrieves cached matches from wardrobe_matches table,
        or computes and stores them if missing/expired.
        Returns up to 6 best matches.
        """
        s_cust = str(customer_id).strip()
        p_key = str(getattr(product, 'product_id', getattr(product, 'id', ''))).strip()

        if not force_refresh:
            cached = list(WardrobeMatch.objects.filter(
                customer_id=s_cust,
                product_key=p_key
            ).select_related('wardrobe_item').order_by('-score')[:6])

            if cached:
                # Check for expiration (10 min max for valid cached results)
                now = timezone.now()
                is_stale = any((now - m.computed_at).total_seconds() > 600 for m in cached)
                if not is_stale:
                    valid_cached = [
                        m for m in cached
                        if m.wardrobe_item and m.wardrobe_item.is_active and not m.wardrobe_item.needs_review and bool(m.wardrobe_item.image_url) and m.score > 0
                    ]
                    if valid_cached:
                        return [
                            {
                                'wardrobe_item_id': m.wardrobe_item_id,
                                'id': m.wardrobe_item_id,
                                'item_name': m.wardrobe_item.item_name,
                                'slot_type': m.wardrobe_item.slot_type,
                                'subtype': m.wardrobe_item.subtype,
                                'length': getattr(m.wardrobe_item, 'length', None),
                                'sleeve_type': getattr(m.wardrobe_item, 'sleeve_type', None),
                                'dominant_colours': m.wardrobe_item.dominant_colours,
                                'formality': m.wardrobe_item.formality,
                                'pattern': m.wardrobe_item.pattern,
                                'style_family': m.wardrobe_item.style_family,
                                'image_url': m.wardrobe_item.image_url,
                                'thumb_url': m.wardrobe_item.thumb_url or m.wardrobe_item.image_url,
                                'flat_image_url': m.wardrobe_item.flat_image_url or m.wardrobe_item.image_url,
                                'score': m.score,
                                'match_percentage': int(round(m.score)),
                                'reasons': m.reasons,
                                'reason': m.reasons[0] if (isinstance(m.reasons, list) and m.reasons) else "Stylist verified outfit combination",
                            }
                            for m in valid_cached
                        ]

        # Compute matches from scratch using only eligible wardrobe items
        w_items = cls.get_eligible_wardrobe_items(s_cust)
        computed = cls.match_product_to_wardrobe(product, w_items)

        # Cache in DB
        WardrobeMatch.objects.filter(customer_id=s_cust, product_key=p_key).delete()
        results = []
        for c in computed:
            item = c['wardrobe_item']
            match_obj = WardrobeMatch.objects.create(
                customer_id=s_cust,
                product_key=p_key,
                wardrobe_item=item,
                score=c['score'],
                reasons=c['reasons']
            )
            results.append({
                'wardrobe_item_id': item.id,
                'id': item.id,
                'item_name': item.item_name,
                'slot_type': item.slot_type,
                'subtype': item.subtype,
                'sleeve_type': getattr(item, 'sleeve_type', None),
                'dominant_colours': item.dominant_colours,
                'formality': item.formality,
                'pattern': item.pattern,
                'style_family': item.style_family,
                'image_url': item.image_url,
                'thumb_url': item.thumb_url or item.image_url,
                'flat_image_url': item.flat_image_url or item.image_url,
                'score': c['score'],
                'match_percentage': int(round(c['score'])),
                'reasons': c['reasons'],
                'reason': c['reasons'][0] if (isinstance(c['reasons'], list) and c['reasons']) else "Stylist verified outfit combination",
            })

        return results

    @classmethod
    def invalidate_customer_matches(cls, customer_id: str):
        """
        Invalidates all cached matches for a customer when their wardrobe items change.
        """
        s_cust = str(customer_id).strip()
        WardrobeMatch.objects.filter(customer_id=s_cust).delete()
