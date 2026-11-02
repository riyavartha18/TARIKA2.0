import re
import json
import urllib.request
from io import BytesIO
from PIL import Image

# Standard color palette definitions with representative RGB values
COLOR_RGB_MAP = {
    'black': (25, 25, 25),
    'white': (245, 245, 245),
    'grey': (128, 128, 128),
    'beige': (220, 205, 180),
    'cream': (250, 245, 225),
    'pink': (235, 120, 150),
    'maroon': (130, 20, 40),
    'red': (210, 30, 30),
    'navy': (20, 40, 90),
    'blue': (50, 120, 210),
    'green': (40, 130, 70),
    'olive': (110, 120, 40),
    'yellow': (240, 200, 30),
    'mustard': (210, 160, 20),
    'purple': (120, 50, 170),
    'brown': (110, 70, 45),
    'orange': (230, 110, 30),
    'gold': (212, 175, 55),
    'silver': (192, 192, 192),
    'teal': (30, 130, 130),
    'peach': (255, 190, 160),
}

COLOR_SYNONYMS = {
    'black': ['black', 'noir', 'charcoal', 'jet black', 'dark black'],
    'white': ['white', 'ivory', 'off-white', 'snow'],
    'grey': ['grey', 'gray', 'ash', 'silver grey', 'slate'],
    'beige': ['beige', 'nude', 'tan', 'camel', 'khaki'],
    'cream': ['cream', 'off white', 'ecru'],
    'pink': ['pink', 'rose', 'blush', 'magenta', 'fuchsia', 'salmon', 'rani', 'baby pink'],
    'maroon': ['maroon', 'burgundy', 'wine', 'crimson'],
    'red': ['red', 'scarlet', 'ruby', 'vermilion'],
    'navy': ['navy', 'navy blue', 'midnight blue', 'dark blue'],
    'blue': ['blue', 'azure', 'sky blue', 'cobalt', 'royal blue', 'denim blue', 'cyan'],
    'green': ['green', 'emerald', 'mint', 'sage', 'bottle green', 'pista'],
    'olive': ['olive', 'mehendi', 'mehndi', 'military green'],
    'yellow': ['yellow', 'lemon', 'haldi', 'mango yellow'],
    'mustard': ['mustard', 'ochre'],
    'purple': ['purple', 'violet', 'lavender', 'plum', 'lilac'],
    'brown': ['brown', 'chocolate', 'coffee', 'mocha', 'tan brown'],
    'orange': ['orange', 'rust', 'coral', 'tangerine'],
    'gold': ['gold', 'golden', 'zari gold'],
    'silver': ['silver', 'metallic silver'],
    'teal': ['teal', 'peacock'],
    'peach': ['peach'],
}

INNERWEAR_OR_JUNK = [
    'bra', 'panty', 'panties', 'brief', 'briefs', 'shapewear', 'petticoat',
    'boyshorts', 'camisole', 'innerwear', 'nightwear', 'nightdress', 'nighty',
    'pajama set', 'boxer', 'underwear', 'cancan', 'fall pico', 'saree fall',
    'blouse pad', 'nipple cover', '#name?',
    # Footwear inserts, cleaners & utility hardware
    'heel grip', 'heel grips', 'heel pad', 'heel pads', 'insole', 'insoles',
    'shoe insert', 'shoe inserts', 'crep protect', 'shoe cleaner', 'whitener',
    'shoe horn', 'toe shield', 'toe shields', 'cushion pad', 'orthotic insole',
    'cobbler nail', 'cobbler nails', 'shoe repair', 'shoe tree', 'shoe trees',
    'crease protector', 'crease protectors', 'sole protector', 'sole protectors',
    'shoe stretcher', 'shoe shaper', 'fevicol', 'all fix', 'fevikwik',
    # Craft hardware, earring backs, stoppers, tools
    'stopper bead', 'stopper beads', 'earring back', 'earring backs',
    'ear lifter', 'ear lifters', 'safety pin', 'safety pins', 'screw back', 'pech',
    'ring sizer', 'ring sizers', 'ring mandrel', 'ring size adjuster',
    'ring adjuster for loose rings', 'invisible ring sizer', 'ring tool'
]


def extract_colors_from_text(text):
    """Finds all matching normalized color names in the text."""
    if not text:
        return []
    text_lower = text.lower()
    matched = []
    for base_color, synonyms in COLOR_SYNONYMS.items():
        for syn in synonyms:
            # Word boundary match to avoid substring errors (e.g., 'red' in 'shred')
            if re.search(r'\b' + re.escape(syn) + r'\b', text_lower):
                if base_color not in matched:
                    matched.append(base_color)
                break
    return matched


def rgb_to_closest_color(r, g, b):
    """Finds closest color in the palette using Euclidean distance in RGB space."""
    # Check for near black or near white first
    brightness = 0.299 * r + 0.587 * g + 0.114 * b
    if brightness < 40:
        return 'black'
    if brightness > 235 and max(r, g, b) - min(r, g, b) < 25:
        return 'white'
    if max(r, g, b) - min(r, g, b) < 18:
        return 'grey'

    min_dist = float('inf')
    closest = 'neutral'
    for c_name, (cr, cg, cb) in COLOR_RGB_MAP.items():
        dist = (r - cr) ** 2 + (g - cg) ** 2 + (b - cb) ** 2
        if dist < min_dist:
            min_dist = dist
            closest = c_name
    return closest


def sample_image_dominant_color(image_url, timeout=2.5):
    """Downloads first few KB of image, resizes to 1x1, and returns closest color."""
    if not image_url or not isinstance(image_url, str) or not image_url.startswith('http'):
        return None
    try:
        req = urllib.request.Request(
            image_url,
            headers={'User-Agent': 'Mozilla/5.0'}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
            img = Image.open(BytesIO(data)).convert('RGB')
            # Resize to 1x1 to average the pixels
            img = img.resize((1, 1), Image.Resampling.BOX)
            r, g, b = img.getpixel((0, 0))
            return rgb_to_closest_color(r, g, b)
    except Exception:
        return None


def classify_product(product_name, main_category, sub_category, image_url=None, sample_image=False):
    """
    Classifies a product into all required attributes with high precision.
    Returns a dict with:
      slot_type, formality, pattern, dominant_colours, style_family,
      season, footwear_type, accessory_type, subtype, includes_blouse,
      includes_dupatta, confidence, hidden, mismatch_reason
    """
    name = (product_name or '').strip()
    name_lower = name.lower()
    main_lower = (main_category or '').strip().lower()
    sub_lower = (sub_category or '').strip().lower()
    full_text = f"{name_lower} {main_lower} {sub_lower}"

    # 1. Check for Junk or Innerwear
    if not name or len(name) < 3 or '#name?' in name_lower:
        return {
            'slot_type': None,
            'formality': 1,
            'pattern': 'solid',
            'dominant_colours': json.dumps([]),
            'style_family': 'western',
            'season': 'all',
            'footwear_type': None,
            'accessory_type': None,
            'subtype': 'other',
            'includes_blouse': False,
            'includes_dupatta': False,
            'metal_tone': 'unknown',
            'confidence': 0.0,
            'hidden': True,
            'mismatch_reason': 'Unusable title or #NAME? artifact'
        }

    for junk in INNERWEAR_OR_JUNK:
        if re.search(r'\b' + re.escape(junk) + r'\b', name_lower):
            return {
                'slot_type': 'other',
                'formality': 1,
                'pattern': 'solid',
                'dominant_colours': json.dumps([]),
                'style_family': 'western',
                'season': 'all',
                'footwear_type': None,
                'accessory_type': None,
                'subtype': 'other',
                'includes_blouse': False,
                'includes_dupatta': False,
                'metal_tone': 'unknown',
                'confidence': 0.2,
                'hidden': True,
                'mismatch_reason': f'Innerwear / intimates keyword: {junk}'
            }

    # 2. Check garment roles and exceptions
    is_wallet = bool(re.search(r'\b(wallet|wallets|card holder|card case|money clip|passport holder)\b', name_lower))
    is_saree_accessory = bool(re.search(r'\b(pin|brooch|tassel|latkan|fall|safety pin|pico)\b', name_lower))
    is_saree_blouse = bool(re.search(r'\b(saree blouse|blouse for saree|choli|readymade blouse|saree for blouse)\b', name_lower))
    is_top_garment = not is_wallet and bool(re.search(r'\b(crop top|top|blouse|shirt|t-shirt|tee|choli|tunic|kurti|kurta|peplum|hoodie|sweatshirt|coat|jacket|blazer|shrug|cardigan)\b', name_lower))
    is_bottom_garment = bool(re.search(r'\b(jeans|pant|pants|trouser|trousers|palazzo|skirt|leggings|jeggings|shorts|churidar|salwar)\b', name_lower))
    is_hair_accessory = bool(re.search(r'\b(hair clip|hair clips|claw clip|claw clips|hair claw|clutcher|clutchers|hairband|scrunchie|hair pin|hair tie|hair band|ponytail holder)\b', name_lower))
    is_pants_chain = bool(re.search(r'\b(pants chain|jeans chain|jean chain|wallet chain)\b', name_lower))
    is_earring_clutch = bool(re.search(r'\b(clutch back|earring|earrings|hoop|bali|stud|jhumka)\b', name_lower))
    is_watch_item = bool(re.search(r'\b(watch strap|watch band|leather strap|wrist watch|smartwatch)\b', name_lower))
    is_jewellery_item = bool(re.search(r'\b(chain|necklace|earring|earrings|anklet|payal|bangle|bangles|bracelet|choker|pendant|mangalsutra|nose pin|ring|jewellery|jewelry)\b', name_lower))
    is_coat_or_jacket = bool(re.search(r'\b(coat|jacket|blazer|cardigan|shrug|trench|sweater)\b', name_lower))

    # 3. Classify Slot Type & Subtype
    slot_type = None
    subtype = 'other'
    footwear_type = None
    accessory_type = None
    includes_blouse = False
    includes_dupatta = False
    confidence = 0.90
    mismatch_reason = None

    # --- WATCH ACCESSORY (intercept before footwear so "watch strap with flat finish" != footwear) ---
    if is_watch_item:
        slot_type = 'accessory'
        accessory_type = 'watch'
        subtype = 'other'

    # --- JEWELLERY ACCESSORY (intercept before footwear so "flat designer chain" != footwear) ---
    elif is_jewellery_item and ('shoe' not in main_lower and 'footwear' not in main_lower):
        slot_type = 'accessory'
        if any(w in name_lower for w in ['earring', 'earrings', 'hoop', 'bali', 'stud', 'jhumka']):
            accessory_type = 'earrings'
        elif any(w in name_lower for w in ['necklace', 'choker', 'pendant', 'chain', 'mangalsutra']):
            accessory_type = 'necklace'
        elif any(w in name_lower for w in ['bangle', 'bangles', 'bracelet', 'kada']):
            accessory_type = 'bangle'
        elif any(w in name_lower for w in ['anklet', 'payal']):
            accessory_type = 'anklet'
        else:
            accessory_type = 'other'

    # --- FOOTWEAR ---
    elif not is_watch_item and not is_jewellery_item and ('shoe' in main_lower or 'footwear' in main_lower or any(w in name_lower for w in [
        'heel', 'heels', 'stiletto', 'pumps', 'wedge', 'wedges', 'sandal', 'sandals',
        'sneaker', 'sneakers', 'flat', 'flats', 'ballerina', 'loafers', 'loafer',
        'jutti', 'juttis', 'mojari', 'kolhapuri', 'flip flop', 'flip-flop', 'slipper', 'slippers',
        'mules', 'crocs', 'boots', 'derby', 'oxford', 'chappal'
    ])):
        slot_type = 'footwear'
        if any(w in name_lower for w in ['heel', 'heels', 'stiletto', 'pumps', 'wedge', 'wedges']):
            footwear_type = 'heel'
        elif any(w in name_lower for w in ['jutti', 'juttis', 'mojari', 'kolhapuri', 'nagra']):
            footwear_type = 'jutti'
        elif any(w in name_lower for w in ['sneaker', 'sneakers', 'running', 'trainer', 'sports shoes', 'canvas']):
            footwear_type = 'sneaker'
        elif any(w in name_lower for w in ['flip flop', 'flip-flop', 'flipflop', 'slipper', 'slippers', 'slide', 'slides', 'chappal', 'crocs', 'thong']):
            footwear_type = 'flip_flop'
        elif any(w in name_lower for w in ['derby', 'oxford', 'brogue', 'monk strap', 'dress shoe']):
            footwear_type = 'dress_shoe'
        elif any(w in name_lower for w in ['sandal', 'sandals', 'gladiator', 'strappy']):
            footwear_type = 'sandal'
        elif any(w in name_lower for w in ['flat', 'flats', 'ballerina', 'ballet', 'loafer', 'loafers', 'moccasin']):
            footwear_type = 'flat'
        else:
            footwear_type = 'other'

    # --- HAIR ACCESSORY (explicitly intercept before Bag to prevent "hair clutch" -> Bag) ---
    elif is_hair_accessory:
        slot_type = 'accessory'
        accessory_type = 'hair'
        subtype = 'hair_accessory'

    # --- PANTS CHAIN / WALLET CHAIN (intercept before Bag) ---
    elif is_pants_chain:
        slot_type = 'accessory'
        accessory_type = 'belt'
        subtype = 'other'

    # --- BAG ---
    elif (
        not is_top_garment and not is_bottom_garment and not is_coat_or_jacket and not is_earring_clutch and not is_hair_accessory and not is_jewellery_item and (
            bool(re.search(r'\b(handbag|handbags|tote|totes|sling\s+bag|sling\s+bags|potli|potlis|shoulder\s+bag|shoulder\s+bags|satchel|satchels|duffle\s+bag|duffle\s+bags|crossbody|backpack|backpacks|clutch|clutches)\b', name_lower)) or
            bool(re.search(r'\b(purse|purses|pouch|pouches|makeup\s+bag|cosmetic\s+bag|toiletry\s+bag)\b', name_lower)) or
            ('bag' in sub_lower and 'jewel' not in name_lower and 'clothing' not in main_lower)
        )
    ):
        slot_type = 'bag'
        if any(w in name_lower for w in ['makeup', 'cosmetic', 'toiletry', 'pouch', 'pencil bag', 'coin pouch']):
            subtype = 'pouch'
            accessory_type = 'pouch'
        elif any(w in name_lower for w in ['tote', 'totes']):
            subtype = 'tote'
            accessory_type = 'bag'
        elif any(w in name_lower for w in ['clutch', 'clutches', 'potli', 'potlis', 'batwa']):
            subtype = 'clutch'
            accessory_type = 'bag'
        elif any(w in name_lower for w in ['sling', 'crossbody']):
            subtype = 'sling'
            accessory_type = 'bag'
        elif any(w in name_lower for w in ['shoulder bag', 'satchel']):
            subtype = 'shoulder'
            accessory_type = 'bag'
        elif any(w in name_lower for w in ['backpack', 'backpacks']):
            subtype = 'backpack'
            accessory_type = 'bag'
        else:
            subtype = 'handbag'
            accessory_type = 'bag'

    # --- CHOLI / READYMADE BLOUSE / TOP (explicitly intercept before Saree!) ---
    elif is_top_garment and any(w in name_lower for w in ['saree', 'sari', 'blouse', 'choli', 'crop top']):
        slot_type = 'top'
        subtype = 'choli'

    # --- ACCESSORY ---
    elif 'accessories' in main_lower or 'jewellery' in sub_lower or 'jewelry' in sub_lower or any(w in name_lower for w in [
        'necklace', 'earring', 'earrings', 'bangle', 'bangles', 'bracelet', 'ring',
        'choker', 'pendant', 'jhumka', 'jewellery', 'jewelry', 'kamarbandh', 'anklet',
        'watch', 'belt', 'sunglass', 'sunglasses', 'stole', 'shawl'
    ]) or is_saree_accessory:
        slot_type = 'accessory'
        if any(w in name_lower for w in ['watch', 'smartwatch']):
            accessory_type = 'watch'
        elif any(w in name_lower for w in ['belt', 'waist belt']):
            accessory_type = 'belt'
        elif any(w in name_lower for w in ['sunglass', 'sunglasses', 'goggles', 'shades']):
            accessory_type = 'sunglasses'
        elif any(w in name_lower for w in ['dupatta', 'stole', 'scarf', 'shawl', 'chunni']):
            accessory_type = 'scarf'
            subtype = 'dupatta'
        else:
            accessory_type = 'jewellery'

    # --- SAREE (ONE PIECE) (Only genuine sarees, NOT tops/crop tops!) ---
    elif ('saree' in name_lower or 'sari' in name_lower) and not is_top_garment and not is_saree_accessory:
        slot_type = 'one_piece'
        subtype = 'saree'
        # Check blouse piece
        if any(w in name_lower for w in ['with blouse', 'blouse piece', 'unstitched blouse', 'running blouse', 'attached blouse', 'incl blouse', '+ blouse']):
            includes_blouse = True
        elif 'without blouse' in name_lower:
            includes_blouse = False
        else:
            includes_blouse = True

    # --- LEHENGA SET OR SEPARATE ---
    elif 'lehenga' in name_lower or 'ghagra' in name_lower or 'chaniya choli' in name_lower:
        if any(w in name_lower for w in ['lehenga choli', 'lehenga set', 'ghagra choli', 'with dupatta', 'semi-stitched lehenga', 'chaniya choli']):
            slot_type = 'one_piece'
            subtype = 'lehenga_set'
            includes_dupatta = True
            includes_blouse = True
        elif any(w in name_lower for w in ['skirt', 'umbrella cut', 'bottom', 'flared skirt']):
            slot_type = 'bottom'
            subtype = 'lehenga_skirt'
        else:
            slot_type = 'one_piece'
            subtype = 'lehenga_set'
            includes_dupatta = True
            includes_blouse = True

    # --- CHOLI / READYMADE BLOUSE (TOP) ---
    elif is_saree_blouse or 'choli' in name_lower:
        slot_type = 'top'
        subtype = 'choli'

    # --- DRESS / JUMPSUIT / ROMPER / ONE PIECE ---
    elif any(w in name_lower for w in [
        'jumpsuit', 'romper', 'dungaree', 'playsuit', 'dress', 'gown', 'maxi', 'midi dress',
        'anarkali suit', 'salwar suit', 'kurta set', 'kurti set', 'pant set', 'co-ord', 'coord set',
        'suit set'
    ]):
        slot_type = 'one_piece'
        if 'kurta set' in name_lower or 'kurti set' in name_lower or 'suit set' in name_lower:
            subtype = 'kurta'
            if 'dupatta' in name_lower or '3 piece' in name_lower or '3pc' in name_lower:
                includes_dupatta = True
        else:
            subtype = 'other'

    # --- BOTTOMS ---
    elif any(w in name_lower for w in [
        'jean', 'jeans', 'trouser', 'trousers', 'pant', 'pants', 'chino', 'chinos',
        'shorts', 'skirt', 'palazzo', 'sharara', 'garara', 'legging', 'leggings', 'jeggings',
        'salwar', 'churidar', 'dhoti', 'joggers', 'cargo', 'trackpant'
    ]):
        slot_type = 'bottom'
        if any(w in name_lower for w in ['palazzo', 'sharara', 'garara']):
            subtype = 'palazzo'
        elif any(w in name_lower for w in ['legging', 'leggings']):
            subtype = 'other'

    # --- TOPS ---
    elif any(w in name_lower for w in [
        'shirt', 't-shirt', 'tee', 'top', 'crop top', 'blouse', 'kurti', 'kurta',
        'jacket', 'hoodie', 'sweatshirt', 'shrug', 'blazer', 'tunic', 'peplum', 'polo'
    ]):
        slot_type = 'top'
        if 'kurta' in name_lower or 'kurti' in name_lower:
            subtype = 'kurta'

    # Fallback to category hints if slot not found
    if not slot_type:
        if 'shoe' in main_lower:
            slot_type = 'footwear'
            footwear_type = 'other'
        elif 'bag' in main_lower or 'handbag' in sub_lower:
            slot_type = 'bag'
            accessory_type = 'bag'
        elif 'jewel' in sub_lower or 'accessori' in main_lower:
            slot_type = 'accessory'
            accessory_type = 'jewellery'
        elif 'bottom' in sub_lower:
            slot_type = 'bottom'
        elif 'top' in sub_lower or 'shirt' in sub_lower:
            slot_type = 'top'
        else:
            slot_type = None
            confidence = 0.4

    # 4. RULE-BASED MISMATCH CHECK (e.g. title says "leggings" but listed in Tops)
    bottom_kws = ['legging', 'leggings', 'jeans', 'trouser', 'trousers', 'pant', 'pants', 'palazzo', 'skirt']
    top_kws = ['shirt', 't-shirt', 'top', 'crop top', 'blouse', 'kurti', 'kurta', 'tee']

    is_bottom_title = any(re.search(r'\b' + re.escape(w) + r'\b', name_lower) for w in bottom_kws)
    is_top_title = any(re.search(r'\b' + re.escape(w) + r'\b', name_lower) for w in top_kws)

    if is_bottom_title and ('top' in sub_lower or 'shirt' in sub_lower or 'tee' in sub_lower) and not is_top_title:
        mismatch_reason = f"Title contains bottomwear keyword ({name_lower[:30]}) but categorized as Top"
        confidence = 0.35
    elif is_top_title and ('bottom' in sub_lower or 'trouser' in sub_lower or 'pant' in sub_lower) and not is_bottom_title:
        mismatch_reason = f"Title contains topwear keyword ({name_lower[:30]}) but categorized as Bottom"
        confidence = 0.35

    # 5. Formality (1 - 5)
    # Default 3 (smart casual)
    formality = 3
    if subtype in ['lehenga_set', 'lehenga_skirt']:
        formality = 5 if any(w in name_lower for w in ['bridal', 'heavy', 'zari', 'sequin', 'embroidered', 'wedding']) else 4
    elif subtype == 'saree':
        if any(w in name_lower for w in ['cotton', 'casual', 'daily wear', 'linen', 'mulmul']):
            formality = 3
        elif any(w in name_lower for w in ['silk', 'banarasi', 'kanjivaram', 'party', 'wedding', 'heavy', 'zari', 'chiffon', 'georgette']):
            formality = 4
        else:
            formality = 4
    elif footwear_type == 'flip_flop':
        formality = 1
    elif footwear_type == 'heel':
        formality = 4
    elif footwear_type == 'dress_shoe':
        formality = 4
    elif footwear_type == 'sneaker':
        formality = 2
    elif any(w in name_lower for w in ['lounge', 'night', 'pajama', 'tracksuit', 'track pant', 'rubber slide']):
        formality = 1
    elif any(w in name_lower for w in ['tee', 't-shirt', 'basic top', 'casual shorts', 'denim shorts']):
        formality = 2
    elif any(w in name_lower for w in ['blazer', 'trousers', 'formal', 'cocktail', 'evening', 'party dress', 'sequin', 'gown']):
        formality = 4
    elif any(w in name_lower for w in ['bridal', 'gala', 'tuxedo']):
        formality = 5

    # 6. Pattern (solid / printed / embellished)
    if any(w in name_lower for w in [
        'sequin', 'embroidered', 'embroidery', 'zari', 'embellished', 'beaded', 'mirror work',
        'gota patti', 'chikankari', 'handwork', 'brocade', 'metallic'
    ]):
        pattern = 'embellished'
    elif any(w in name_lower for w in [
        'print', 'printed', 'floral', 'bandhani', 'batik', 'stripe', 'striped', 'polka',
        'geometric', 'tie dye', 'leheriya', 'ajrakh', 'block print', 'graphic', 'check', 'checks'
    ]):
        pattern = 'printed'
    else:
        pattern = 'solid'

    # 7. Style Family (western / ethnic / indo_western / athleisure)
    if any(w in full_text for w in [
        'saree', 'sari', 'lehenga', 'kurta', 'kurti', 'anarkali', 'palazzo', 'salwar', 'churidar',
        'ethnic', 'traditional', 'choli', 'dupatta', 'potli', 'jutti', 'kolhapuri', 'bandhani', 'banarasi'
    ]):
        style_family = 'ethnic'
    elif any(w in full_text for w in ['indo-western', 'fusion', 'ethnic crop top', 'dhoti pant']):
        style_family = 'indo_western'
    elif any(w in full_text for w in ['hoodie', 'tracksuit', 'jogger', 'joggers', 'sweatshirt', 'activewear', 'gym', 'sports shoes']):
        style_family = 'athleisure'
    else:
        style_family = 'western'

    # 8. Season (summer / all / winter)
    if any(w in name_lower for w in ['cotton', 'linen', 'sleeveless', 'shorts', 'summer']):
        season = 'summer'
    elif any(w in name_lower for w in ['wool', 'woollen', 'sweater', 'jacket', 'coat', 'hoodie', 'cardigan', 'boots', 'thermal', 'fleece', 'winter']):
        season = 'winter'
    else:
        season = 'all'

    # 9. Dominant Colours
    text_colors = extract_colors_from_text(name_lower)
    if sample_image and image_url:
        img_color = sample_image_dominant_color(image_url)
        if img_color and img_color not in text_colors:
            text_colors.append(img_color)

    if not text_colors:
        text_colors = ['neutral']

    # 10. Metal Tone (gold / silver / other / unknown)
    metal_tone = 'unknown'
    if slot_type in ('accessory', 'bag', 'footwear') or any(w in full_text for w in ['jewellery', 'jewelry', 'earring', 'necklace', 'bangle', 'bracelet', 'watch', 'buckle', 'chain', 'potli', 'clutch']):
        if any(w in full_text for w in ['gold', 'golden', 'rose gold', 'zari', 'kundan', 'brass', 'gilded']):
            metal_tone = 'gold'
        elif any(w in full_text for w in ['silver', 'oxidised', 'oxidized', 'platinum', 'rhodium', 'steel']):
            metal_tone = 'silver'
        elif any(w in full_text for w in ['gunmetal', 'bronze', 'copper']):
            metal_tone = 'other'

    # Final confidence calculation
    if mismatch_reason:
        hidden = True
        confidence = 0.35
    elif not slot_type:
        hidden = True
        confidence = 0.0
    elif len(name) < 5:
        hidden = True
        confidence = 0.4
    else:
        hidden = False
        confidence = 0.95

    return {
        'slot_type': slot_type,
        'formality': formality,
        'pattern': pattern,
        'dominant_colours': json.dumps(text_colors),
        'style_family': style_family,
        'season': season,
        'footwear_type': footwear_type,
        'accessory_type': accessory_type,
        'subtype': subtype,
        'includes_blouse': includes_blouse,
        'includes_dupatta': includes_dupatta,
        'metal_tone': metal_tone,
        'confidence': confidence,
        'hidden': hidden,
        'mismatch_reason': mismatch_reason
    }
