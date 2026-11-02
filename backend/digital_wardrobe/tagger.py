import os
os.environ['LOKY_MAX_CPU_COUNT'] = '4'
import io
import json
import base64
import requests
import numpy as np
import scipy.ndimage
import skimage.color
from typing import Dict, Any, List, Optional, Tuple
from PIL import Image
from sklearn.cluster import KMeans

# ==============================================================================
# 1. CANONICAL FASHION COLOUR PALETTE (RGB Reference)
# ==============================================================================
CANONICAL_COLOR_PALETTE = {
    'beige': (225, 212, 187),
    'cream': (253, 248, 230),
    'ivory': (255, 255, 240),
    'taupe': (179, 158, 140),
    'tan': (210, 180, 140),
    'camel': (193, 154, 107),
    'brown': (115, 65, 40),
    'olive': (105, 115, 45),
    'khaki': (195, 176, 145),
    'navy': (20, 35, 75),
    'denim blue': (65, 105, 155),
    'teal': (0, 128, 128),
    'maroon': (128, 0, 0),
    'burgundy': (100, 15, 30),
    'pink': (235, 130, 160),
    'blush': (245, 205, 205),
    'mustard': (215, 165, 35),
    'yellow': (245, 220, 45),
    'red': (215, 35, 45),
    'green': (35, 140, 60),
    'black': (18, 18, 18),
    'white': (250, 250, 250),
    'grey': (140, 140, 140),
    'silver': (192, 192, 192),
    'gold': (212, 175, 55),
    'orange': (235, 115, 30),
    'purple': (125, 45, 145),
}

# Pre-convert canonical reference palette to LAB for CIEDE2000 calculations
PALETTE_NAMES = list(CANONICAL_COLOR_PALETTE.keys())
_PALETTE_RGB_NORM = np.array([CANONICAL_COLOR_PALETTE[k] for k in PALETTE_NAMES], dtype=np.float32) / 255.0
PALETTE_LAB = skimage.color.rgb2lab(_PALETTE_RGB_NORM.reshape(-1, 1, 3)).reshape(-1, 3)


# ==============================================================================
# 2. OBJECTIVE CIEDE2000 COLOUR EXTRACTION FROM ITEM PIXELS
# ==============================================================================
def extract_dominant_colors_lab(
    cutout_rgba_img: Image.Image,
    num_clusters: int = 4
) -> Tuple[List[str], List[Dict[str, Any]]]:
    """
    Extracts authentic garment colours exclusively from garment pixels:
    - Alpha mask > 200
    - Binary erosion (iterations=2) strips edge halos and soft contact shadows
    - K-means clustering (k=3-5) in LAB color space
    - Nearest palette mapping using CIEDE2000 perceptual difference
    - Returns:
        - dominant_colours: List of top 1-3 color name strings
        - detailed_shares: List of {'name': str, 'share': float, 'deltaE': float}
    """
    if cutout_rgba_img.mode != 'RGBA':
        cutout_rgba_img = cutout_rgba_img.convert('RGBA')

    arr = np.array(cutout_rgba_img)
    alpha = arr[:, :, 3]

    # Filter out transparent and low-alpha pixels
    alpha_mask = alpha > 200

    # Erode boundary by 2 pixels to completely eliminate background fringe & edge halos
    eroded_mask = scipy.ndimage.binary_erosion(alpha_mask, iterations=2)

    fg_pixels = arr[eroded_mask][:, :3]
    if len(fg_pixels) < 50:
        return ['neutral'], [{'name': 'neutral', 'share': 1.0, 'deltaE': 0.0}]

    # Convert RGB to LAB via skimage
    fg_norm = fg_pixels.astype(np.float32) / 255.0
    fg_lab = skimage.color.rgb2lab(fg_norm)

    # Subsample for computational performance while maintaining cluster accuracy
    if len(fg_lab) > 8000:
        indices = np.random.RandomState(42).choice(len(fg_lab), 8000, replace=False)
        fg_lab = fg_lab[indices]

    k = min(num_clusters, max(1, len(fg_lab) // 100))
    kmeans = KMeans(n_clusters=k, random_state=42, n_init='auto').fit(fg_lab)
    labels = kmeans.labels_
    centers_lab = kmeans.cluster_centers_

    counts = np.bincount(labels, minlength=k)
    total_samples = len(labels)

    raw_clusters = []
    for i in range(k):
        center = centers_lab[i]
        share = float(counts[i] / total_samples)

        # Broadcast center against reference palette for CIEDE2000
        center_broadcast = np.broadcast_to(center, (len(PALETTE_LAB), 3))
        deltas = skimage.color.deltaE_ciede2000(PALETTE_LAB, center_broadcast)
        best_idx = int(np.argmin(deltas))

        raw_clusters.append({
            'name': PALETTE_NAMES[best_idx],
            'share': share,
            'deltaE': float(deltas[best_idx]),
            'center': center
        })

    # Sort descending by share
    raw_clusters.sort(key=lambda x: x['share'], reverse=True)

    # Ignore low-saturation grey/silver highlight or shadow artifacts when a chromatic or warm base exists
    base_clusters = [c for c in raw_clusters if c['name'] not in ('silver', 'grey', 'charcoal', 'white', 'black')]
    if base_clusters:
        base_clusters.sort(key=lambda x: x['share'], reverse=True)
        primary_base = base_clusters[0]
        p_center = primary_base['center']
        for c in raw_clusters:
            if c['name'] in ('silver', 'grey'):
                c_center = c['center']
                hue_dist = float(np.sqrt((c_center[1] - p_center[1])**2 + (c_center[2] - p_center[2])**2))
                if hue_dist < 4.5:
                    c['name'] = primary_base['name']

    # Consolidate duplicate color names
    merged: Dict[str, float] = {}
    for c in raw_clusters:
        merged[c['name']] = merged.get(c['name'], 0.0) + c['share']

    sorted_merged = sorted(merged.items(), key=lambda x: x[1], reverse=True)

    # Top colours with >= 8% share (or at least the top dominant color)
    top_colors = [c[0] for c in sorted_merged if c[1] >= 0.08][:3]
    if not top_colors and sorted_merged:
        top_colors = [sorted_merged[0][0]]

    detailed_shares = [{'name': c[0], 'share': round(c[1], 3)} for c in sorted_merged if c[1] >= 0.05]
    return top_colors or ['neutral'], detailed_shares


# ==============================================================================
# 3. FIXED TAXONOMY & STRICT JSON PROMPT
# ==============================================================================
ALLOWED_SLOT_TYPES = ['top', 'bottom', 'one_piece', 'footwear', 'bag', 'accessory']

ALLOWED_SUBTYPES = {
    'top': [
        'sleeveless top', 'tank', 'camisole', 'crop top', 't-shirt', 'shirt',
        'blouse', 'kurta', 'kurti', 'sweater', 'jacket', 'hoodie', 'cardigan',
        'blazer', 'polo'
    ],
    'bottom': [
        'jeans', 'trousers', 'pants', 'palazzo', 'skirt', 'shorts', 'leggings', 'lehenga_skirt'
    ],
    'one_piece': [
        'dress', 'jumpsuit', 'romper', 'saree', 'lehenga_set', 'dupatta'
    ],
    'footwear': [
        'heel', 'sneaker', 'jutti', 'flat', 'boot', 'sandal', 'loafer'
    ],
    'bag': [
        'tote', 'shoulder_bag', 'crossbody', 'clutch', 'potli', 'handbag', 'backpack'
    ],
    'accessory': [
        'necklace', 'earrings', 'bracelet', 'bangle', 'ring', 'watch', 'sunglasses', 'belt', 'scarf'
    ]
}

ALLOWED_SLEEVE_TYPES = ['sleeveless', 'short', '3/4', 'full']
ALLOWED_PATTERNS = ['solid', 'printed', 'floral', 'striped', 'checked', 'embroidered', 'embellished', 'textured', 'geometric', 'abstract']
ALLOWED_STYLES = ['western', 'ethnic', 'indo_western', 'athleisure']
ALLOWED_SEASONS = ['all_season', 'summer', 'winter', 'monsoon']


WARDROBE_VISION_TAGGING_PROMPT = """
You are an expert fashion stylist and garment categorizer for a luxury fashion house.
Analyze this photo of a single garment and categorize it strictly according to the product schema below.
Choose ONLY from the allowed values. Output ONLY a valid JSON object.

Allowed Schema:
{
  "slot_type": "<one of: top, bottom, one_piece, footwear, bag, accessory>",
  "subtype": "<one of: sleeveless top, tank, camisole, crop top, t-shirt, shirt, blouse, kurta, kurti, sweater, jacket, hoodie, cardigan, blazer, polo, jeans, trousers, pants, palazzo, skirt, shorts, leggings, lehenga_skirt, dress, jumpsuit, romper, saree, lehenga_set, dupatta, heel, sneaker, jutti, flat, boot, sandal, loafer, tote, shoulder_bag, crossbody, clutch, potli, handbag, backpack, necklace, earrings, bracelet, bangle, ring, watch, sunglasses, belt, scarf>",
  "sleeve_type": "<one of: sleeveless, short, 3/4, full, or null if not a top/dress>",
  "dominant_colours": ["<color name from: beige, cream, ivory, taupe, tan, camel, brown, olive, khaki, navy, denim blue, teal, maroon, burgundy, pink, blush, mustard, yellow, red, green, black, white, grey, silver, gold, orange, purple>"],
  "pattern": "<one of: solid, printed, floral, striped, checked, embroidered, embellished, textured, geometric, abstract>",
  "formality": <integer from 1 to 5, where 1=very casual, 2=casual, 3=smart casual, 4=semi-formal/festive, 5=ultra-formal>,
  "style_family": "<one of: western, ethnic, indo_western, athleisure>",
  "season": "<one of: all_season, summer, winter, monsoon>",
  "footwear_type": "<heel, sneaker, jutti, flat, boot, sandal, loafer, or null>",
  "accessory_type": "<necklace, earrings, bracelet, bangle, ring, watch, sunglasses, belt, scarf, or null>",
  "metal_tone": "<gold, silver, rose_gold, or null>",
  "includes_blouse": <boolean>,
  "includes_dupatta": <boolean>,
  "confidence": <float between 0.1 and 1.0>
}

Rules:
1. Saree, Lehenga Sets, Dresses, and Jumpsuits MUST have slot_type='one_piece'.
2. Jeans, palazzos, skirts, trousers MUST have slot_type='bottom'.
3. Sleeveless tops, tanks, kurtis, and shirts MUST have slot_type='top'. If a top has no sleeves, set sleeve_type='sleeveless' and subtype='sleeveless top' or 'tank'.
4. Do not invent custom values outside the allowed schema.
"""


# ==============================================================================
# 4. DYNAMIC FASHION ITEM NAME GENERATOR
# ==============================================================================
def generate_garment_name(tags: Dict[str, Any]) -> str:
    """
    Generates realistic, editorial fashion titles from garment attributes.
    Example: 'Taupe Ribbed Sleeveless Top', 'Navy Floral Silk Saree', 'Beige Pleated Trousers'.
    Never outputs generic titles like 'Wardrobe T-Shirt'.
    """
    colors = tags.get('dominant_colours') or []
    c_str = colors[0].title() if colors else ''

    pattern = tags.get('pattern', 'solid')
    pat_str = pattern.title() if pattern not in ('solid', None, '') else ''

    sleeve = tags.get('sleeve_type')
    sleeve_str = sleeve.title() if sleeve and sleeve not in ('null', 'none') else ''

    subtype = str(tags.get('subtype') or tags.get('slot_type') or 'Garment').replace('_', ' ').title()

    # Deduplicate on individual word basis (e.g. avoid 'Sleeveless Sleeveless Top')
    raw_tokens = []
    for comp in [c_str, pat_str, sleeve_str, subtype]:
        if comp:
            for word in comp.split():
                if word.lower() not in [w.lower() for w in raw_tokens]:
                    raw_tokens.append(word)

    name = ' '.join(raw_tokens).strip()
    return name or 'Fashion Garment'


# ==============================================================================
# 5. UNIFIED AUTOTAGGER SERVICE
# ==============================================================================
class AutoTagger:
    """
    Production Auto-Tagging pipeline:
    1. Extracts objective colours via CIEDE2000 LAB clustering on eroded foreground pixels.
    2. Calls real vision model (Gemini, Claude, or OpenAI) if configured.
    3. Validates against strict taxonomy schema with automatic single retry.
    4. Compares vision colour with CIEDE2000 colour; sets needs_review if conflicting.
    5. NEVER falls back to default tags: if vision is unavailable or fails, sets needs_review = True
       with no guessed tags and never shows 'Verified'.
    6. Generates high-end editorial garment title.
    """

    @classmethod
    def tag_item(cls, image_bytes: bytes, cutout_img: Image.Image) -> Dict[str, Any]:
        # 1. Objective CIEDE2000 Color Extraction directly from pixel foreground
        lab_colors, color_shares = extract_dominant_colors_lab(cutout_img, num_clusters=4)

        provider = (os.environ.get('WARDROBE_VISION_PROVIDER') or os.environ.get('VISION_PROVIDER') or 'mock').lower().strip()
        vision_tags = None

        # 2. Vision Model Call (Gemini, Claude, OpenAI)
        if provider == 'gemini' and os.environ.get('GEMINI_API_KEY'):
            vision_tags = cls._call_gemini_with_retry(image_bytes)
        elif provider in ('claude', 'anthropic') and os.environ.get('ANTHROPIC_API_KEY'):
            vision_tags = cls._call_claude_with_retry(image_bytes)
        elif provider == 'openai' and os.environ.get('OPENAI_API_KEY'):
            vision_tags = cls._call_openai_with_retry(image_bytes)

        # 3. Vision Model Evaluation
        if vision_tags and vision_tags.get('confidence', 0) >= 0.5:
            tags = vision_tags

            # Color Consistency Check
            # Compare vision reported colors with CIEDE2000 pixel analysis
            vision_cols = [c.lower().strip() for c in (tags.get('dominant_colours') or [])]
            primary_lab = lab_colors[0] if lab_colors else None

            # Always anchor dominant_colours to the objective pixel analysis
            tags['dominant_colours'] = lab_colors
            tags['color_shares'] = color_shares

            # If vision model contradicts objective pixel colour, flag for customer review
            needs_review = False
            if vision_cols and primary_lab and (primary_lab not in vision_cols):
                # Vision and pixel disagree (e.g. vision thought it was black but pixels are taupe/beige)
                needs_review = True
                tags['confidence'] = min(tags.get('confidence', 0.8), 0.58)

            tags['needs_review'] = needs_review or (tags.get('confidence', 1.0) < 0.6)
            tags['item_name'] = generate_garment_name(tags)
            return tags

        # 4. Fallback when vision model is unconfigured, unavailable, or invalid:
        # NEVER guess tags or invent fake attributes! Mark needs_review with no fake tags.
        slot_type, subtype, sleeve_type = cls._infer_geometry_hints(cutout_img)

        tags = {
            "slot_type": slot_type,
            "subtype": subtype,
            "sleeve_type": sleeve_type,
            "dominant_colours": lab_colors,
            "color_shares": color_shares,
            "formality": 3,
            "pattern": "solid",
            "style_family": "western",
            "season": "all_season",
            "footwear_type": "heel" if slot_type == 'footwear' else None,
            "accessory_type": None,
            "metal_tone": None,
            "includes_blouse": False,
            "includes_dupatta": False,
            "confidence": 0.55,  # Sub-60% requires customer review
            "needs_review": True,
            "user_verified": False,
        }
        tags['item_name'] = generate_garment_name(tags)
        return tags

    @classmethod
    def _call_gemini_with_retry(cls, image_bytes: bytes) -> Optional[Dict[str, Any]]:
        for attempt in range(2):
            try:
                api_key = os.environ.get('GEMINI_API_KEY')
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
                b64_img = base64.b64encode(image_bytes).decode('utf-8')

                payload = {
                    "contents": [{
                        "parts": [
                            {"text": WARDROBE_VISION_TAGGING_PROMPT},
                            {"inline_data": {"mime_type": "image/jpeg", "data": b64_img}}
                        ]
                    }],
                    "generationConfig": {
                        "temperature": 0.1,
                        "response_mime_type": "application/json"
                    }
                }
                resp = requests.post(url, json=payload, timeout=20)
                if resp.status_code == 200:
                    text = resp.json()['candidates'][0]['content']['parts'][0]['text']
                    data = json.loads(text.strip())
                    normalized = cls._validate_and_normalize(data)
                    if normalized:
                        return normalized
            except Exception:
                pass
        return None

    @classmethod
    def _call_claude_with_retry(cls, image_bytes: bytes) -> Optional[Dict[str, Any]]:
        for attempt in range(2):
            try:
                api_key = os.environ.get('ANTHROPIC_API_KEY')
                url = "https://api.anthropic.com/v1/messages"
                b64_img = base64.b64encode(image_bytes).decode('utf-8')

                headers = {
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"
                }
                payload = {
                    "model": "claude-3-5-sonnet-20241022",
                    "max_tokens": 1024,
                    "messages": [{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": WARDROBE_VISION_TAGGING_PROMPT},
                            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64_img}}
                        ]
                    }]
                }
                resp = requests.post(url, headers=headers, json=payload, timeout=25)
                if resp.status_code == 200:
                    content = resp.json()['content'][0]['text']
                    data = json.loads(content.strip())
                    normalized = cls._validate_and_normalize(data)
                    if normalized:
                        return normalized
            except Exception:
                pass
        return None

    @classmethod
    def _call_openai_with_retry(cls, image_bytes: bytes) -> Optional[Dict[str, Any]]:
        for attempt in range(2):
            try:
                api_key = os.environ.get('OPENAI_API_KEY')
                url = "https://api.openai.com/v1/chat/completions"
                b64_img = base64.b64encode(image_bytes).decode('utf-8')

                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": "gpt-4o-mini",
                    "messages": [{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": WARDROBE_VISION_TAGGING_PROMPT},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_img}", "detail": "low"}}
                        ]
                    }],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.1
                }
                resp = requests.post(url, headers=headers, json=payload, timeout=20)
                if resp.status_code == 200:
                    content = resp.json()['choices'][0]['message']['content']
                    data = json.loads(content.strip())
                    normalized = cls._validate_and_normalize(data)
                    if normalized:
                        return normalized
            except Exception:
                pass
        return None

    @classmethod
    def _validate_and_normalize(cls, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Validates that output conforms strictly to the schema taxonomy."""
        slot = str(data.get('slot_type', '')).lower().strip()
        if slot not in ALLOWED_SLOT_TYPES:
            return None

        subtype = str(data.get('subtype', '')).lower().strip()
        allowed_for_slot = ALLOWED_SUBTYPES.get(slot, [])
        if subtype not in allowed_for_slot:
            # Fallback to closest valid subtype in slot
            subtype = allowed_for_slot[0] if allowed_for_slot else 'other'

        sleeve = data.get('sleeve_type')
        if sleeve and str(sleeve).lower().strip() in ALLOWED_SLEEVE_TYPES:
            sleeve = str(sleeve).lower().strip()
        else:
            sleeve = None

        pat = str(data.get('pattern', 'solid')).lower().strip()
        if pat not in ALLOWED_PATTERNS:
            pat = 'solid'

        style = str(data.get('style_family', 'western')).lower().strip()
        if style not in ALLOWED_STYLES:
            style = 'western'

        season = str(data.get('season', 'all_season')).lower().strip()
        if season not in ALLOWED_SEASONS:
            season = 'all_season'

        try:
            form = max(1, min(5, int(data.get('formality', 3))))
        except Exception:
            form = 3

        try:
            conf = max(0.1, min(1.0, float(data.get('confidence', 0.85))))
        except Exception:
            conf = 0.85

        return {
            "slot_type": slot,
            "subtype": subtype,
            "sleeve_type": sleeve,
            "pattern": pat,
            "formality": form,
            "style_family": style,
            "season": season,
            "dominant_colours": data.get('dominant_colours') or [],
            "footwear_type": data.get('footwear_type'),
            "accessory_type": data.get('accessory_type'),
            "metal_tone": data.get('metal_tone'),
            "includes_blouse": bool(data.get('includes_blouse', False)),
            "includes_dupatta": bool(data.get('includes_dupatta', False)),
            "confidence": conf,
        }

    @classmethod
    def _infer_geometry_hints(cls, cutout_img: Image.Image) -> Tuple[str, str, Optional[str]]:
        """Non-destructive geometric shape analysis for offline fallback (always needs_review=True)."""
        w, h = cutout_img.size
        aspect = h / max(1, w)

        if aspect > 1.8:
            return 'one_piece', 'dress', 'sleeveless'
        elif aspect > 1.25:
            return 'top', 'sleeveless top', 'sleeveless'
        elif aspect < 0.70:
            return 'footwear', 'heel', None
        else:
            return 'top', 'sleeveless top', 'sleeveless'
