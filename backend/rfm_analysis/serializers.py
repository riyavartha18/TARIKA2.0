"""DRF serializers for the RFM/campaign module.

Campaign authoring is admin-only (Section 12): the serializer validates every
targeting and limit field, enforces sane date ordering, and refuses a
`LIMITED` usage type with no per-customer limit. Coupon codes are normalised to
uppercase so lookup and uniqueness stay predictable.
"""

from rest_framework import serializers

from . import utils
from .models import Campaign, DiscountType, UsageType


class CampaignSerializer(serializers.ModelSerializer):
    target_segments = serializers.ListField(
        child=serializers.CharField(), required=False, default=list
    )
    target_tags = serializers.ListField(
        child=serializers.CharField(), required=False, default=list
    )

    class Meta:
        model = Campaign
        fields = [
            'campaign_id', 'name', 'coupon_code', 'description',
            'discount_type', 'discount_value', 'max_discount',
            'target_segments', 'target_tags',
            'start_date', 'end_date',
            'min_order_amount', 'usage_type', 'per_customer_limit',
            'global_usage_limit', 'stacking_allowed', 'status',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['campaign_id', 'created_at', 'updated_at']

    def validate_coupon_code(self, value):
        cleaned = str(value or '').strip().upper()
        if not cleaned:
            raise serializers.ValidationError("A coupon code is required.")
        return cleaned

    def validate(self, attrs):
        start = attrs.get('start_date') or (self.instance and self.instance.start_date)
        end = attrs.get('end_date') or (self.instance and self.instance.end_date)
        if start and end and end <= start:
            raise serializers.ValidationError({'end_date': 'End date must be after the start date.'})

        discount_type = attrs.get('discount_type', getattr(self.instance, 'discount_type', None))
        value = attrs.get('discount_value', getattr(self.instance, 'discount_value', None))
        if value is not None:
            if float(value) <= 0:
                raise serializers.ValidationError({'discount_value': 'Discount must be greater than zero.'})
            if discount_type == DiscountType.PERCENTAGE and float(value) > 100:
                raise serializers.ValidationError({'discount_value': 'A percentage discount cannot exceed 100.'})

        usage_type = attrs.get('usage_type', getattr(self.instance, 'usage_type', None))
        limit = attrs.get('per_customer_limit', getattr(self.instance, 'per_customer_limit', 0))
        if usage_type == UsageType.LIMITED and (not limit or int(limit) < 1):
            raise serializers.ValidationError(
                {'per_customer_limit': 'Limited usage requires a per-customer limit of at least 1.'}
            )

        segments = attrs.get('target_segments', getattr(self.instance, 'target_segments', []))
        unknown = [s for s in (segments or []) if s not in utils.ALL_SEGMENTS]
        if unknown:
            raise serializers.ValidationError({'target_segments': f'Unknown segments: {unknown}'})

        return attrs
