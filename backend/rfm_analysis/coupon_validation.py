"""Checkout-time coupon validation and redemption recording.

Every rule is enforced on the backend; the frontend never decides a discount.
Validation is a strict chain and the first failed check returns a clear reason:

1. The coupon exists.
2. Its campaign is PUBLISHED.
3. It is within its validity dates (a lapsed campaign is refused).
4. The authenticated customer currently has a segment.
5. That segment/tags match the campaign's targeting.
6. The cart meets the minimum order amount.
7. This customer has not already redeemed this coupon (one use per customer).
8. The customer/global usage limits of the campaign are not exhausted.

The benefit itself (discount, cashback, free shipping, gift - including every
Buy & Get rule) is computed by `benefits.py` from the server-side cart lines
when they are available, and from the cart value alone for simple percentage/
fixed offers.

A coupon is only *consumed* when `redeem()` books a row, which the checkout
service does inside the same transaction that writes the order rows: a failed
or rolled-back payment therefore never marks the coupon as used. Redemption
history is append-only and is never deleted, so My Profile / Member Privileges
can keep showing a Used offer and reports can audit it.
"""

from django.db import transaction
from django.db.utils import IntegrityError
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from . import benefits, personalization
from .models import Campaign, CampaignRedemption, CampaignStatus, UsageType

NOT_AVAILABLE = 'This offer is not available for your account.'
ALREADY_USED = 'You have already used this coupon.'


def _customer_usage_count(campaign, customer_id):
    return CampaignRedemption.objects.filter(
        campaign=campaign, customer_id=customer_id
    ).count()


def already_redeemed(campaign_id, customer_id):
    """Whether this authenticated customer has already redeemed this coupon."""
    return CampaignRedemption.objects.filter(
        campaign_id=campaign_id, customer_id=customer_id
    ).exists()


def validate_coupon(customer_id, coupon_code, cart_value, cart_lines=None):
    """Return the applied benefits for an eligible coupon, or raise 400.

    `cart_lines` is the server-side cart breakdown (product id, quantity,
    unit price, category); product-scoped Buy & Get rules need it. When only
    a cart value is available, whole-cart offers (percentage, flat, spend-
    based, cashback, free shipping, free gift) are still priced exactly.
    Raises `rest_framework.exceptions.ValidationError` with a customer-safe
    message for any failed rule; the caller never receives a partial discount.
    """
    cart_value = round(float(cart_value or 0), 2)
    code = str(coupon_code or '').strip().upper()
    if not code:
        raise ValidationError({'coupon_code': 'A coupon code is required.'})

    campaign = Campaign.objects.filter(coupon_code__iexact=code).first()
    if not campaign:
        raise ValidationError({'coupon_code': 'Invalid coupon code.'})

    now = timezone.now()
    if campaign.status != CampaignStatus.PUBLISHED:
        raise ValidationError({'coupon_code': 'This offer is not active.'})
    if campaign.end_date < now:
        raise ValidationError({'coupon_code': 'This offer has expired.'})
    if campaign.start_date > now:
        raise ValidationError({'coupon_code': 'This offer has not started yet.'})

    segment, tags, _record, version = personalization.get_customer_segment(customer_id)
    if not segment and version is None:
        # No completed analysis in this process yet (e.g. a restarted server,
        # since the snapshot is cache-only). Ask for a run and ask the customer
        # to retry, rather than rejecting a coupon they are actually eligible
        # for. The run lock keeps concurrent requests from stacking up.
        from . import cache_manager, engine
        if cache_manager.try_offer_self_heal():
            engine.ensure_latest()
        raise ValidationError({
            'coupon_code': 'Your offers are being refreshed. Please try again in a minute.'
        })
    if not segment:
        raise ValidationError({'coupon_code': NOT_AVAILABLE})

    from . import campaign_engine
    if not campaign_engine.matches_customer(campaign, segment, tags):
        # Also covers someone typing another segment's code by hand: eligibility
        # is always decided from the server-side segment, never from the input.
        raise ValidationError({'coupon_code': NOT_AVAILABLE})

    # One customer, one redemption per coupon - whatever the usage type says.
    if _customer_usage_count(campaign, customer_id) >= 1:
        raise ValidationError({'detail': ALREADY_USED})

    if cart_value < float(campaign.min_order_amount or 0):
        raise ValidationError({
            'detail': 'Minimum purchase of '
                      f'₹{float(campaign.min_order_amount):,.0f} is required to use this coupon.'
        })

    if campaign.usage_type == UsageType.LIMITED:
        if _customer_usage_count(campaign, customer_id) >= campaign.per_customer_limit:
            raise ValidationError({'detail': 'You have reached this coupon usage limit.'})

    if campaign.global_usage_limit:
        if campaign.redemptions.count() >= campaign.global_usage_limit:
            raise ValidationError({'detail': 'This offer has reached its total usage limit.'})

    discount_result = benefits.compute_benefits(campaign, cart_lines, cart_value)
    if discount_result['discount'] <= 0 and not discount_result['benefit_applied']:
        raise ValidationError({'detail': 'This offer does not apply to the items in your bag.'})
    return {
        'campaign_id': campaign.campaign_id,
        'coupon_code': campaign.coupon_code,
        'discount_type': campaign.discount_type,
        'discount': discount_result['discount'],
        'cashback': discount_result['cashback'],
        'free_shipping': discount_result['free_shipping'],
        'gift': discount_result['gift'],
        'benefit_applied': discount_result['benefit_applied'],
        'benefit_labels': discount_result['benefit_labels'],
        'offer_summary': benefits.offer_summary(campaign),
        'subtotal': cart_value,
        'payable': round(cart_value - discount_result['discount'], 2),
    }


def redeem(campaign_id, customer_id, order_id, discount):
    """Book one redemption for this customer, immediately after the order rows.

    Called inside the checkout transaction, so nothing is consumed unless the
    order itself commits. Three layers keep a coupon to one use per customer:

    * the campaign row is locked (`SELECT ... FOR UPDATE`), so two checkouts
      racing for the same customer + coupon serialize instead of both booking;
    * an existing redemption for that pair is refused before inserting;
    * the `unique_coupon_per_customer` constraint is the final guarantee - a
      duplicate insert raises IntegrityError and rolls back only this booking.

    Redemption rows are never deleted, so history stays auditable and the offer
    keeps showing as Used in My Profile and Member Privileges.
    """
    from . import cache_manager

    try:
        with transaction.atomic():
            campaign = (Campaign.objects.select_for_update()
                        .filter(campaign_id=campaign_id).first())
            if campaign is None:
                return False
            if _customer_usage_count(campaign, customer_id) >= 1:
                return False
            CampaignRedemption.objects.create(
                campaign=campaign,
                customer_id=customer_id,
                order_id=str(order_id),
                discount_applied=discount,
            )
    except (Campaign.DoesNotExist, IntegrityError):
        return False

    # The customer's offer list now has a different status, so the cached copy
    # must not be served any more (My Profile / Member Privileges flip to Used).
    cache_manager.bump_campaign_epoch()
    return True
