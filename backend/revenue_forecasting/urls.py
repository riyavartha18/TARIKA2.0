from django.urls import path
from revenue_forecasting.views import RevenueForecastView

app_name = 'revenue_forecasting'

urlpatterns = [
    path('', RevenueForecastView.as_view(), name='revenue_forecast'),
]
