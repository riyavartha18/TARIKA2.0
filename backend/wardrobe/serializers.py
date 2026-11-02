from rest_framework import serializers
from .models import WardrobeItem

class WardrobeItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = WardrobeItem
        fields = [
            'id',
            'customer_id',
            'item_name',
            'category',
            'subcategory',
            'primary_color',
            'secondary_color',
            'style_tag',
            'occasion',
            'season',
            'material',
            'image_url',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'customer_id', 'created_at', 'updated_at']
