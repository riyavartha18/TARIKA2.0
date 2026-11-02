import os
import sys
import django

# Add backend directory to path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend'))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from catalog.models import Product
from digital_wardrobe.models import WardrobeItem, WardrobeMatch, WardrobeCollection, WardrobeOutfit
from digital_wardrobe.matching import WardrobeMatcher

def seed():
    cust_id = 'U100010'
    print(f"Seeding digital wardrobe items for customer {cust_id}...")

    # Find diverse products from catalog to get high-quality images and real items
    def find_prod(slot, kw=None, sub=None):
        qs = Product.objects.filter(slot_type=slot, is_image_valid=True).exclude(image='')
        if sub:
            qs = qs.filter(subtype=sub)
        if kw:
            qs = qs.filter(product_name__icontains=kw)
        prod = qs.first()
        if not prod:
            prod = Product.objects.filter(slot_type=slot, is_image_valid=True).first()
        return prod

    items_data = [
        # 1. Tops
        {
            'name': "White Crisp Linen Shirt",
            'slot': 'top',
            'sub': 'shirt',
            'formality': 3,
            'pattern': 'solid',
            'colors': ['white'],
            'style': 'western',
            'season': 'summer',
            'kw': 'shirt',
            'review': False,
            'conf': 0.95
        },
        {
            'name': "Chikankari Embroidered Kurti",
            'slot': 'top',
            'sub': 'kurta',
            'formality': 3,
            'pattern': 'embroidered',
            'colors': ['peach', 'white'],
            'style': 'ethnic',
            'season': 'all_season',
            'kw': 'kurta',
            'review': False,
            'conf': 0.92
        },
        {
            'name': "Classic Black Ribbed Tank Top",
            'slot': 'top',
            'sub': 'tank',
            'formality': 2,
            'pattern': 'solid',
            'colors': ['black'],
            'style': 'western',
            'season': 'summer',
            'kw': 'top',
            'review': False,
            'conf': 0.94
        },
        # 2. Bottoms
        {
            'name': "High-Rise Navy Blue Denim Jeans",
            'slot': 'bottom',
            'sub': 'jeans',
            'formality': 2,
            'pattern': 'solid',
            'colors': ['navy', 'blue'],
            'style': 'western',
            'season': 'all_season',
            'kw': 'jeans',
            'review': False,
            'conf': 0.96
        },
        {
            'name': "Tailored Beige Pleated Trousers",
            'slot': 'bottom',
            'sub': 'trousers',
            'formality': 4,
            'pattern': 'solid',
            'colors': ['beige'],
            'style': 'western',
            'season': 'all_season',
            'kw': 'pant',
            'review': False,
            'conf': 0.91
        },
        {
            'name': "Flared Ivory Chanderi Palazzo",
            'slot': 'bottom',
            'sub': 'palazzo',
            'formality': 3,
            'pattern': 'solid',
            'colors': ['ivory', 'white'],
            'style': 'ethnic',
            'season': 'summer',
            'kw': 'palazzo',
            'review': False,
            'conf': 0.89
        },
        # 3. One-Pieces (Dress & Saree)
        {
            'name': "Floral Chiffon Midi Sundress",
            'slot': 'one_piece',
            'sub': 'dress',
            'formality': 3,
            'pattern': 'floral',
            'colors': ['blue', 'white'],
            'style': 'western',
            'season': 'spring_summer',
            'kw': 'dress',
            'review': False,
            'conf': 0.94
        },
        {
            'name': "Royal Kanjivaram Silk Saree",
            'slot': 'one_piece',
            'sub': 'saree',
            'formality': 5,
            'pattern': 'woven',
            'colors': ['maroon', 'gold'],
            'style': 'ethnic',
            'season': 'wedding',
            'kw': 'saree',
            'review': False,
            'conf': 0.97,
            'includes_blouse': True
        },
        # 4. Footwear
        {
            'name': "Pointed Black Stiletto Pumps",
            'slot': 'footwear',
            'sub': 'heel',
            'fw_type': 'heel',
            'formality': 4,
            'pattern': 'solid',
            'colors': ['black'],
            'style': 'western',
            'season': 'all_season',
            'kw': 'heel',
            'review': False,
            'conf': 0.95
        },
        {
            'name': "Rose Gold Embellished Juttis",
            'slot': 'footwear',
            'sub': 'jutti',
            'fw_type': 'jutti',
            'formality': 4,
            'pattern': 'embellished',
            'colors': ['gold', 'pink'],
            'style': 'ethnic',
            'season': 'all_season',
            'kw': 'juti',
            'review': False,
            'conf': 0.93
        },
        # 5. Bags
        {
            'name': "Cognac Vegan Leather Tote Bag",
            'slot': 'bag',
            'sub': 'tote',
            'formality': 3,
            'pattern': 'solid',
            'colors': ['brown', 'tan'],
            'style': 'western',
            'season': 'all_season',
            'kw': 'tote',
            'review': False,
            'conf': 0.93
        },
        {
            'name': "Golden Zari Embroidered Potli Bag",
            'slot': 'bag',
            'sub': 'potli',
            'formality': 5,
            'pattern': 'embroidered',
            'colors': ['gold'],
            'style': 'ethnic',
            'season': 'wedding',
            'kw': 'potli',
            'review': False,
            'conf': 0.92
        },
        # 6. Accessories
        {
            'name': "Layered Pearl Pendant Necklace",
            'slot': 'accessory',
            'sub': 'jewelry',
            'acc_type': 'necklace',
            'metal': 'gold',
            'formality': 4,
            'pattern': 'solid',
            'colors': ['gold', 'white'],
            'style': 'western',
            'season': 'all_season',
            'kw': 'necklace',
            'review': False,
            'conf': 0.95
        },
        # 7. Needs Review Item (Unverified item with low confidence)
        {
            'name': "Oversized Vintage Jacket",
            'slot': 'top',
            'sub': 'outerwear',
            'formality': 2,
            'pattern': 'abstract',
            'colors': ['olive'],
            'style': 'western',
            'season': 'winter',
            'kw': 'jacket',
            'review': True,
            'conf': 0.52,
            'retake_prompt': "Item boundary was partially obstructed. Please confirm the category tags."
        }
    ]

    created_items = []
    for d in items_data:
        p = find_prod(d['slot'], d.get('kw'), d.get('sub'))
        img_url = p.image if p and p.image else "https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?w=600"
        
        # Check if item with this name already exists for customer
        item = WardrobeItem.objects.filter(customer_id=cust_id, item_name=d['name']).first()
        if not item:
            item = WardrobeItem.objects.create(
                customer_id=cust_id,
                item_name=d['name'],
                category=d['slot'].capitalize(),
                slot_type=d['slot'],
                subtype=d['sub'],
                formality=d['formality'],
                pattern=d['pattern'],
                dominant_colours=d['colors'],
                style_family=d['style'],
                season=d['season'],
                footwear_type=d.get('fw_type'),
                accessory_type=d.get('acc_type'),
                metal_tone=d.get('metal'),
                includes_blouse=d.get('includes_blouse', False),
                confidence=d['conf'],
                needs_review=d['review'],
                user_verified=not d['review'],
                is_active=True,
                source='upload',
                image_url=img_url,
                flat_image_url=img_url,
                thumb_url=img_url,
                retake_prompt=d.get('retake_prompt', '')
            )
            print(f"Created: [{item.slot_type}] {item.item_name} (ID: {item.id})")
        else:
            item.image_url = img_url
            item.flat_image_url = img_url
            item.thumb_url = img_url
            item.confidence = d['conf']
            item.needs_review = d['review']
            item.user_verified = not d['review']
            item.save()
            print(f"Updated: [{item.slot_type}] {item.item_name} (ID: {item.id})")
        created_items.append(item)

    # Pre-compute some matches for sample products
    sample_prods = Product.objects.filter(is_image_valid=True, slot_type__isnull=False)[:5]
    print(f"Pre-computing wardrobe matches against {sample_prods.count()} store products...")
    for sp in sample_prods:
        matches = WardrobeMatcher.get_or_compute_matches(cust_id, sp)
        if matches:
            print(f"Product '{sp.product_name[:30]}' matched with {len(matches)} wardrobe pieces!")

    print(f"SUCCESS: Seeded {len(created_items)} items for customer {cust_id}!")

if __name__ == '__main__':
    seed()
