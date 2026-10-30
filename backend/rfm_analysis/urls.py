"""URL routes for the RFM module, mounted under /api/ by config.urls."""

from django.urls import path

from . import views

app_name = 'rfm_analysis'

urlpatterns = [
    # ---- Admin analytics ----
    path('analytics/rfm/run', views.RfmRunView.as_view(), name='rfm-run'),
    path('analytics/rfm/summary', views.RfmSummaryView.as_view(), name='rfm-summary'),
    path('analytics/rfm/segments', views.RfmSegmentsView.as_view(), name='rfm-segments'),
    path('analytics/rfm/segments/<str:segment>', views.RfmSegmentDetailView.as_view(),
         name='rfm-segment-detail'),

    # ---- Admin campaign management ----
    path('campaigns/', views.CampaignListCreateView.as_view(), name='campaign-list-create'),
    path('campaigns/<int:campaign_id>/', views.CampaignDetailView.as_view(),
         name='campaign-detail'),
    path('campaigns/<int:campaign_id>/status/', views.CampaignStatusView.as_view(),
         name='campaign-status'),

    # ---- Customer offers ----
    path('customer/me/offers', views.CustomerOffersView.as_view(), name='customer-offers'),
    path('customer/me/coupons', views.CustomerCouponsView.as_view(), name='customer-coupons'),

    # ---- Checkout coupon validation ----
    path('checkout/validate-coupon', views.CheckoutCouponValidateView.as_view(),
         name='checkout-validate-coupon'),
]
