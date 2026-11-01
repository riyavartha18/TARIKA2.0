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
* `rfm_customer_segments` + `rfm_analysis_state` - the segment label of the
  latest completed analysis per buyer, so a customer page reads one indexed row
  instead of rebuilding the cached snapshot (or recomputing the analysis).

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


class OfferCategory(models.TextChoices):
    """Which of the two offer families a campaign carries.

    A campaign may hold a discount offer, a Buy & Get offer, or both at once
    (`COMBINED`). The category decides which of the JSON rule fields must be
    filled in; `benefits_combinable` then decides whether a COMBINED campaign
    stacks both benefits at checkout or only grants the better one.
    """
    DISCOUNT = 'DISCOUNT', 'Discount offer'
    BUY_GET = 'BUY_GET', 'Buy & Get offer'
    COMBINED = 'COMBINED', 'Combined offer'


class Campaign(models.Model):
    campaign_id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=200)
    coupon_code = models.CharField(max_length=64, unique=True)
    description = models.TextField(blank=True, default='')

    offer_category = models.CharField(max_length=20, choices=OfferCategory.choices,
                                      default=OfferCategory.DISCOUNT)

    # Structured offer rules (see benefits.py for the exact shape of each):
    # `discount_rule` holds the monetary offer, `buy_get_rule` the quantity/
    # product-based one, and `scope` the eligible product/category selection.
    # Empty dicts mean "no such benefit"; a COMBINED campaign fills both.
    discount_rule = models.JSONField(default=dict, blank=True)
    buy_get_rule = models.JSONField(default=dict, blank=True)
    scope = models.JSONField(default=dict, blank=True)
    # COMBINED only: can both benefits apply to the same checkout, or does
    # the customer get whichever benefit is better for them?
    benefits_combinable = models.BooleanField(default=False)

    # Legacy simple-discount fields, kept as the headline mirror of
    # `discount_rule` so older offers and API consumers keep working.
    discount_type = models.CharField(max_length=20, choices=DiscountType.choices,
                                     default=DiscountType.PERCENTAGE)
    discount_value = models.DecimalField(max_digits=12, decimal_places=2,
                                         default=0)
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
        # Every customer offer read asks for "PUBLISHED rows whose validity
        # window covers now". Without this index PostgreSQL would scan the whole
        # table on each request; with it the live set is an index range scan.
        indexes = [
            models.Index(fields=['status', 'start_date', 'end_date'],
                         name='campaign_live_window'),
        ]

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
            # One customer, one redemption per coupon - the business rule for
            # personalized segment offers. It is a database guarantee, not a
            # convention: two checkouts racing each other cannot both book it,
            # and it still lets a different customer use the same campaign.
            models.UniqueConstraint(
                fields=['campaign', 'customer_id'],
                name='unique_coupon_per_customer',
            ),
        ]
        indexes = [
            models.Index(fields=['campaign', 'customer_id'],
                         name='redemption_campaign_customer'),
            # The customer offer list asks "what has THIS buyer already
            # redeemed" in one query, for every campaign at once.
            models.Index(fields=['customer_id', 'campaign_id'],
                         name='redemption_customer_campaign'),
        ]

    def __str__(self):
        return f"{self.campaign_id} on {self.order_id} by {self.customer_id}"


class CustomerSegment(models.Model):
    """One row per buyer: the segment label from the latest completed analysis.

    The dashboard keeps its full snapshot in the shared cache (percentiles,
    scores, per-segment buckets), but a customer page only ever needs this
    buyer's segment and secondary tags. Reading them is a single primary-key row
    instead of deserializing ~100k cached records, and - crucially - it survives
    a server restart, so opening My Profile can never trigger a fresh full
    RFM computation. Written only by a successfully completed run (see
    `segment_store`), so what is stored here is always a completed analysis.
    """
    customer_id = models.CharField(max_length=255, primary_key=True)
    segment = models.CharField(max_length=40)
    tags = models.JSONField(default=list, blank=True)
    version = models.PositiveIntegerField(default=0)
    computed_at = models.DateTimeField()

    class Meta:
        db_table = 'rfm_customer_segments'
        indexes = [
            # Audience counts by segment (admin campaign list / preview).
            models.Index(fields=['segment', 'customer_id'],
                         name='rfm_segment_by_label'),
        ]

    def __str__(self):
        return f"{self.customer_id} -> {self.segment}"


class RfmAnalysisState(models.Model):
    """Single row recording which analysis version is currently stored.

    It tells the read path the difference between "this buyer simply has no
    eligible purchase (so: no personalized offers)" and "no analysis has ever
    completed here yet (so: one is needed)". Without it, a missing segment row
    would be indistinguishable from an uninitialised system.
    """
    SINGLETON_ID = 1
    id = models.PositiveIntegerField(primary_key=True)
    version = models.PositiveIntegerField(default=0)
    buyer_count = models.PositiveIntegerField(default=0)
    analysis_date = models.DateField(null=True, blank=True)
    completed_at = models.DateTimeField()

    class Meta:
        db_table = 'rfm_analysis_state'

    def __str__(self):
        return f'RFM v{self.version} ({self.buyer_count} buyers)'
