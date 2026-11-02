import json
from typing import Dict, Any, List
from django.db import transaction
from django.db.models import Q
from orders.models import Order
from catalog.models import Product
from .models import WardrobeItem


class OrderHistoryImporter:
    """
    Idempotent order-history auto-import service.
    Imports delivered, non-returned customer orders directly into wardrobe_items
    by copying the product's catalog attributes and image without needing vision calls.
    """

    @classmethod
    def import_customer_orders(cls, customer_id: str) -> Dict[str, Any]:
        s_cust = str(customer_id).strip()
        if not s_cust:
            return {"success": False, "error": "Invalid customer_id", "imported_count": 0}

        # Filter delivered orders; exclude returned / cancelled
        orders_qs = Order.objects.filter(
            Q(customer__customer_id=s_cust) | Q(customer_id=s_cust),
            delivery_status__iexact='delivered'
        ).exclude(
            delivery_status__iexact='returned'
        ).select_related('product')

        imported = []
        skipped = []

        with transaction.atomic():
            for o in orders_qs:
                prod = o.product
                if not prod:
                    continue

                p_key = str(prod.product_id).strip()

                # Idempotency check: don't duplicate if already imported
                existing = WardrobeItem.objects.filter(
                    customer_id=s_cust,
                    product_key=p_key,
                    source='order_import',
                    is_active=True
                ).first()

                if existing:
                    skipped.append(p_key)
                    continue

                # Parse dominant colors from product
                raw_cols = getattr(prod, 'dominant_colours', '[]') or '[]'
                if isinstance(raw_cols, list):
                    parsed_cols = [str(c).lower().strip() for c in raw_cols if c]
                elif isinstance(raw_cols, str):
                    try:
                        p_list = json.loads(raw_cols)
                        if isinstance(p_list, list):
                            parsed_cols = [str(c).lower().strip() for c in p_list if c]
                        else:
                            parsed_cols = [c.strip().lower() for c in raw_cols.replace('[', '').replace(']', '').replace('"', '').split(',') if c.strip()]
                    except Exception:
                        parsed_cols = [c.strip().lower() for c in raw_cols.replace('[', '').replace(']', '').replace('"', '').split(',') if c.strip()]
                else:
                    parsed_cols = []

                slot = getattr(prod, 'slot_type', 'top') or 'top'
                subtype = getattr(prod, 'subtype', 'other') or 'other'
                form = getattr(prod, 'formality', 3) or 3
                pat = getattr(prod, 'pattern', 'solid') or 'solid'
                style = getattr(prod, 'style_family', 'western') or 'western'
                season = getattr(prod, 'season', 'all_season') or 'all_season'
                fw_type = getattr(prod, 'footwear_type', None)
                acc_type = getattr(prod, 'accessory_type', None)
                metal = getattr(prod, 'metal_tone', None)
                inc_blouse = bool(getattr(prod, 'includes_blouse', False))
                inc_dupatta = bool(getattr(prod, 'includes_dupatta', False))

                item = WardrobeItem.objects.create(
                    customer_id=s_cust,
                    source='order_import',
                    product_key=p_key,
                    item_name=prod.product_name or f"Purchased Item {p_key}",
                    image_url=prod.image,
                    flat_image_url=prod.image,
                    thumb_url=prod.image,
                    original_image_url=prod.image,
                    slot_type=slot,
                    subtype=subtype,
                    formality=form,
                    pattern=pat,
                    dominant_colours=parsed_cols,
                    style_family=style,
                    season=season,
                    footwear_type=fw_type,
                    accessory_type=acc_type,
                    metal_tone=metal,
                    includes_blouse=inc_blouse,
                    includes_dupatta=inc_dupatta,
                    confidence=1.0,
                    needs_review=False,
                    user_verified=True,
                    is_active=True
                )
                imported.append(item.id)

        return {
            "success": True,
            "imported_count": len(imported),
            "skipped_count": len(skipped),
            "imported_item_ids": imported
        }
