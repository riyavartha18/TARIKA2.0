from django.urls import path
from stock_to_be_ordered.views import StockToBeOrderedView, StockCategoriesView

app_name = 'stock_to_be_ordered'

urlpatterns = [
    path('', StockToBeOrderedView.as_view(), name='stock_forecast'),
    path('categories/', StockCategoriesView.as_view(), name='stock_categories'),
]
