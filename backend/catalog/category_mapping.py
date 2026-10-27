"""
Transparent, maintainable category mapping logic for TARIKA.

Maps editorial fashion categories to actual database queries on `public.products`.
Preserves raw database categories (`women's clothing`, `men's clothing`, etc.)
while enabling curated, high-end editorial collections requested by the storefront:

Women's Fashion:
  - The Dress Story ("Dresses for every you.")
  - Top Stories ("Tops that speak you.")
  - Bottom Line ("Foundations for your looks.")
  - Denim Diaries ("Denim for every mood.")
  - The Layer Room ("Layers that complete the look.")
  - Shirt Theory ("Shirts for new perspectives.")
  - Ethnic Edit ("Tradition, reimagined.")

Men's Fashion:
  - The Gentleman’s Edit ("Classic never goes out of style.")
  - The Shirt Society ("Every detail makes the look.")
  - Denim District ("Made for your kind of cool.")
  - Sole Stories ("Every step, your signature.")

Accessories:
  - The Accessory Edit ("It’s the little things that make the look.")
  - The Finishing Touch ("Details that do more.")
  - Carry the Look ("Little details. Big statements.")
"""
from django.db.models import Q

def normalize_cat_key(val):
    if not val:
        return ''
    return str(val).strip().lower().replace('’', "'")


# =========================================================================
# 1. WOMEN'S FASHION EDITORIAL FILTERS
# =========================================================================
WOMEN_BASE = (
    Q(main_category__iexact="women's clothing") |
    (Q(main_category__iexact="stores") & Q(sub_category__icontains="Women"))
)

# The Dress Story — "Dresses for every you."
DRESS_FILTER = WOMEN_BASE & (
    Q(product_name__iregex=r'\y(dress|dresses|gown|gowns|frock|frocks|maxi|midi|jumpsuit|jumpsuits)\y') |
    Q(sub_category__icontains='dress')
)

# Top Stories — "Tops that speak you."
TOPS_FILTER = WOMEN_BASE & (
    (
        Q(product_name__iregex=r'\y(top|tops|blouse|blouses|crop top|tank top|camisole|cami|tunic|tunics)\y') |
        Q(sub_category__icontains='top')
    ) &
    ~Q(product_name__iregex=r'\y(dress|dresses|gown|gowns|skirt|trouser|pant|jean|jeans|jacket|coat)\y')
)

# Bottom Line — "Foundations for your looks."
BOTTOM_FILTER = WOMEN_BASE & (
    (
        Q(product_name__iregex=r'\y(trouser|trousers|pant|pants|palazzo|palazzos|skirt|skirts|legging|leggings|jeggings|shorts|capris|culottes)\y') |
        Q(sub_category__icontains='bottom')
    ) &
    ~Q(product_name__iregex=r'\y(jean|jeans|denim|dress|top|shirt)\y')
)

# Denim Diaries — "Denim for every mood."
DENIM_WOMEN_FILTER = WOMEN_BASE & (
    Q(product_name__iregex=r'\y(jean|jeans|denim|jeggings)\y') |
    (Q(sub_category__icontains='jean') & Q(product_name__iregex=r'\y(jean|jeans|denim|jeggings)\y'))
)

# The Layer Room — "Layers that complete the look."
LAYERS_FILTER = WOMEN_BASE & (
    Q(product_name__iregex=r'\y(jacket|jackets|blazer|blazers|coat|coats|shrug|shrugs|cardigan|cardigans|sweater|sweaters|sweatshirt|sweatshirts|hoodie|hoodies)\y') |
    Q(sub_category__icontains='jacket')
)

# Shirt Theory — "Shirts for new perspectives."
SHIRTS_WOMEN_FILTER = WOMEN_BASE & (
    (
        Q(product_name__iregex=r'\y(shirt|shirts|button down|button-down)\y') |
        Q(sub_category__icontains='shirt')
    ) &
    ~Q(product_name__iregex=r'\y(t-shirt|t\s*shirt|tshirt|tee)\y')
)

# Ethnic Edit — "Tradition, reimagined."
ETHNIC_FILTER = WOMEN_BASE & (
    Q(product_name__iregex=r'\y(kurti|kurtis|kurta|kurtas|saree|sarees|sari|saris|lehenga|lehengas|anarkali|ethnic|dupatta|dupattas|salwar|churidar)\y') |
    Q(sub_category__iregex=r'\y(ethnic|kurti|saree)\y')
)

KURTIS_FILTER = WOMEN_BASE & Q(product_name__iregex=r'\y(kurti|kurtis|kurta|kurtas)\y')
SAREES_FILTER = WOMEN_BASE & Q(product_name__iregex=r'\y(saree|sarees|sari|saris)\y')
ETHNIC_WEAR_SUB_FILTER = WOMEN_BASE & (
    Q(product_name__iregex=r'\y(lehenga|lehengas|anarkali|ethnic|dupatta|dupattas|salwar|churidar)\y') |
    Q(sub_category__icontains='ethnic')
)


# =========================================================================
# 2. MEN'S FASHION EDITORIAL FILTERS
# =========================================================================
MEN_BASE = (
    Q(main_category__iexact="men's clothing") |
    (Q(main_category__iexact="stores") & Q(sub_category__icontains="Men"))
)

# The Gentleman’s Edit — "Classic never goes out of style."
GENTLEMAN_FILTER = (
    MEN_BASE & (
        Q(product_name__iregex=r'\y(blazer|blazers|suit|suits|tuxedo|tuxedos|trouser|trousers|formal pant|formal pants|waistcoat|waistcoats|cufflink|cufflinks|necktie|neckties|bow tie)\y') |
        (Q(product_name__iregex=r'\y(tie|ties)\y') & ~Q(product_name__iregex=r'\ytie[\s-]dye\y')) |
        Q(sub_category__icontains='formal')
    )
) & ~Q(product_name__iregex=r'\y(t-shirt|tee|tshirt|track pant|hoodie|sweatshirt)\y')

# The Shirt Society — "Every detail makes the look."
# Excludes T-shirts and polos that were inaccurately tagged or contain 'shirt'
MEN_SHIRTS_FILTER = MEN_BASE & (
    (
        Q(sub_category__iexact="Shirts") |
        Q(product_name__iregex=r'\y(shirt|shirts)\y')
    ) &
    ~Q(product_name__iregex=r'\y(t-shirt|t\s*shirt|tshirt|tee|polo)\y') &
    ~Q(sub_category__icontains="t-shirt")
)

# Denim District — "Made for your kind of cool."
# Requires actual denim/jeans and excludes mismatched shirts/trousers/caps in the Jeans subcategory
MEN_DENIM_FILTER = MEN_BASE & (
    Q(product_name__iregex=r'\y(jean|jeans|denim)\y') &
    ~Q(product_name__iregex=r'\y(t-shirt|t\s*shirt|tshirt|tee|polo|track pant|cap|caps|hat|hats|jacket|jackets)\y')
)

# Sole Stories — "Every step, your signature." (Strictly Men's Footwear)
MEN_FOOTWEAR_FILTER = (
    Q(main_category__iexact="men's shoes") |
    (
        (Q(main_category__iexact="men's clothing") | (Q(main_category__iexact="stores") & Q(sub_category__icontains="Men"))) &
        Q(product_name__iregex=r'\y(shoe|shoes|sneaker|sneakers|loafer|loafers|sandal|sandals|boot|boots|formal shoe|oxford|derby|slip-on|moccasin)\y')
    )
) & ~Q(product_name__iregex=r'\y(women|woman|women\'s|ladies|girl|girls|heel|heels)\y')

# Women's Footwear — (Fashion Sandals, Heels, Flats, Wedges, Boots)
WOMEN_FOOTWEAR_FILTER = (
    Q(main_category__iexact="women's shoes") |
    (
        (Q(main_category__iexact="women's clothing") | (Q(main_category__iexact="stores") & Q(sub_category__icontains="Women"))) &
        Q(product_name__iregex=r'\y(shoe|shoes|sneaker|sneakers|sandal|sandals|heel|heels|flat|flats|boot|boots|wedge|wedges|pump|pumps|ballerina|kolhapuri)\y')
    )
) & ~Q(product_name__iregex=r'\y(men|men\'s|boys)\y')


# =========================================================================
# 3. ACCESSORIES EDITORIAL FILTERS
# =========================================================================
ACCESSORIES_BASE = Q(main_category__iexact="accessories")

# The Accessory Edit — "It’s the little things that make the look." (Fine Jewellery)
JEWELLERY_FILTER = (
    ACCESSORIES_BASE |
    Q(product_name__iregex=r'\y(jewellery|jewelry|necklace|necklaces|earring|earrings|ring|rings|bracelet|bracelets|bangle|bangles|pendant|pendants|choker|anklet)\y') |
    Q(sub_category__icontains='jewellery')
) & ~Q(product_name__iregex=r'\y(bag|bags|handbag|backpack|wallet|shoe|shoes|watch|watches|belt|sunglasses)\y')

# The Finishing Touch — "Details that do more." (Accents, Watches, Belts, Eyewear)
FINISHING_TOUCH_FILTER = (
    Q(product_name__iregex=r'\y(watch|watches|belt|belts|sunglasses|scarf|scarves|hat|hats|cap|caps|hairband|cufflink|cufflinks|brooch|brooches|stole|muffler)\y')
) & ~Q(product_name__iregex=r'\y(bag|bags|handbag|backpack|wallet)\y')

# Carry the Look — "Little details. Big statements." (Bags, Wallets & Clutches)
BAGS_FILTER = Q(
    product_name__iregex=r'\y(bag|bags|handbag|handbags|backpack|backpacks|clutch|clutches|tote|totes|wallet|wallets|purse|purses|sling bag|duffle)\y'
)


# =========================================================================
# MASTER MAPPING TABLE
# =========================================================================
EDITORIAL_FILTER_MAP = {
    # Women's Fashion
    'the dress story': DRESS_FILTER,
    'dresses': DRESS_FILTER,
    'top stories': TOPS_FILTER,
    'tops': TOPS_FILTER,
    'bottom line': BOTTOM_FILTER,
    'bottom wear': BOTTOM_FILTER,
    'bottoms': BOTTOM_FILTER,
    'denim diaries': DENIM_WOMEN_FILTER,
    'the layer room': LAYERS_FILTER,
    'jackets': LAYERS_FILTER,
    'shirt theory': SHIRTS_WOMEN_FILTER,
    'shirts': SHIRTS_WOMEN_FILTER,
    'ethnic edit': ETHNIC_FILTER,
    'kurtis': KURTIS_FILTER,
    'sarees': SAREES_FILTER,
    'ethnic wear': ETHNIC_WEAR_SUB_FILTER,
    'sole studio': WOMEN_FOOTWEAR_FILTER,
    "women's footwear": WOMEN_FOOTWEAR_FILTER,
    'women footwear': WOMEN_FOOTWEAR_FILTER,
    "women's shoes": WOMEN_FOOTWEAR_FILTER,

    # Men's Fashion
    "the gentleman's edit": GENTLEMAN_FILTER,
    'the gentleman’s edit': GENTLEMAN_FILTER,
    'the shirt society': MEN_SHIRTS_FILTER,
    'men-shirts': MEN_SHIRTS_FILTER,
    'denim district': MEN_DENIM_FILTER,
    'men-jeans': MEN_DENIM_FILTER,
    'jeans': DENIM_WOMEN_FILTER,
    'sole stories': MEN_FOOTWEAR_FILTER,
    'men footwear': MEN_FOOTWEAR_FILTER,
    "men's footwear": MEN_FOOTWEAR_FILTER,
    "men's shoes": MEN_FOOTWEAR_FILTER,

    # Accessories
    'the accessory edit': JEWELLERY_FILTER,
    'the finishing touch': FINISHING_TOUCH_FILTER,
    'carry the look': BAGS_FILTER,
    'handbags': BAGS_FILTER,
    'footwear': WOMEN_FOOTWEAR_FILTER, # In accessories multi-card, Footwear maps to women's shoes
}


def get_editorial_filter(category_name):
    """
    Returns a Q object if `category_name` matches an editorial category key,
    or None if it should fall back to standard database column matching.
    """
    if not category_name:
        return None
    key = normalize_cat_key(category_name)
    return EDITORIAL_FILTER_MAP.get(key, None)
