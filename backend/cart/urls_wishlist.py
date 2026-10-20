from django.urls import path
from .views import WishlistListView, WishlistRemoveView

app_name = 'wishlist'

urlpatterns = [
    path('', WishlistListView.as_view(), name='wishlist-list'),
    path('<str:product_id>/', WishlistRemoveView.as_view(), name='wishlist-remove'),
]
