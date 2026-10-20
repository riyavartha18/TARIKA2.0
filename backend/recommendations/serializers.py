from rest_framework import serializers
from .models import ProductRecommendation


class RecommendationRuleSerializer(serializers.ModelSerializer):
    """
    Serializer for the ProductRecommendation model.
    """
    class Meta:
        model = ProductRecommendation
        fields = [
            'id',
            'product',
            'frequently_bought_with',
            'support',
            'confidence',
            'lift',
            'created_at',
        ]


class RecommendedProductInfoSerializer(serializers.Serializer):
    """
    Serializer for the resolved catalog product matching the recommendation.
    """
    product_id = serializers.CharField()
    product_name = serializers.CharField()
    sku = serializers.CharField(allow_null=True)
    selling_price = serializers.IntegerField(allow_null=True)
    base_price = serializers.IntegerField(allow_null=True)
    category_id = serializers.CharField(allow_null=True)
    category_name = serializers.CharField(allow_null=True)
    gender = serializers.CharField(allow_null=True)
    color = serializers.CharField(allow_null=True)
    size = serializers.CharField(allow_null=True)
    material = serializers.CharField(allow_null=True)
    is_active = serializers.BooleanField()


class RecommendationItemSerializer(serializers.Serializer):
    """
    Serializer for each recommendation entry returned by the API.
    Combines rule metrics and recommended catalog product details.
    """
    id = serializers.IntegerField(allow_null=True)
    product = serializers.CharField()
    frequently_bought_with = serializers.CharField()
    support = serializers.FloatField(allow_null=True)
    confidence = serializers.FloatField(allow_null=True)
    lift = serializers.FloatField(allow_null=True)
    created_at = serializers.DateTimeField(allow_null=True, required=False)
    recommended_product = RecommendedProductInfoSerializer(allow_null=True, required=False)
    matching_products = RecommendedProductInfoSerializer(many=True, required=False)


class ProductRecommendationsResponseSerializer(serializers.Serializer):
    """
    Serializer for the complete recommendations endpoint response.
    """
    product_id = serializers.CharField()
    product_name = serializers.CharField()
    category_id = serializers.CharField(allow_null=True, required=False)
    total_recommendations = serializers.IntegerField()
    recommendations = RecommendationItemSerializer(many=True)
