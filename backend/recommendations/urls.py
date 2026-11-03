from django.urls import path
from .views import (
    ProductRecommendationView,
    PersonalizedRecommendationView,
    SmartBudgetOutfitView,
    CustomerCoinsView,
    RedeemCoinsView,
    SpinRewardsView,
)

app_name = 'recommendations'

urlpatterns = [
    path('personalized/', PersonalizedRecommendationView.as_view(), name='personalized-recommendations'),
    path('spin-reward/', SpinRewardsView.as_view(), name='spin-reward'),
    path('smart-budget/coins/', CustomerCoinsView.as_view(), name='smart-budget-coins'),
    path('smart-budget/redeem-coins/', RedeemCoinsView.as_view(), name='smart-budget-redeem-coins'),
    path('smart-budget/', SmartBudgetOutfitView.as_view(), name='smart-budget-outfits'),
    path('<str:product_id>/', ProductRecommendationView.as_view(), name='product-recommendations'),
]
