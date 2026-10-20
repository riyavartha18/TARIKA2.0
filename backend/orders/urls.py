from django.urls import path
from .views import CheckoutView, OrderDetailView, CustomerOrdersListView, CustomerOrderReturnView

app_name = 'orders'

urlpatterns = [
    path('', CustomerOrdersListView.as_view(), name='order-list'),
    path('checkout/', CheckoutView.as_view(), name='checkout'),
    path('<str:order_id>/', OrderDetailView.as_view(), name='order-detail'),
    path('<str:order_id>/return/', CustomerOrderReturnView.as_view(), name='order-return'),
    path('<str:order_id>/returns/', CustomerOrderReturnView.as_view(), name='order-returns'),
]
