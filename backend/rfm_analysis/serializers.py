"""DRF serializers for the RFM/campaign module.

Campaign authoring is admin-only: the serializer validates every targeting,
offer-rule and limit field, enforces sane date ordering, and refuses a
`LIMITED` usage type with no per-customer limit. Coupon codes are normalised to
uppercase so lookup and uniqueness stay predictable.

Segment targeting is strict by design: `target_segments` is mandatory and can
only name the six primary buyer segments. "Never Purchased" can never be a
campaign audience (buyer campaigns must not reach non-buyers), there is no
"Others" segment, and "Big Spender" is only usable as a secondary tag - never
as a primary segment. Publishing validity (dates, completion) is additionally
guarded by the status endpoint in `views.py`.
"""

from rest_framework import serializers

from . import benefits, utils
from .models import Campaign, DiscountType, OfferCategory, UsageType


def _num(value, field, *, minimum=0, maximum=None, required=True):
    """Coerce one JSON rule number with a clear, field-scoped error."""
    if value is None or value == '':
        if required:
            raise serializers.ValidationError({field: f'{field} is required.'})
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise serializers.ValidationError({field: f'{field} must be a number.'})
    if number < minimum:
        raise serializers.ValidationError({field: f'{field} must be at least {minimum}.'})
    if maximum is not None and number > maximum:
        raise serializers.ValidationError({field: f'{field} cannot exceed {maximum}.'})
    return number


class CampaignSerializer(serializers.ModelSerializer):
    target_segments = serializers.ListField(
        child=serializers.CharField(), required=False, default=list
    )
    target_tags = serializers.ListField(
        child=serializers.CharField(), required=False, default=list
    )
    offer_summary = serializers.SerializerMethodField()

    class Meta:
        model = Campaign
        fields = [
            'campaign_id', 'name', 'coupon_code', 'description',
            'offer_category', 'discount_rule', 'buy_get_rule', 'scope',
            'benefits_combinable', 'offer_summary',
            'discount_type', 'discount_value', 'max_discount',
            'target_segments', 'target_tags',
            'start_date', 'end_date',
            'min_order_amount', 'usage_type', 'per_customer_limit',
            'global_usage_limit', 'stacking_allowed', 'status',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['campaign_id', 'created_at', 'updated_at']

    def get_offer_summary(self, obj):
        return benefits.offer_summary(obj)

    def validate_coupon_code(self, value):
        cleaned = str(value or '').strip().upper()
        if not cleaned:
            raise serializers.ValidationError("A coupon code is required.")
        return cleaned

    def validate_target_segments(self, value):
        cleaned = []
        for segment in value or []:
            label = str(segment).strip()
            if label == utils.SEGMENT_NEVER_PURCHASED:
                raise serializers.ValidationError(
                    "Never Purchased customers cannot receive buyer-segment campaigns."
                )
            if label not in utils.PRIMARY_SEGMENTS:
                raise serializers.ValidationError(f'Unknown segment: {label}')
            if label not in cleaned:
                cleaned.append(label)
        if not cleaned:
            raise serializers.ValidationError(
                'Choose at least one target segment - campaigns never go to all customers.'
            )
        return cleaned

    def validate_target_tags(self, value):
        cleaned = []
        for tag in value or []:
            label = str(tag).strip()
            if label not in utils.SECONDARY_TAGS:
                raise serializers.ValidationError(
                    f'Unknown secondary tag: {label}. Only {utils.SECONDARY_TAGS} exist.'
                )
            if label not in cleaned:
                cleaned.append(label)
        return cleaned

    def validate_scope(self, value):
        mode = (value or {}).get('mode') or 'ALL'
        if mode not in benefits.SCOPE_MODES:
            raise serializers.ValidationError({'scope': f'Unknown scope mode: {mode}'})
        if mode == 'PRODUCTS':
            ids = [str(p).strip() for p in (value.get('product_ids') or []) if str(p).strip()]
            if not ids:
                raise serializers.ValidationError(
                    {'scope': 'Select at least one eligible product.'})
            value = dict(value, product_ids=ids)
        elif mode == 'CATEGORIES':
            cats = [str(c).strip() for c in (value.get('categories') or []) if str(c).strip()]
            if not cats:
                raise serializers.ValidationError(
                    {'scope': 'Select at least one eligible category.'})
            value = dict(value, categories=cats)
        return value

    def validate_discount_rule(self, value):
        if not value:
            return {}
        kind = value.get('type')
        if kind not in benefits.DISCOUNT_TYPES:
            raise serializers.ValidationError({'discount_rule': f'Unknown discount offer: {kind}'})
        if kind == 'PERCENTAGE':
            _num(value.get('percent'), 'percent', minimum=0.01, maximum=100)
        elif kind == 'FLAT':
            _num(value.get('flat'), 'flat', minimum=0.01)
        elif kind == 'SPEND_BASED':
            _num(value.get('spend_threshold'), 'spend_threshold', minimum=0.01)
            off = _num(value.get('spend_discount'), 'spend_discount', minimum=0.01)
            if off > float(value['spend_threshold']):
                raise serializers.ValidationError(
                    {'discount_rule': 'The spend discount cannot exceed its spend threshold.'})
        elif kind == 'BUY_MORE_SAVE_MORE':
            tiers = value.get('tiers') or []
            if not tiers:
                raise serializers.ValidationError(
                    {'discount_rule': 'Add at least one buy-more-save-more tier.'})
            for tier in tiers:
                _num(tier.get('buy'), 'buy', minimum=2, maximum=999)
                _num(tier.get('percent'), 'percent', minimum=0.01, maximum=100)
        elif kind == 'CASHBACK':
            _num(value.get('cashback'), 'cashback', minimum=0.01)
        return value

    def validate_buy_get_rule(self, value):
        if not value:
            return {}
        kind = value.get('type')
        if kind not in benefits.BUY_GET_TYPES:
            raise serializers.ValidationError({'buy_get_rule': f'Unknown Buy & Get offer: {kind}'})
        if kind in ('BUY_X_GET_Y_FREE', 'BUY_X_GET_Y_DISCOUNT'):
            _num(value.get('buy_qty'), 'buy_qty', minimum=1, maximum=999)
            _num(value.get('get_qty'), 'get_qty', minimum=1, maximum=999)
            if kind == 'BUY_X_GET_Y_DISCOUNT':
                _num(value.get('discount_percent'), 'discount_percent',
                     minimum=0.01, maximum=100)
        elif kind == 'BUNDLE':
            ids = [str(p).strip() for p in (value.get('product_ids') or []) if str(p).strip()]
            if len(ids) < 2:
                raise serializers.ValidationError(
                    {'buy_get_rule': 'A bundle needs at least two selected products.'})
            _num(value.get('bundle_price'), 'bundle_price', minimum=0.01)
            value = dict(value, product_ids=ids)
        elif kind == 'FREE_GIFT':
            if not str(value.get('gift_name') or '').strip():
                raise serializers.ValidationError(
                    {'buy_get_rule': 'Name the free gift product.'})
            _num(value.get('gift_value'), 'gift_value', minimum=0)
            _num(value.get('min_order_amount'), 'min_order_amount', minimum=0)
        elif kind == 'PRODUCT_DISCOUNT':
            percent = value.get('discount_percent')
            flat = value.get('discount_flat')
            if not percent and not flat:
                raise serializers.ValidationError(
                    {'buy_get_rule': 'Set a percentage or flat amount for the product offer.'})
            if percent:
                _num(percent, 'discount_percent', minimum=0.01, maximum=100)
            if flat:
                _num(flat, 'discount_flat', minimum=0.01)
        return value

    def validate(self, attrs):
        start = attrs.get('start_date') or (self.instance and self.instance.start_date)
        end = attrs.get('end_date') or (self.instance and self.instance.end_date)
        if start and end and end <= start:
            raise serializers.ValidationError({'end_date': 'End date must be after the start date.'})

        category = attrs.get('offer_category',
                             getattr(self.instance, 'offer_category', OfferCategory.DISCOUNT))
        discount_rule = attrs.get('discount_rule',
                                  getattr(self.instance, 'discount_rule', None) or {})
        buy_get_rule = attrs.get('buy_get_rule',
                                 getattr(self.instance, 'buy_get_rule', None) or {})

        # The category decides which rules must exist; stray rules from an
        # earlier edit are cleared so a campaign never carries hidden benefits.
        if category == OfferCategory.DISCOUNT:
            attrs['buy_get_rule'] = {}
            buy_get_rule = {}
            if not discount_rule:
                self._validate_legacy_discount(attrs)
            elif not discount_rule.get('type'):
                raise serializers.ValidationError(
                    {'discount_rule': 'Configure the discount offer details.'})
        elif category == OfferCategory.BUY_GET:
            attrs['discount_rule'] = {}
            discount_rule = {}
            if not buy_get_rule or not buy_get_rule.get('type'):
                raise serializers.ValidationError(
                    {'buy_get_rule': 'Configure the Buy & Get offer details.'})
        else:  # COMBINED
            if not discount_rule or not discount_rule.get('type'):
                raise serializers.ValidationError(
                    {'discount_rule': 'A combined campaign needs discount offer details.'})
            if not buy_get_rule or not buy_get_rule.get('type'):
                raise serializers.ValidationError(
                    {'buy_get_rule': 'A combined campaign needs Buy & Get offer details.'})

        usage_type = attrs.get('usage_type', getattr(self.instance, 'usage_type', None))
        limit = attrs.get('per_customer_limit', getattr(self.instance, 'per_customer_limit', 0))
        if usage_type == UsageType.LIMITED and (not limit or int(limit) < 1):
            raise serializers.ValidationError(
                {'per_customer_limit': 'Limited usage requires a per-customer limit of at least 1.'}
            )

        attrs = self._mirror_legacy_fields(attrs, discount_rule or buy_get_rule)
        return attrs

    def _validate_legacy_discount(self, attrs):
        """Structured-rule-free DISCOUNT campaigns still use discount_value."""
        discount_type = attrs.get('discount_type',
                                  getattr(self.instance, 'discount_type', DiscountType.PERCENTAGE))
        value = attrs.get('discount_value',
                          getattr(self.instance, 'discount_value', None))
        if value is None or float(value) <= 0:
            raise serializers.ValidationError(
                {'discount_value': 'Discount must be greater than zero.'})
        if discount_type == DiscountType.PERCENTAGE and float(value) > 100:
            raise serializers.ValidationError(
                {'discount_value': 'A percentage discount cannot exceed 100.'})

    def _mirror_legacy_fields(self, attrs, headline_rule):
        """Keep discount_type/discount_value a faithful headline of the rule.

        Older API consumers (and the customer offer cards) read the legacy
        fields; syncing them from the structured rule means one campaign can
        never describe itself differently on two surfaces.
        """
        kind = (headline_rule or {}).get('type')
        percent = flat = None
        if kind == 'PERCENTAGE':
            percent = headline_rule.get('percent')
        elif kind == 'FLAT':
            flat = headline_rule.get('flat')
        elif kind == 'SPEND_BASED':
            flat = headline_rule.get('spend_discount')
        elif kind == 'BUY_MORE_SAVE_MORE':
            tiers = headline_rule.get('tiers') or [{}]
            percent = max((float(t.get('percent') or 0) for t in tiers), default=0)
        elif kind == 'PRODUCT_DISCOUNT':
            percent = headline_rule.get('discount_percent')
            flat = headline_rule.get('discount_flat')
        elif kind == 'BUY_X_GET_Y_DISCOUNT':
            percent = headline_rule.get('discount_percent')
        elif kind == 'CASHBACK':
            flat = headline_rule.get('cashback')
        if percent:
            attrs['discount_type'] = DiscountType.PERCENTAGE
            attrs['discount_value'] = percent
        elif flat:
            attrs['discount_type'] = DiscountType.FIXED
            attrs['discount_value'] = flat
        elif kind:  # free shipping / gift / bogo / bundle / buy-get-free
            attrs['discount_type'] = DiscountType.FIXED
            attrs['discount_value'] = 0
        return attrs
