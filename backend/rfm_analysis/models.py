"""Persistent campaign configuration and order-level redemption audit.

Section 12 requires campaign definitions to persist somewhere durable: unlike
the RFM results (which stay in a short-lived snapshot cache), a campaign cannot
exist only in memory. The inspected Neon database had no campaign, coupon or
redemption table, so this is the smallest new schema that satisfies the feature
without duplicating anything that already exists:

* `rfm_campaigns` - the admin-authored campaigns and their targeting rules.
* `rfm_campaign_redemptions` - one row per order that used a coupon, giving
  order-level redemption auditing (usage limits, global limits, duplicate
  protection) without adding columns to the read-only `public.orders` table and
  without any permanent customer-coupon assignment table.

Customer and order identity are stored as plain text keys (`customer_id`,
`order_id`) rather than foreign keys, because `public.orders`/`public.customers`
are unmanaged dataset tables; matching them by key avoids introducing FK
constraints Postgres could not validate against existing rows.
"""

from django.db import models


class UsageType(models.TextChoices):
    ONCE = 'ONCE', 'Once per customer'
    LIMITED = 'LIMITED', 'Limited uses per customer'
    UNLIMITED = 'UNLIMITED', 'Unlimited uses per customer'


class DiscountType(models.TextChoices):
    PERCENTAGE = 'PERCENTAGE', 'Percentage'
    FIXED = 'FIXED', 'Fixed amount'


class CampaignStatus(models.TextChoices):
    DRAFT = 'DRAFT', 'Draft'
    PUBLISHED = 'PUBLISHED', 'Published'
    PAUSED = 'PAUSED', 'Paused'
    EXPIRED = 'EXPIRED', 'Expired'


class Campaign(models.Model):
    campaign_id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=200)
    coupon_code = models.CharField(max_length=64, unique=True)
    description = models.TextField(blank=True, default='')

    discount_type = models.CharField(max_length=20, choices=DiscountType.choices,
                                     default=DiscountType.PERCENTAGE)
    discount_value = models.DecimalField(max_digits=12, decimal_places=2)
    max_discount = models.DecimalField(max_digits=12, decimal_places=2,
                                       null=True, blank=True)

    # Targeting: JSON lists of segment labels / secondary tags. Empty target
    # segment list means the campaign targets no one and is never shown.
    target_segments = models.JSONField(default=list, blank=True)
    target_tags = models.JSONField(default=list, blank=True)

    start_date = models.DateTimeField()
    end_date = models.DateTimeField()

    min_order_amount = models.DecimalField(max_digits=12, decimal_places=2,
                                           default=0)
    usage_type = models.CharField(max_length=20, choices=UsageType.choices,
                                  default=UsageType.UNLIMITED)
    per_customer_limit = models.PositiveIntegerField(default=0)  # used with LIMITED
    global_usage_limit = models.PositiveIntegerField(default=0)  # 0 = unlimited
    stacking_allowed = models.BooleanField(default=False)

    status = models.CharField(max_length=20, choices=CampaignStatus.choices,
                              default=CampaignStatus.DRAFT)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'rfm_campaigns'
        ordering = ['-campaign_id']

    def __str__(self):
        return f"{self.name} ({self.coupon_code})"


class CampaignRedemption(models.Model):
    redemption_id = models.BigAutoField(primary_key=True)
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE,
                                 related_name='redemptions')
    order_id = models.CharField(max_length=32)
    customer_id = models.CharField(max_length=255)
    discount_applied = models.DecimalField(max_digits=12, decimal_places=2)
    redeemed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'rfm_campaign_redemptions'
        ordering = ['-redemption_id']
        # Duplicate-order protection: the same coupon cannot be booked twice
        # against the same order, whatever the usage limit is.
        constraints = [
            models.UniqueConstraint(
                fields=['campaign', 'order_id'],
                name='unique_coupon_per_order',
            ),
        ]
        indexes = [
            models.Index(fields=['campaign', 'customer_id'],
                         name='redemption_campaign_customer'),
        ]

    def __str__(self):
        return f"{self.campaign_id} on {self.order_id} by {self.customer_id}"
