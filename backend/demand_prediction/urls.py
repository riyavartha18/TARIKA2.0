from django.urls import path
from demand_prediction.views import DemandPredictionAnalyticsView, SlowMovingInventoryView

app_name = 'demand_prediction'

urlpatterns = [
    path('analytics/', DemandPredictionAnalyticsView.as_view(), name='analytics'),
    path('slow-inventory/', SlowMovingInventoryView.as_view(), name='slow_inventory'),
]
