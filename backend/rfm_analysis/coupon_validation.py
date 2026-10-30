"""Checkout-time coupon validation and redemption recording.

Every rule from Section 14 is enforced on the backend; the frontend never
decides a discount. Validation is a strict chain and the first failed check
returns a clear reason:

1. The coupon exists.
2. Its campaign is PUBLISHED.
3. It is within the start/end window (a lapsed campaign is refused).
4. The authenticated customer currently has a segment.
5. That segment/tags match the campaign's targeting.
6. The cart meets the minimum order amount.
7. The customer's usage limit (once / limited / unlimited) is not exhausted.
8. The campaign's global usage limit is not exhausted.

The discount amount and the final payable total are always recomputed here,
capped by `max_discount` for percentage offers and by the cart value.
Duplicate-order protection is guaranteed by the (campaign, order) unique
constraint in `models.CampaignRedemption`, applied when the redemption is
recorded after the order row is written.
"""

from django.db import transaction
from django.db.utils import IntegrityError
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from . import personalization
from .models import Campaign, CampaignRedemption, CampaignStatus, DiscountType, UsageType


def _compute_discount(campaign, cart_value):
    value = float(campaign.discount_value)
    if campaign.discount_type == DiscountType.PERCENTAGE:
        discount = cart_value * (value / 100.0)
        if campaign.max_discount is not None:
            discount = min(discount, float(campaign.max_discount))
    else:  # FIXED
        discount = value
    # Never discount below zero or beyond the cart itself.
    discount = max(0.0, min(discount, cart_value))
    return round(discount, 2)


def _customer_usage_count(campaign, customer_id):
    return CampaignRedemption.objects.filter(
        campaign=campaign, customer_id=customer_id
    ).count()


def validate_coupon(customer_id, coupon_code, cart_value):
    """Return the applied discount for an eligible coupon, or raise 400.

    Raises `rest_framework.exceptions.ValidationError` with a customer-safe
    message for any failed rule; the caller never receives a partial discount.
    """
    cart_value = round(float(cart_value or 0), 2)
    code = str(coupon_code or '').strip().upper()
    if not code:
        raise ValidationError({'coupon_code': 'A coupon code is required.'})

    campaign = Campaign.objects.filter(coupon_code__iexact=code).first()
    if not campaign:
        raise ValidationError({'coupon_code': 'This coupon code is not valid.'})

    now = timezone.now()
    if campaign.status != CampaignStatus.PUBLISHED:
        raise ValidationError({'coupon_code': 'This offer is not active.'})
    if not (campaign.start_date <= now <= campaign.end_date):
        raise ValidationError({'coupon_code': 'This offer is outside its validity dates.'})

    segment, tags, _record, _version = personalization.get_customer_segment(customer_id)
    if not segment:
        raise ValidationError({'coupon_code': 'This offer is not available for your account.'})

    from . import campaign_engine
    if not campaign_engine.matches_customer(campaign, segment, tags):
        raise ValidationError({'coupon_code': 'This offer does not apply to your account.'})

    if cart_value < float(campaign.min_order_amount or 0):
        raise ValidationError({
            'detail': f"A minimum order of {float(campaign.min_order_amount):.2f} is required for this coupon."
        })

    if campaign.usage_type == UsageType.ONCE:
        if _customer_usage_count(campaign, customer_id) >= 1:
            raise ValidationError({'detail': 'You have already used this coupon.'})
    elif campaign.usage_type == UsageType.LIMITED:
        if _customer_usage_count(campaign, customer_id) >= campaign.per_customer_limit:
            raise ValidationError({'detail': 'You have reached this coupon usage limit.'})

    if campaign.global_usage_limit:
        if campaign.redemptions.count() >= campaign.global_usage_limit:
            raise ValidationError({'detail': 'This offer has reached its total usage limit.'})

    discount = _compute_discount(campaign, cart_value)
    return {
        'campaign_id': campaign.campaign_id,
        'coupon_code': campaign.coupon_code,
        'discount_type': campaign.discount_type,
        'discount': discount,
        'subtotal': cart_value,
        'payable': round(cart_value - discount, 2),
    }


def redeem(campaign_id, customer_id, order_id, discount):
    """Book one redemption against a written order (duplicate-safe).

    Called after the order row exists. A second booking of the same coupon on
    the same order violates the unique constraint and is treated as already
    recorded, never as an error the customer must see twice.
    """
    try:
        with transaction.atomic():
            campaign = Campaign.objects.get(campaign_id=campaign_id)
            CampaignRedemption.objects.create(
                campaign=campaign,
                customer_id=customer_id,
                order_id=str(order_id),
                discount_applied=discount,
            )
    except (Campaign.DoesNotExist, IntegrityError):
        return False
    return True
