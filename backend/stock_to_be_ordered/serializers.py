"""
serializers.py
--------------
DRF serializers for the Stock to Be Ordered API response.
"""
from rest_framework import serializers


class PredictionItemSerializer(serializers.Serializer):
    product_key = serializers.IntegerField()
    product_id = serializers.CharField(allow_null=True)
    product_name = serializers.CharField(allow_null=True)
    category_name = serializers.CharField(allow_null=True)
    predicted_demand = serializers.IntegerField(allow_null=True)
    status = serializers.CharField()
    message = serializers.CharField(allow_null=True)
    n_training_samples = serializers.IntegerField()


class StockForecastResponseSerializer(serializers.Serializer):
    latest_historical_month = serializers.CharField()
    forecast_month = serializers.CharField()
    latest_period_str = serializers.CharField()
    forecast_period_str = serializers.CharField()
    total_products = serializers.IntegerField()
    forecasted_products = serializers.IntegerField()
    insufficient_data_products = serializers.IntegerField()
    predictions = PredictionItemSerializer(many=True)
