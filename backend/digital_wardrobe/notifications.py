import os
from datetime import timedelta
from typing import Dict, Any, List
from django.utils import timezone
from django.db.models import Count
from catalog.models import Product
from .models import WardrobeItem, WardrobeNotificationLog
from .matching import WardrobeMatcher


class WardrobeNotificationService:
    """
    Nightly background notification engine (Feature Flagged: WARDROBE_NOTIFICATIONS_ENABLED).
    Evaluates newly launched products vs active customer wardrobes.
    Rules:
    - Feature flag off by default.
    - Notify only if match score >= 80 and at least 2 pieces match.
    - Max 2 notifications per customer per rolling 7-day week.
    - Logs every notification into wardrobe_notification_logs.
    """

    @classmethod
    def can_notify_customer(cls, customer_id: str) -> bool:
        """Checks whether the customer has received fewer than 2 notifications in rolling 7 days."""
        now = timezone.now()
        week_ago = now - timedelta(days=7)
        recent_sends = WardrobeNotificationLog.objects.filter(
            customer_id=customer_id,
            sent_at__gte=week_ago
        ).count()
        return recent_sends < 2

    @classmethod
    def is_enabled(cls) -> bool:
        flag = os.environ.get('WARDROBE_NOTIFICATIONS_ENABLED', 'false').lower().strip()
        return flag in ('true', '1', 'yes')

    @classmethod
    def run_nightly_job(cls, days_back: int = 1) -> Dict[str, Any]:
        if not cls.is_enabled():
            return {
                "success": True,
                "message": "Wardrobe notifications are disabled by feature flag (WARDROBE_NOTIFICATIONS_ENABLED=false).",
                "sent_count": 0
            }

        now = timezone.now()
        week_ago = now - timedelta(days=7)

        # 1. Get newly active products
        new_products = Product.objects.filter(is_active=True, hidden=False)[:30]

        # 2. Get active customers who have at least 2 wardrobe items
        active_customers = WardrobeItem.objects.filter(
            is_active=True
        ).values('customer_id').annotate(
            item_count=Count('id')
        ).filter(item_count__gte=2)

        sent_records = []

        for cust_record in active_customers:
            cust_id = cust_record['customer_id']

            # Check weekly cap: max 2 notifications per customer per rolling 7 days
            recent_sends = WardrobeNotificationLog.objects.filter(
                customer_id=cust_id,
                sent_at__gte=week_ago
            ).count()

            if recent_sends >= 2:
                continue

            customer_items = list(WardrobeItem.objects.filter(customer_id=cust_id, is_active=True))

            for prod in new_products:
                matches = WardrobeMatcher.match_product_to_wardrobe(prod, customer_items)

                # Gate: Score >= 80 and at least 2 pieces match
                qualifying_matches = [m for m in matches if m['score'] >= 80.0]
                if len(qualifying_matches) >= 2:
                    top_score = max(m['score'] for m in qualifying_matches)
                    
                    # Record send
                    log_entry = WardrobeNotificationLog.objects.create(
                        customer_id=cust_id,
                        product_key=str(prod.product_id),
                        score=top_score,
                        matches_count=len(qualifying_matches)
                    )
                    sent_records.append({
                        'customer_id': cust_id,
                        'product_id': prod.product_id,
                        'product_name': prod.product_name,
                        'score': top_score,
                        'matches_count': len(qualifying_matches)
                    })

                    recent_sends += 1
                    if recent_sends >= 2:
                        break  # Reached weekly cap for this customer

        return {
            "success": True,
            "sent_count": len(sent_records),
            "notifications": sent_records
        }
