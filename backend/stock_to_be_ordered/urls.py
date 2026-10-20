from django.urls import path
from stock_to_be_ordered.views import StockToBeOrderedView

app_name = 'stock_to_be_ordered'

urlpatterns = [
    path('', StockToBeOrderedView.as_view(), name='stock_forecast'),
]
