from django.urls import path
from demand_prediction.views import (
    DemandPredictionAnalyticsView,
    DemandPredictionProductsView,
    CategoryFilterView,
    SlowMovingInventoryView,
)

app_name = 'demand_prediction'

urlpatterns = [
    path('analytics/', DemandPredictionAnalyticsView.as_view(), name='analytics'),
    path('products/', DemandPredictionProductsView.as_view(), name='products'),
    path('categories/', CategoryFilterView.as_view(), name='categories'),
    path('slow-inventory/', SlowMovingInventoryView.as_view(), name='slow_inventory'),
]
