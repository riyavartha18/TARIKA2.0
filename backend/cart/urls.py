from django.urls import path
from .views import CartView, CartItemDetailView, CartClearView

app_name = 'cart'

urlpatterns = [
    path('', CartView.as_view(), name='cart-summary'),
    path('clear/', CartClearView.as_view(), name='cart-clear'),
    path('<str:product_id>/', CartItemDetailView.as_view(), name='cart-item-detail'),
]
