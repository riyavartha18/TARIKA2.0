"""DRF serializers for the RFM/campaign module.

Campaign authoring is admin-only: the serializer validates every targeting,
offer-rule and limit field, enforces sane date ordering, and refuses a
`LIMITED` usage type with no per-customer limit. Coupon codes are normalised to
uppercase so lookup and uniqueness stay predictable.

Audience rules, for the two segmentation kinds a campaign can carry:

* K-Means (what the Campaign page authors now): `target_cluster_ids` is
  mandatory and may only name clusters of the persisted clustering run; each
  campaign stores that run plus the business labels those clusters carried in
  it, and never mixes in the old segment fields.
* Legacy rule-based segments (`LEGACY_RFM`): read-only history. The segments a
  campaign names are kept so an already published campaign still describes who
  its coupons went to, and the vocabulary is validated (`Never Purchased` can
  never be an audience, there is no "Others" segment, `Big Spender` is only a
  secondary tag). Authoring or re-targeting on segments is refused unless the
  operator puts the previous segmentation back in service
  (`RFM_LEGACY_CAMPAIGNS_VISIBLE_TO_CUSTOMERS=1`).

An existing campaign may only change its audience kind while it is a draft: a
published campaign's audience - and therefore who holds its coupons - is never
reinterpreted under the admin's feet. Publishing validity (dates, completion)
is additionally guarded by the status endpoint in `views.py`.
"""

import json
from datetime import datetime, timezone as utc_timezone
from decimal import Decimal

from rest_framework import serializers

from . import benefits, cluster_targeting, clustering, utils
from .models import (Campaign, CampaignAudience, CampaignStatus, DiscountType,
                     OfferCategory, TargetingMode, UsageType)


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
    # K-Means targeting. `required=False` with no default, so a partial edit
    # that does not mention the audience keeps the stored one instead of
    # silently clearing it.
    targeting_mode = serializers.ChoiceField(
        choices=TargetingMode.choices, required=False
    )
    target_cluster_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=0), required=False
    )
    target_cluster_labels = serializers.ListField(
        child=serializers.CharField(), read_only=True
    )
    # The run reference is read from the local foreign-key column on every row,
    # while its full description (and the per-cluster audience breakdown) is
    # only fetched for one campaign at a time: a list page must not turn into a
    # query per campaign against the remote database.
    clustering_run_id = serializers.IntegerField(read_only=True)
    clustering_run = serializers.SerializerMethodField()
    audience_clusters = serializers.SerializerMethodField()
    offer_summary = serializers.SerializerMethodField()

    class Meta:
        model = Campaign
        fields = [
            'campaign_id', 'name', 'coupon_code', 'description',
            'offer_category', 'discount_rule', 'buy_get_rule', 'scope',
            'benefits_combinable', 'offer_summary',
            'discount_type', 'discount_value', 'max_discount',
            'targeting_mode', 'target_segments', 'target_tags',
            'target_cluster_ids', 'target_cluster_labels',
            'clustering_run_id', 'clustering_run', 'audience_clusters',
            'start_date', 'end_date',
            'min_order_amount', 'usage_type', 'per_customer_limit',
            'global_usage_limit', 'stacking_allowed', 'status',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['campaign_id', 'created_at', 'updated_at']

    def get_offer_summary(self, obj):
        return benefits.offer_summary(obj)

    def _detailed(self):
        return bool(self.context.get('include_audience'))

    def get_clustering_run(self, obj):
        """Which K-Means run this campaign's audience was chosen from."""
        if not self._detailed():
            return None
        return clustering.run_view(obj.clustering_run)

    def get_audience_clusters(self, obj):
        """Per selected cluster: business label, eligible customers, coupons."""
        if not self._detailed() or not obj.targets_clusters:
            return []
        return cluster_targeting.cluster_breakdown(obj)

    def validate_coupon_code(self, value):
        cleaned = str(value or '').strip().upper()
        if not cleaned:
            raise serializers.ValidationError("A coupon code is required.")
        return cleaned

    def validate_target_segments(self, value):
        """Vocabulary only; whether a legacy campaign needs at least one is
        decided in `validate()`, where the campaign's targeting mode is known."""
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
        attrs = self._validate_audience(attrs)
        attrs = self._validate_issued_terms(attrs)

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

    # The fields that define what a holder of this coupon is entitled to: the
    # benefit, its limits, its scope and its validity window.
    TERM_FIELDS = ('offer_category', 'discount_rule', 'buy_get_rule', 'scope',
                   'benefits_combinable', 'discount_type', 'discount_value',
                   'max_discount', 'min_order_amount', 'start_date', 'end_date',
                   'usage_type', 'per_customer_limit', 'global_usage_limit',
                   'stacking_allowed')

    def _terms_are_issued(self, instance):
        """Has this campaign's coupon already reached customers?

        Anything beyond a fresh draft counts: a campaign that has been published
        (even if it is now paused or expired) and any campaign that already holds
        coupon assignments or redemptions. Those customers received concrete
        terms, and no later edit may change them.
        """
        if instance.status != CampaignStatus.DRAFT:
            return True
        if instance.redemptions.exists():
            return True
        return CampaignAudience.objects.filter(campaign=instance).exists()

    @staticmethod
    def _term_value(value):
        """Comparable form of one term field (dates, decimals and JSON as needed)."""
        if isinstance(value, (dict, list)):
            return json.dumps(value, sort_keys=True, default=str)
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, datetime):
            # A naive stamp (only ever a UTC one in this project) is read as UTC
            # so both sides of the comparison are on the same instant.
            aware = value if value.tzinfo else value.replace(tzinfo=utc_timezone.utc)
            return aware.astimezone(utc_timezone.utc).isoformat()
        return value

    def _validate_issued_terms(self, attrs):
        """Refuse a silent rewrite of terms customers already hold.

        Editing a campaign that has issued coupons is limited to what cannot
        change the offer itself: its name, its description and - for a K-Means
        campaign - the customer groups it is aimed at, which only ever *adds*
        customers with the very same terms. Anything monetary or time-bound is
        rejected with the reason, so the admin deactivates and authors a new
        campaign instead of moving coupons already in customers' accounts.
        """
        instance = self.instance
        if instance is None or not self._terms_are_issued(instance):
            return attrs
        changed = [field for field in self.TERM_FIELDS
                   if field in attrs
                   and self._term_value(attrs[field])
                   != self._term_value(getattr(instance, field, None))]
        if changed:
            raise serializers.ValidationError({
                field: (
                    'This campaign has already issued coupons, so its '
                    f'{field.replace("_", " ")} cannot be changed without altering '
                    'terms customers already hold. Deactivate it and create a new '
                    'campaign instead.')
                for field in changed
            })
        return attrs

    def _validate_audience(self, attrs):
        """Resolve and cross-check the campaign's audience for its mode.

        A K-Means campaign stores the clusters of the latest persisted run plus
        the labels that run gave them, and carries no segment/tag targeting; a
        legacy campaign keeps the segment rules and never carries cluster ids.
        The two can therefore never be confused for each other, on any surface.
        """
        instance = self.instance
        mode = attrs.get('targeting_mode') or getattr(
            instance, 'targeting_mode', TargetingMode.LEGACY_RFM)

        if instance is not None and instance.targeting_mode != mode:
            if instance.status != CampaignStatus.DRAFT:
                raise serializers.ValidationError({'targeting_mode': (
                    'Only a draft can switch its audience to the K-Means clusters. '
                    'A published campaign keeps the customers its coupons were '
                    'issued to - create a new campaign for the new groups instead.')})

        if mode != TargetingMode.KMEANS and not utils.LEGACY_CAMPAIGNS_VISIBLE_TO_CUSTOMERS:
            # Campaign targeting uses the four K-Means groups only. The stored
            # segments of an existing legacy campaign are still readable (they
            # describe who its coupons went to) but no campaign may be authored
            # or re-targeted on them, and only a draft may be converted.
            raise serializers.ValidationError({
                'targeting_mode': (
                    'Campaign targeting uses the current K-Means customer groups. '
                    'Choose one or more of the four groups instead of RFM segments.')})

        if mode == TargetingMode.KMEANS:
            cluster_ids = attrs.get('target_cluster_ids')
            if cluster_ids is None and instance is not None:
                # The audience was not restated, so it is kept exactly as
                # published - the same clusters, the same business labels and
                # the same clustering run. Editing an offer or a date of a live
                # campaign can never re-point it at a newer run.
                attrs['targeting_mode'] = TargetingMode.KMEANS
                attrs.setdefault(
                    'target_segments', getattr(instance, 'target_segments', []) or [])
                return attrs
            try:
                cluster_ids = cluster_targeting.validate_cluster_ids(cluster_ids or [])
            except ValueError as exc:
                raise serializers.ValidationError({'target_cluster_ids': str(exc)})
            run = cluster_targeting.selected_run()
            attrs['targeting_mode'] = TargetingMode.KMEANS
            attrs['target_cluster_ids'] = cluster_ids
            attrs['target_cluster_labels'] = [
                label for label in cluster_targeting.labels_for(cluster_ids, run) if label]
            attrs['clustering_run'] = run
            # Old segment targeting is simply not part of this campaign any more
            # (and the reverse holds for a legacy campaign: no cluster ids).
            attrs['target_segments'] = []
            attrs['target_tags'] = []
            return attrs

        segments = attrs.get('target_segments') or getattr(
            instance, 'target_segments', None) or []
        if not segments:
            raise serializers.ValidationError({
                'target_segments': (
                    'Choose at least one target segment - '
                    'campaigns never go to all customers.')})
        attrs['targeting_mode'] = TargetingMode.LEGACY_RFM
        attrs['target_segments'] = segments
        attrs['target_cluster_ids'] = []
        attrs['target_cluster_labels'] = []
        attrs['clustering_run'] = None
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
