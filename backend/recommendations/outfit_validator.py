"""
Outfit Compatibility Validator for Smart Budget Stylist.

Enforces hard compatibility gates BEFORE scoring:
  1. Max formality gap between any two pieces <= 1
  2. At most one printed/embellished piece (statement piece rule)
  3. No colour clash & at least one neutral, tonal or complementary relationship
  4. Style family compatibility (explicit allowed-pairs table)
  5. Occasion x footwear / accessory rules
  6. Slot legitimacy (no one-piece with bottoms, correct slots)
  7. Saree and lehenga rules (blouse required, no belt with saree, no duplicate dupatta, etc.)
  8. Accessory compatibility (belt only with waist/bottoms, no duplicate accessory types, metal consistency)
  9. Total price <= budget (hard cap)
"""

import json

# ==============================================================================
# EDITABLE RULE TABLES
# ==============================================================================

# Explicit color clash pairs (combinations that conflict visually)
COLOR_CLASH_PAIRS = [
    ({'maroon', 'red'}, {'green', 'olive'}),
    ({'yellow'}, {'purple'}),
    ({'orange'}, {'pink'}),
]


def are_colors_clashing(cols_a, cols_b):
    """Returns True if the union of two color sets contains any explicit color clash."""
    all_c = set(cols_a or []) | set(cols_b or [])
    for c_a, c_b in COLOR_CLASH_PAIRS:
        if (all_c & c_a) and (all_c & c_b):
            return True
    return False

NEUTRAL_COLORS = {
    'black', 'white', 'grey', 'gray', 'beige', 'cream', 'navy', 'denim', 'neutral',
    'gold', 'silver', 'metallic', 'tan', 'nude', 'taupe', 'ivory', 'camel', 'khaki',
    'charcoal', 'off-white', 'denim blue'
}

# Occasion rules for footwear and accessories
OCCASION_RULES = {
    'chic': {
        'blocked_footwear': {'flip_flop', 'slipper'},
        'allowed_footwear': {'heel', 'flat', 'sandal', 'dress_shoe', 'jutti'},
        'blocked_ethnic': set(),
        'max_saree_formality': 5,
    },
    'party': {
        'blocked_footwear': {'flip_flop', 'slipper'},
        'allowed_footwear': {'heel', 'flat', 'sandal', 'dress_shoe', 'jutti'},
        'blocked_ethnic': set(),
        'max_saree_formality': 5,
    },
    'formal': {
        'blocked_footwear': {'flip_flop', 'slipper', 'sneaker'},
        'allowed_footwear': {'heel', 'flat', 'dress_shoe', 'sandal'},
        'blocked_ethnic': set(),
        'min_formality': 3,
        'max_saree_formality': 5,
    },
    'elegant': {
        'blocked_footwear': {'flip_flop', 'slipper'},
        'allowed_footwear': {'heel', 'flat', 'sandal', 'dress_shoe', 'jutti'},
        'blocked_ethnic': set(),
        'max_saree_formality': 5,
    },
    'traditional': {
        'blocked_footwear': {'sneaker', 'sports'},
        'preferred_footwear': {'jutti', 'sandal', 'heel', 'kolhapuri', 'flat'},
        'blocked_bags': {'backpack', 'sports_bag'},
        'preferred_bags': {'potli', 'clutch', 'ethnic_sling'},
        'blocked_ethnic': set(),
        'max_saree_formality': 5,
    },
    'festive': {
        'blocked_footwear': {'sneaker', 'sports', 'flip_flop', 'slipper'},
        'preferred_footwear': {'jutti', 'sandal', 'heel', 'kolhapuri', 'flat'},
        'blocked_bags': {'backpack', 'sports_bag'},
        'preferred_bags': {'potli', 'clutch', 'ethnic_sling'},
        'blocked_ethnic': set(),
        'max_saree_formality': 5,
    },
    'casual': {
        'blocked_footwear': {'flip_flop', 'slipper'},  # slippers strictly excluded
        'allowed_footwear': {'sneaker', 'flat', 'sandal', 'other'},
        'blocked_ethnic_subtypes': {'lehenga_set', 'lehenga_skirt'},  # Lehengas never for casual
        'max_saree_formality': 3,  # Only light cotton/printed sarees (formality <= 3)
    },
    'college': {
        'blocked_footwear': {'flip_flop', 'slipper'},
        'allowed_footwear': {'sneaker', 'flat', 'sandal', 'other'},
        'blocked_ethnic_subtypes': {'lehenga_set', 'lehenga_skirt'},
        'max_saree_formality': 3,
    },
    'streetwear': {
        'blocked_footwear': {'flip_flop', 'slipper'},
        'allowed_footwear': {'sneaker', 'flat', 'other'},
        'blocked_ethnic_subtypes': {'lehenga_set', 'lehenga_skirt'},
        'max_saree_formality': 3,
    },
    'sportswear': {
        'blocked_footwear': {'flip_flop', 'slipper', 'heel', 'jutti', 'flat', 'dress_shoe'},
        'allowed_footwear': {'sneaker'},
        'blocked_ethnic_subtypes': {'lehenga_set', 'lehenga_skirt', 'saree'},
        'max_saree_formality': 0,
    },
    'activewear': {
        'blocked_footwear': {'flip_flop', 'slipper', 'heel', 'jutti', 'flat', 'dress_shoe'},
        'allowed_footwear': {'sneaker'},
        'blocked_ethnic_subtypes': {'lehenga_set', 'lehenga_skirt', 'saree'},
        'max_saree_formality': 0,
    },
    'sports': {
        'blocked_footwear': {'flip_flop', 'slipper', 'heel', 'jutti', 'flat', 'dress_shoe'},
        'allowed_footwear': {'sneaker'},
        'blocked_ethnic_subtypes': {'lehenga_set', 'lehenga_skirt', 'saree'},
        'max_saree_formality': 0,
    },
}

# Style family compatibility
ALLOWED_STYLE_PAIRS = {
    'western': {'western', 'athleisure'},
    'ethnic': {'ethnic'},
    'indo_western': {'indo_western', 'ethnic', 'western'},
    'athleisure': {'athleisure', 'western'},
}


def _get_item_attr(item, attr, default=None):
    """Safely extracts attribute from either Product model instance or dict."""
    if item is None:
        return default
    if isinstance(item, dict):
        return item.get(attr, default)
    return getattr(item, attr, default)


def _get_item_colors(item):
    """Parses dominant colors as list of lowercase strings."""
    val = _get_item_attr(item, 'dominant_colours', '[]')
    if isinstance(val, list):
        return [str(c).lower().strip().strip("'\"") for c in val if c]
    if isinstance(val, str):
        try:
            parsed = json.loads(val)
            if isinstance(parsed, list):
                return [str(c).lower().strip().strip("'\"") for c in parsed if c]
        except Exception:
            pass
        return [c.strip().lower().strip("'\"") for c in val.replace('[', '').replace(']', '').replace('"', '').replace("'", '').split(',') if c.strip()]
    return ['neutral']


def validate_outfit(pieces, user_prefs=None):
    """
    Validates a proposed outfit candidate against all strict compatibility rules.
    Runs BEFORE scoring. Discards candidate if ANY check fails.

    pieces: dict containing:
      - 'top': Topwear item or None
      - 'bottom': Bottomwear item or None
      - 'one_piece': One-piece garment (dress, jumpsuit, saree, lehenga set) or None
      - 'footwear': Shoes or None
      - 'bag': Bag or None
      - 'accessories': list of accessory items or []

    user_prefs: dict with:
      - 'budget': float
      - 'occasion': str ('casual', 'formal', 'party', 'festive', 'college', 'traditional', etc.)
      - 'style': str
      - 'preferred_color': str or None

    Returns:
      (passed: bool, reasons: list of str)
    """
    reasons = []
    prefs = user_prefs or {}
    budget = float(prefs.get('budget', 2000.0))
    occasion = str(prefs.get('occasion', 'casual')).strip().lower()

    # Collect present pieces
    top = pieces.get('top')
    bottom = pieces.get('bottom')
    one_piece = pieces.get('one_piece')
    layer = pieces.get('layer')
    footwear = pieces.get('footwear')
    bag = pieces.get('bag')
    accessories = [a for a in pieces.get('accessories', []) if a]

    all_pieces = []
    if one_piece:
        all_pieces.append(one_piece)
    if top:
        all_pieces.append(top)
    if bottom:
        all_pieces.append(bottom)
    if layer:
        all_pieces.append(layer)
    if footwear:
        all_pieces.append(footwear)
    if bag:
        all_pieces.append(bag)
    all_pieces.extend(accessories)

    # Layer rule: cannot layer over traditional saree or lehenga set
    if layer and one_piece:
        op_sub = _get_item_attr(one_piece, 'subtype', 'other')
        if op_sub in ('saree', 'lehenga_set'):
            reasons.append("Layer (jacket/blazer/cardigan) cannot be paired over traditional saree or lehenga.")
            return False, reasons

    # --------------------------------------------------------------------------
    # 0. MINIMUM TWO DISTINCT PRODUCTS FOR STYLED LOOK
    # --------------------------------------------------------------------------
    distinct_ids = set()
    for p in all_pieces:
        pid = _get_item_attr(p, 'product_id') or _get_item_attr(p, 'id')
        distinct_ids.add(str(pid) if pid else str(id(p)))
    if len(distinct_ids) < 2:
        reasons.append("Styled look must contain at least two distinct products.")
        return False, reasons

    # --------------------------------------------------------------------------
    # 1. GENDER AND JUNK VERIFICATION
    # --------------------------------------------------------------------------
    user_gender = str(prefs.get('gender', 'women')).lower()
    if 'women' in user_gender or 'female' in user_gender:
        for p in all_pieces:
            pnm = (_get_item_attr(p, 'product_name', '') or '').lower()
            if any(k in pnm for k in ["men's", "for men", "boys'", "for boys", "gents", "school shoes"]):
                if 'women' not in pnm:
                    reasons.append(f"Product '{pnm}' is designated for men/boys and cannot be in women's styling.")
                    return False, reasons

    if footwear:
        fw_nm = (_get_item_attr(footwear, 'product_name', '') or '').lower()
        fw_type = _get_item_attr(footwear, 'footwear_type', 'other')
        fw_sub = (_get_item_attr(footwear, 'sub_category', '') or '').lower()

        # Strict universal sandal, slide, and slipper exclusion
        sandal_kws = [
            'sandal', 'sandals', 'sandle', 'sandles', 'sendal', 'sendel', 'sendle',
            'slide', 'slides', 'chappal', 'chappals', 'chappl',
            'flip flop', 'flipflop', 'slipper', 'slippers', 'thong', 'toe ring'
        ]
        if (
            fw_type in ('sandal', 'flip_flop', 'slipper') or
            any(k in fw_sub for k in ['sandal', 'sandle', 'slipper', 'slide', 'chappal']) or
            any(k in fw_nm for k in sandal_kws)
        ):
            reasons.append("Sandals, slides, flip-flops, and slippers are strictly excluded from Smart Budget Stylist recommendations.")
            return False, reasons

        if any(j in fw_nm for j in [
            'heel grip', 'shoe insert', 'insole', 'shoe tree', 'shoe horn', 'cleaner', 'protector',
            'cushion pad', 'shoe repair', 'crease protector', 'sole protector', 'toe shield',
            'watch strap', 'watch band', 'leather strap', 'cobbler', 'nail', 'screw', 'fevicol', 'glue', 'all fix'
        ]):
            reasons.append("Footwear item is hardware, repair supply, or shoe accessory/insert/cleaner, not wearable footwear.")
            return False, reasons

    if bag:
        bag_nm = (_get_item_attr(bag, 'product_name', '') or '').lower()
        bag_sub = _get_item_attr(bag, 'subtype', 'handbag')
        if bag_sub == 'pouch' or any(j in bag_nm for j in [
            'makeup bag', 'makeup pouch', 'cosmetic bag', 'cosmetic pouch', 'toiletry bag', 'toiletry pouch',
            'pencil pouch', 'kit pouch', 'organizer pouch', 'jewel pouch', 'purse pouch', 'pouch for necklace',
            'claw clip', 'hair clip', 'clutcher', 'scrunchie', 'hair band', 'hairpin', 'pants chain', 'trouser',
            'pant', 'clutch back', 'earring', 'hoop', 'dress with sling bag'
        ]):
            reasons.append("Bag item is a cosmetic/travel pouch, hair accessory, or non-bag product, not a wearable bag/purse.")
            return False, reasons

    for acc in accessories:
        acc_nm = (_get_item_attr(acc, 'product_name', '') or '').lower()
        if any(j in acc_nm for j in [
            'ring sizer', 'ring tool', 'mandrel', 'ring size adjuster', 'ring adjuster for loose rings',
            'invisible ring sizer', 'stopper', 'safety pin', 'brooch pin back', 'craft', 'raw material',
            'elastic band', 'hair elastic', 'rubber band', 'bead wire', 'keychain hook', 'jewellery making',
            'hair tie', 'scrunchie', 'hair band', 'ponytail holder', 'nail', 'screw', 'fevicol', 'glue'
        ]):
            reasons.append("Accessory item is utility/craft tool/hardware, not wearable fashion jewellery.")
            return False, reasons

    # --------------------------------------------------------------------------
    # 2. CLOTHING BASE CHECK & SLOT LEGITIMACY
    # --------------------------------------------------------------------------
    has_one_piece = one_piece is not None
    has_top = top is not None
    has_bottom = bottom is not None
    allow_partial = bool(user_prefs.get('allow_partial', False) or user_prefs.get('partial', False))
    if not allow_partial and not has_one_piece and not (has_top and has_bottom):
        # Incomplete clothing base
        reasons.append("Outfit lacks a valid clothing base (must have either a one-piece or top + bottom).")
        return False, reasons

    # RULE: When styling for women, NEVER include men's products, men's shoes, or anything related to men
    gender = (user_prefs.get('gender') or '').lower()
    if gender == 'women':
        for p in all_pieces:
            p_name = (_get_item_attr(p, 'product_name', '') or '').lower()
            p_main = (_get_item_attr(p, 'main_category', '') or '').lower()
            p_sub = (_get_item_attr(p, 'sub_category', '') or '').lower()
            is_mens_category = (
                ("men's" in p_main or "men's" in p_sub or "men's fashion" in p_sub or p_main.startswith("men"))
                and "women" not in p_main and "women" not in p_sub
            )
            if is_mens_category:
                reasons.append(f"Product '{_get_item_attr(p, 'product_name')}' belongs to men's category and cannot be in a women's outfit.")
                return False, reasons
            has_women_term = any(w in p_name for w in ['women', 'woman', 'ladies', 'lady', 'girl'])
            if not has_women_term:
                has_men_term = (
                    "men's" in p_name or "mens " in p_name or " mens" in p_name or
                    "for men" in p_name or "boys'" in p_name or "for boys" in p_name or
                    "gents" in p_name or p_name.startswith("men ") or " men " in p_name or p_name.endswith(" men")
                )
                if has_men_term:
                    reasons.append(f"Product '{_get_item_attr(p, 'product_name')}' is a men's product and cannot be in a women's outfit.")
                    return False, reasons

    # RULE: Do not pair two bottom-wear products together
    bottom_pieces = [p for p in all_pieces if _get_item_attr(p, 'slot_type') == 'bottom']
    if len(bottom_pieces) > 1:
        reasons.append("An outfit cannot contain two bottom-wear products.")
        return False, reasons

    # RULE: No one-piece with a bottom
    if has_one_piece and has_bottom:
        reasons.append("One-piece garment (dress/jumpsuit/saree/lehenga) cannot be paired with bottomwear.")
        return False, reasons

    # RULE: Saree or Lehenga is NEVER paired with western bottoms, jeans, or western tops
    for c_chk in (one_piece, top, bottom):
        if not c_chk:
            continue
        sub = _get_item_attr(c_chk, 'subtype', 'other')
        nm = (_get_item_attr(c_chk, 'product_name', '') or '').lower()
        if sub in ('saree', 'lehenga_set') or 'saree' in nm or 'lehenga' in nm:
            if has_bottom and sub != 'lehenga_skirt':
                reasons.append("Saree or lehenga cannot be paired with western bottoms or jeans.")
                return False, reasons

    # RULE: One-piece garments and top pairing rules
    if has_one_piece:
        op_subtype = _get_item_attr(one_piece, 'subtype', 'other')
        if op_subtype != 'saree' and has_top:
            reasons.append("One-piece garment (dress/jumpsuit/lehenga set) cannot be paired with a separate top.")
            return False, reasons
        if op_subtype == 'saree' and has_top:
            # Saree can only be paired with an ethnic choli or blouse, never a western top!
            top_subtype = _get_item_attr(top, 'subtype', 'other')
            top_style = _get_item_attr(top, 'style_family', 'western')
            if top_subtype != 'choli' and top_style != 'ethnic':
                reasons.append("Saree can only be paired with a traditional choli/blouse, not a western top.")
                return False, reasons

    # --------------------------------------------------------------------------
    # 2. BUDGET HARD CAP (0 tolerance)
    # --------------------------------------------------------------------------
    def get_price(item):
        if not item:
            return 0.0
        p = _get_item_attr(item, 'selling_price')
        if p is None:
            p = _get_item_attr(item, 'discount_price')
        if p is None:
            p = _get_item_attr(item, 'base_price', 0.0)
        try:
            return float(p)
        except (ValueError, TypeError):
            return 0.0

    total_price = sum(get_price(p) for p in all_pieces)
    if total_price > budget:
        reasons.append(f"Total outfit price (₹{total_price:.0f}) exceeds the budget cap of ₹{budget:.0f}.")
        return False, reasons

    # --------------------------------------------------------------------------
    # 3. FORMALITY GAP <= 1 (Applies across all pieces)
    # --------------------------------------------------------------------------
    formalities = []
    for p in all_pieces:
        f = _get_item_attr(p, 'formality', 3)
        try:
            formalities.append((int(f), _get_item_attr(p, 'product_name', 'Item')))
        except (ValueError, TypeError):
            formalities.append((3, 'Item'))

    if formalities:
        min_f, min_item = min(formalities, key=lambda x: x[0])
        max_f, max_item = max(formalities, key=lambda x: x[0])
        if (max_f - min_f) > 1:
            reasons.append(
                f"Formality gap {max_f - min_f} between '{min_item}' (level {min_f}) "
                f"and '{max_item}' (level {max_f}) exceeds allowed maximum of 1."
            )
            return False, reasons

    # --------------------------------------------------------------------------
    # 4. STATEMENT PIECE RULE (At most ONE printed/embellished piece)
    # --------------------------------------------------------------------------
    statement_items = []
    for p in all_pieces:
        pat = _get_item_attr(p, 'pattern', 'solid')
        if pat in ('printed', 'embellished'):
            statement_items.append(_get_item_attr(p, 'product_name', 'Item'))

    # Heavy jewellery or bold bags also count as statement pieces
    for acc in accessories:
        a_type = _get_item_attr(acc, 'accessory_type')
        a_pat = _get_item_attr(acc, 'pattern', 'solid')
        a_name = (_get_item_attr(acc, 'product_name', '') or '').lower()
        if a_type == 'jewellery' and any(w in a_name for w in ['heavy', 'choker', 'bridal', 'necklace set', 'statement']):
            if _get_item_attr(acc, 'product_name') not in statement_items:
                statement_items.append(_get_item_attr(acc, 'product_name', 'Jewellery Set'))

    if len(statement_items) > 1:
        reasons.append(
            f"Outfit has {len(statement_items)} statement pieces ({', '.join(statement_items[:2])}); "
            f"at most 1 printed/embellished statement piece is permitted."
        )
        return False, reasons

    # --------------------------------------------------------------------------
    # 5. ETHNIC STRUCTURE RULES: SAREE & LEHENGA (Section 2B)
    # --------------------------------------------------------------------------
    clothing_items = [p for p in (one_piece, top, bottom) if p]
    for c_item in clothing_items:
        subtype = _get_item_attr(c_item, 'subtype', 'other')
        c_name = (_get_item_attr(c_item, 'product_name', '') or '').lower()

        # --- SAREE RULES ---
        if subtype == 'saree':
            # Saree must have a blouse (either included in listing or separate choli)
            includes_blouse = _get_item_attr(c_item, 'includes_blouse', False)
            if not includes_blouse and not top:
                reasons.append("Saree has no blouse option (listing does not include blouse piece and no matching choli paired).")
                return False, reasons

            # Saree: No belt and no separate dupatta
            for acc in accessories:
                a_type = _get_item_attr(acc, 'accessory_type')
                a_sub = _get_item_attr(acc, 'subtype')
                a_name = (_get_item_attr(acc, 'product_name', '') or '').lower()
                if a_type == 'belt' and 'kamarbandh' not in a_name and 'waist' not in a_name:
                    reasons.append("Saree cannot be paired with a belt (only waist jewellery/kamarbandh is allowed).")
                    return False, reasons
                if a_type == 'scarf' or a_sub == 'dupatta':
                    reasons.append("Saree already has a pallu; cannot add a separate dupatta.")
                    return False, reasons

            # Footwear for Saree: Block sneakers, sports shoes, flip flops, slippers
            if footwear:
                fw_type = _get_item_attr(footwear, 'footwear_type', 'other')
                if fw_type in ('sneaker', 'flip_flop'):
                    reasons.append(f"Saree cannot be paired with {fw_type} footwear (heels, juttis, or dress flats required).")
                    return False, reasons

            # Bag for Saree: Block backpacks, sports bags, totes
            if bag:
                bag_name = (_get_item_attr(bag, 'product_name', '') or '').lower()
                if any(w in bag_name for w in ['backpack', 'duffle', 'gym', 'sports']):
                    reasons.append("Saree cannot be paired with a backpack or sports bag (potli, clutch, or sling required).")
                    return False, reasons

            # Occasion check for Saree
            if occasion in ('casual', 'college', 'streetwear'):
                saree_formality = _get_item_attr(c_item, 'formality', 3)
                if saree_formality > 3:
                    reasons.append(f"Silk/heavy saree (formality {saree_formality}) is not permitted for {occasion.title()} setting (only casual cotton sarees allowed).")
                    return False, reasons

        # --- LEHENGA RULES ---
        if subtype in ('lehenga_set', 'lehenga_skirt'):
            # Lehenga never for Casual, College, or Streetwear!
            if occasion in ('casual', 'college', 'streetwear'):
                reasons.append(f"Lehenga is strictly blocked for {occasion.title()} setting (only allowed for Festive, Traditional, Party, Formal, Elegant).")
                return False, reasons

            # Lehenga: No belt
            for acc in accessories:
                a_type = _get_item_attr(acc, 'accessory_type')
                if a_type == 'belt':
                    reasons.append("Lehenga cannot be paired with a belt.")
                    return False, reasons

            # Lehenga set already includes dupatta: No separate dupatta
            if subtype == 'lehenga_set':
                for acc in accessories:
                    a_sub = _get_item_attr(acc, 'subtype')
                    a_acc_type = _get_item_attr(acc, 'accessory_type')
                    a_name = (_get_item_attr(acc, 'product_name', '') or '').lower()
                    if a_sub == 'dupatta' or a_acc_type == 'dupatta' or 'dupatta' in a_name:
                        reasons.append("Lehenga set already includes a dupatta; duplicate dupatta is prohibited.")
                        return False, reasons

            # Separate lehenga skirt must be paired with an ethnic top/choli
            if subtype == 'lehenga_skirt':
                if not top:
                    reasons.append("Lehenga skirt requires an ethnic top or choli.")
                    return False, reasons
                top_style = _get_item_attr(top, 'style_family', 'western')
                if top_style != 'ethnic':
                    reasons.append("Lehenga skirt cannot be paired with western top/tee.")
                    return False, reasons

            # Footwear for Lehenga: Block sneakers, sports shoes, flip flops
            if footwear:
                fw_type = _get_item_attr(footwear, 'footwear_type', 'other')
                if fw_type in ('sneaker', 'flip_flop'):
                    reasons.append(f"Lehenga cannot be paired with {fw_type} footwear.")
                    return False, reasons

            # Bag for Lehenga: Block backpacks, totes, sports bags
            if bag:
                bag_name = (_get_item_attr(bag, 'product_name', '') or '').lower()
                if any(w in bag_name for w in ['backpack', 'tote', 'gym', 'duffle']):
                    reasons.append("Lehenga cannot be paired with backpack or tote bag (clutch or potli required).")
                    return False, reasons

    # --------------------------------------------------------------------------
    # 6. OCCASION x FOOTWEAR RULES (Editable table enforcement)
    # --------------------------------------------------------------------------
    occ_rules = OCCASION_RULES.get(occasion, OCCASION_RULES.get('casual', {}))
    if footwear:
        fw_type = _get_item_attr(footwear, 'footwear_type', 'other')
        fw_sub = _get_item_attr(footwear, 'sub_category', '')
        fw_name = (_get_item_attr(footwear, 'product_name', '') or '').lower()

        # Digital wardrobe / stylist is strictly for women: block men's footwear
        fw_cat = (_get_item_attr(footwear, 'main_category', '') or '').lower()
        if any(m in fw_name for m in ("men's", "mens ", "for men", " men ")) or ('men' in fw_cat and 'women' not in fw_cat):
            reasons.append("Men's footwear is not permitted in women's styling.")
            return False, reasons

        # Slippers / flip-flops are strictly excluded from all stylist recommendations
        if fw_type in ('flip_flop', 'slipper') or fw_sub == 'Slippers' or 'slipper' in fw_name or 'flip flop' in fw_name or 'flipflop' in fw_name:
            reasons.append("Slippers and flip flops are strictly excluded from Smart Budget Stylist recommendations.")
            return False, reasons

        # Sportswear / activewear check
        has_sport = (
            occasion in ('sportswear', 'activewear', 'sports') or
            any(
                _get_item_attr(p, 'style_family') == 'athleisure' or
                'sport' in (_get_item_attr(p, 'product_name', '') or '').lower() or
                'activewear' in (_get_item_attr(p, 'product_name', '') or '').lower()
                for p in (top, bottom, one_piece) if p
            )
        )
        if has_sport and fw_type in ('heel', 'jutti', 'dress_shoe'):
            reasons.append(f"Sportswear cannot be paired with formal heels or traditional footwear ({fw_type}); pair with suitable sports shoes.")
            return False, reasons

        blocked_fw = occ_rules.get('blocked_footwear', set())
        if fw_type in blocked_fw:
            reasons.append(f"{fw_type.replace('_', ' ').title()} footwear is strictly blocked for {occasion.title()} occasion.")
            return False, reasons

        # Western outfit footwear check: Western outfits (jeans-and-top, skirts, dresses, jumpsuits)
        # MUST take heels (strictly no sneakers, sandals, or ethnic juttis)!
        is_pure_western = False
        if has_one_piece and _get_item_attr(one_piece, 'style_family') == 'western' and _get_item_attr(one_piece, 'subtype') not in ('saree', 'lehenga_set'):
            is_pure_western = True
        elif has_top and has_bottom:
            t_style = _get_item_attr(top, 'style_family', 'western')
            t_nm = (_get_item_attr(top, 'product_name', '') or '').lower()
            b_nm = (_get_item_attr(bottom, 'product_name', '') or '').lower()
            b_sub = _get_item_attr(bottom, 'subtype', 'other')
            if t_style == 'western' and not any(k in t_nm for k in ('kurta', 'kurti', 'anarkali')):
                if b_sub in ('jeans', 'skirt', 'shorts', 'trousers', 'cargo') or 'jeans' in b_nm:
                    is_pure_western = True

        if is_pure_western:
            if fw_type in ('jutti', 'sneaker') or any(k in fw_name for k in ['juti', 'jutti', 'mojari', 'rajasthani', 'kolhapuri', 'sneaker', 'trainer', 'running', 'sport', 'athletic', 'walking']):
                reasons.append("Western outfits cannot be paired with sneakers or ethnic juttis (heels required).")
                return False, reasons

    # --------------------------------------------------------------------------
    # 7. ACCESSORY COMPATIBILITY RULES
    # --------------------------------------------------------------------------
    seen_accessory_types = set()
    if bag:
        seen_accessory_types.add('bag')
    for acc in accessories:
        acc_type = _get_item_attr(acc, 'accessory_type', 'other')
        acc_nm = (_get_item_attr(acc, 'product_name', '') or '').lower()
        if acc_type in ('bag', 'watch', 'sunglasses'):
            if acc_type in seen_accessory_types:
                reasons.append(f"Duplicate accessory type ({acc_type}) is prohibited in a single outfit.")
                return False, reasons
            seen_accessory_types.add(acc_type)

        # Jewellery category deduplication: at most 1 necklace, at most 1 earrings
        if any(w in acc_nm for w in ['necklace', 'choker', 'chain', 'pendant', 'haar', 'mangalsutra']):
            if 'necklace' in seen_accessory_types:
                reasons.append("Duplicate necklace/chain is prohibited in a single outfit.")
                return False, reasons
            seen_accessory_types.add('necklace')
        elif any(w in acc_nm for w in ['earring', 'earrings', 'jhumk', 'stud', 'hoop', 'dangler', 'drop']):
            if 'earrings' in seen_accessory_types:
                reasons.append("Duplicate earrings are prohibited in a single outfit.")
                return False, reasons
            seen_accessory_types.add('earrings')

        # Belt rule: only with bottoms or jumpsuits/dresses with a waist
        if acc_type == 'belt':
            if not has_bottom and not (has_one_piece and _get_item_attr(one_piece, 'subtype') not in ('saree', 'lehenga_set')):
                reasons.append("Belt can only be paired with bottoms or fitted one-pieces.")
                return False, reasons

        # Dupatta rule: only with ethnic or Indo-Western looks
        if _get_item_attr(acc, 'subtype') == 'dupatta' or _get_item_attr(acc, 'accessory_type') == 'dupatta' or 'dupatta' in (_get_item_attr(acc, 'product_name', '') or '').lower():
            primary_style = _get_item_attr(one_piece or top, 'style_family', 'western')
            if primary_style not in ('ethnic', 'indo_western'):
                reasons.append("Dupatta can only be paired with ethnic or Indo-Western looks.")
                return False, reasons

    # Metal tone consistency: gold with gold, silver with silver when known
    known_metal_tones = set()
    for it in [bag] + accessories:
        if not it:
            continue
        m_tone = _get_item_attr(it, 'metal_tone')
        if not m_tone or m_tone == 'unknown':
            name_lower = (_get_item_attr(it, 'product_name') or '').lower()
            if any(w in name_lower for w in ['gold', 'golden', 'zari', 'kundan']):
                m_tone = 'gold'
            elif any(w in name_lower for w in ['silver', 'oxidised', 'oxidized', 'rhodium']):
                m_tone = 'silver'
        if m_tone in ('gold', 'silver'):
            known_metal_tones.add(m_tone)
    if len(known_metal_tones) > 1:
        reasons.append(f"Inconsistent metal tone ({', '.join(sorted(known_metal_tones))}) across bag and accessories hardware.")
        return False, reasons

    # --------------------------------------------------------------------------
    # 8. COLOUR CLASH & POSITIVE RELATIONSHIP RULES
    # --------------------------------------------------------------------------
    all_colors = set()
    for p in all_pieces:
        for c in _get_item_colors(p):
            if c:
                all_colors.add(c)

    # Check for direct clashes
    for set_a, set_b in COLOR_CLASH_PAIRS:
        if (all_colors & set_a) and (all_colors & set_b):
            reasons.append(
                f"Colour clash detected between {set_a} and {set_b} ({', '.join(all_colors)})."
            )
            return False, reasons

    # Check for positive relationship (at least one neutral, tonal, or harmonious pair)
    has_neutral = bool(all_colors & NEUTRAL_COLORS)
    # Tonal or monochromatic check
    is_tonal = len(all_colors - NEUTRAL_COLORS) <= 1
    if not has_neutral and not is_tonal:
        reasons.append("Outfit lacks an anchoring neutral tone or tonal relationship among pieces.")
        return False, reasons

    # --------------------------------------------------------------------------
    # 9. STYLE FAMILY COMPATIBILITY
    # --------------------------------------------------------------------------
    clothing_style = _get_item_attr(one_piece or top, 'style_family', 'western')
    allowed_styles = ALLOWED_STYLE_PAIRS.get(clothing_style, {clothing_style})

    for p in all_pieces:
        p_style = _get_item_attr(p, 'style_family', 'western')
        if p_style not in allowed_styles:
            # Indo-Western exception: ethnic tops with western bottoms
            if clothing_style in ('indo_western', 'ethnic') and p_style in ('western', 'ethnic', 'athleisure'):
                continue
            reasons.append(f"Incompatible style families: {clothing_style} clothing with {p_style} {_get_item_attr(p, 'product_name', 'piece')}.")
            return False, reasons

    return True, []
