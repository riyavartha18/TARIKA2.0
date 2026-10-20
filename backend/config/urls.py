"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', include('myapp.urls'))
Class-based views
    1. Add an import:  from other_app import views
    2. Add a URL to urlpatterns:  path('', Home.as_view())
Including another URLconf
    1. Import the include() function: from django.urls import include, path
"""

from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('accounts.urls')),
    path('api/catalog/', include('catalog.urls')),
    path('api/warehouse/', include('warehouse.urls')),
    path('api/wishlist/', include('cart.urls_wishlist')),
    path('api/cart/', include('cart.urls')),
    path('api/bag/', include(('cart.urls', 'bag'), namespace='bag')),
    path('api/orders/', include(('orders.urls', 'orders'), namespace='orders')),
    path('api/admin/', include(('admin.urls', 'admin_module'), namespace='admin_module')),
    path('api/delivery/', include(('delivery.urls', 'delivery'), namespace='delivery')),
    path(
        'api/demand-prediction/',
        include(
            ('demand_prediction.urls', 'demand_prediction'),
            namespace='demand_prediction'
        )
    ),
    path(
        'api/stock-to-be-ordered/',
        include(
            ('stock_to_be_ordered.urls', 'stock_to_be_ordered'),
            namespace='stock_to_be_ordered'
        )
    ),
    path(
        'api/revenue-forecasting/',
        include(
            ('revenue_forecasting.urls', 'revenue_forecasting'),
            namespace='revenue_forecasting'
        )
    ),
    path(
        'api/recommendations/',
        include(
            ('recommendations.urls', 'recommendations'),
            namespace='recommendations'
        )
    ),
]

# Reload URLconf: registered warehouse app routes