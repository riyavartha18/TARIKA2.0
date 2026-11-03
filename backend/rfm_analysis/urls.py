"""URL routes for the RFM module, mounted under /api/ by config.urls."""

from django.urls import path

from . import views

app_name = 'rfm_analysis'

urlpatterns = [
    # ---- Admin analytics ----
    path('analytics/rfm/run', views.RfmRunView.as_view(), name='rfm-run'),
    path('analytics/rfm/recalculate', views.RfmRecalculateView.as_view(),
         name='rfm-recalculate'),
    path('analytics/rfm/incremental-refresh', views.RfmIncrementalRefreshView.as_view(),
         name='rfm-incremental-refresh'),
    path('analytics/rfm/results', views.RfmResultsView.as_view(), name='rfm-results'),
    path('analytics/rfm/summary', views.RfmSummaryView.as_view(), name='rfm-summary'),
    # The heavier per-cluster profiles / ambiguity report / segment mix, read by
    # the dashboard after it has already painted the KPIs and the cluster bars.
    path('analytics/rfm/analytics', views.RfmAnalyticsDetailView.as_view(),
         name='rfm-analytics-detail'),
    path('analytics/rfm/segments', views.RfmSegmentsView.as_view(), name='rfm-segments'),
    path('analytics/rfm/segments/<str:segment>', views.RfmSegmentDetailView.as_view(),
         name='rfm-segment-detail'),

    # ---- K-Means++ (k=4) RFM clustering ----
    path('analytics/rfm/clusters/customers', views.RfmClusterCustomersView.as_view(),
         name='rfm-cluster-customers'),
    path('analytics/rfm/clusters', views.RfmClustersView.as_view(),
         name='rfm-clusters'),

    # ---- Admin campaign management ----
    # The customer groups a campaign may be aimed at: the four K-Means clusters
    # of the latest persisted clustering run. Listed before the id route so it
    # is never mistaken for a campaign id.
    path('campaigns/clusters/', views.CampaignClusterOptionsView.as_view(),
         name='campaign-clusters'),
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
