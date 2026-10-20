from django.urls import path
from .views import (
    CategoryListView,
    ProductListView,
    ProductDetailView,
    ProductReviewsView,
    NewArrivalsView,
    TrendingView,
    SaleView,
    GroupedCategoryProductsView
)

app_name = 'catalog'

urlpatterns = [
    path('categories/', CategoryListView.as_view(), name='category-list'),
    path('grouped-products/', GroupedCategoryProductsView.as_view(), name='grouped-products'),
    path('products/', ProductListView.as_view(), name='product-list'),
    path('products/<str:product_id>/', ProductDetailView.as_view(), name='product-detail'),
    path('products/<str:product_id>/reviews/', ProductReviewsView.as_view(), name='product-reviews'),
    path('new-arrivals/', NewArrivalsView.as_view(), name='new-arrivals'),
    path('trending/', TrendingView.as_view(), name='trending'),
    path('sale/', SaleView.as_view(), name='sale'),
]
