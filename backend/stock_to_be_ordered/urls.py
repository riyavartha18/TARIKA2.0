from django.urls import path
from stock_to_be_ordered.views import (
    StockToBeOrderedView,
    StockCategoriesView,
    ReplenishmentOrderView,
    HighDemandPreviewView,
    HighDemandOrderView,
    DemandPreviewView,
    DemandOrderView,
    ReplenishmentReceiveView,
    ReplenishmentOrderListView,
    ReplenishmentOrderDetailView,
)

app_name = 'stock_to_be_ordered'

urlpatterns = [
    path('', StockToBeOrderedView.as_view(), name='stock_forecast'),
    path('categories/', StockCategoriesView.as_view(), name='stock_categories'),
    # Replenishment ordering workflow
    path('order/', ReplenishmentOrderView.as_view(), name='replenishment-order'),
    path('high-demand/', HighDemandPreviewView.as_view(), name='high-demand-preview'),
    path('order-high-demand/', HighDemandOrderView.as_view(), name='high-demand-order'),
    # Tier-aware bulk actions (High / Medium / Low demand)
    path('demand-preview/', DemandPreviewView.as_view(), name='demand-preview'),
    path('demand-order/', DemandOrderView.as_view(), name='demand-order'),
    path('orders/', ReplenishmentOrderListView.as_view(), name='replenishment-orders'),
    path('orders/<str:po_key>/', ReplenishmentOrderDetailView.as_view(), name='replenishment-order-detail'),
    path('orders/<str:po_key>/receive/', ReplenishmentReceiveView.as_view(), name='replenishment-receive'),
]
