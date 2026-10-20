from django.urls import path
from .views import ProductRecommendationView

app_name = 'recommendations'

urlpatterns = [
    path('<str:product_id>/', ProductRecommendationView.as_view(), name='product-recommendations'),
]
