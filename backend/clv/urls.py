"""URL routes for the CLV module, mounted under /api/clv/ by config.urls."""

from django.urls import path

from . import views

app_name = 'clv'

urlpatterns = [
    path('summary', views.ClvSummaryView.as_view(), name='clv-summary'),
    path('customers', views.ClvCustomersView.as_view(), name='clv-customers'),
    path('customers/<str:customer_id>', views.ClvCustomerDetailView.as_view(),
         name='clv-customer-detail'),
    path('cohorts', views.ClvCohortsView.as_view(), name='clv-cohorts'),
    path('segments', views.ClvSegmentsView.as_view(), name='clv-segments'),
    path('recalculate', views.ClvRecalculateView.as_view(), name='clv-recalculate'),
]
