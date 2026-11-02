from rest_framework import serializers
from .models import WardrobeItem, WardrobeMatch, WardrobeOutfit, WardrobeCollection


class WardrobeItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = WardrobeItem
        fields = [
            'id',
            'customer_id',
            'image_url',
            'flat_image_url',
            'thumb_url',
            'original_image_url',
            'render_status',
            'display_mode',
            'source',
            'product_key',
            'item_name',
            'slot_type',
            'subtype',
            'formality',
            'pattern',
            'dominant_colours',
            'style_family',
            'season',
            'sleeve_type',
            'length',
            'footwear_type',
            'accessory_type',
            'metal_tone',
            'includes_blouse',
            'includes_dupatta',
            'confidence',
            'needs_review',
            'user_verified',
            'is_active',
            'retake_prompt',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'customer_id', 'created_at', 'updated_at']


class WardrobeMatchSerializer(serializers.ModelSerializer):
    item_details = WardrobeItemSerializer(source='wardrobe_item', read_only=True)

    class Meta:
        model = WardrobeMatch
        fields = [
            'id',
            'customer_id',
            'product_key',
            'wardrobe_item_id',
            'item_details',
            'score',
            'reasons',
            'computed_at',
        ]


class WardrobeOutfitSerializer(serializers.ModelSerializer):
    class Meta:
        model = WardrobeOutfit
        fields = [
            'id',
            'customer_id',
            'name',
            'item_ids',
            'is_valid',
            'validation_notes',
            'created_at',
        ]
        read_only_fields = ['id', 'customer_id', 'created_at']


class WardrobeCollectionSerializer(serializers.ModelSerializer):
    items = WardrobeItemSerializer(many=True, read_only=True)
    item_count = serializers.IntegerField(source='items.count', read_only=True)

    class Meta:
        model = WardrobeCollection
        fields = [
            'id',
            'customer_id',
            'name',
            'items',
            'item_count',
            'created_at',
        ]
        read_only_fields = ['id', 'customer_id', 'created_at']
