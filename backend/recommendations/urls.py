from django.urls import path
from .views import (
    ProductRecommendationView,
    PersonalizedRecommendationView,
    SmartBudgetOutfitView,
)

app_name = 'recommendations'

urlpatterns = [
    path('personalized/', PersonalizedRecommendationView.as_view(), name='personalized-recommendations'),
    path('smart-budget/', SmartBudgetOutfitView.as_view(), name='smart-budget-outfits'),
    path('<str:product_id>/', ProductRecommendationView.as_view(), name='product-recommendations'),
]
