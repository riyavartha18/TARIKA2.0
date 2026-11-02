from django.urls import path
from .views import (
    WardrobeItemListCreateView,
    WardrobeItemDetailView,
    WardrobeToggleDisplayView,
    WardrobeReprocessView,
    WardrobeDeleteAllView,
    WardrobeOrderImportView,
    ProductWardrobeMatchesView,
    WardrobeCompleteLookView,
    WardrobeOutfitListCreateView,
    WardrobeSuggestOutfitView,
    WardrobeCollectionListCreateView,
    WardrobeCollectionDetailView,
    WardrobeMediaServeView,
    WardrobeConfirmParsedItemsView
)

app_name = 'digital_wardrobe'

urlpatterns = [
    path('items/', WardrobeItemListCreateView.as_view(), name='items-list-create'),
    path('items/confirm-parsed-items/', WardrobeConfirmParsedItemsView.as_view(), name='confirm-parsed-items'),
    path('confirm-parsed-items/', WardrobeConfirmParsedItemsView.as_view(), name='confirm-parsed-items-root'),
    path('items/delete-all/', WardrobeDeleteAllView.as_view(), name='items-delete-all'),
    path('items/<int:pk>/', WardrobeItemDetailView.as_view(), name='item-detail'),
    path('items/<int:pk>/toggle-display/', WardrobeToggleDisplayView.as_view(), name='item-toggle-display'),
    path('items/<int:pk>/reprocess/', WardrobeReprocessView.as_view(), name='item-reprocess'),
    path('items/<int:pk>/complete-look/', WardrobeCompleteLookView.as_view(), name='item-complete-look'),
    path('import-orders/', WardrobeOrderImportView.as_view(), name='import-orders'),
    path('matches/<str:product_key>/', ProductWardrobeMatchesView.as_view(), name='product-matches'),
    path('outfits/', WardrobeOutfitListCreateView.as_view(), name='outfits-list-create'),
    path('outfits/suggest/', WardrobeSuggestOutfitView.as_view(), name='outfits-suggest'),
    path('collections/', WardrobeCollectionListCreateView.as_view(), name='collections-list-create'),
    path('collections/<int:pk>/', WardrobeCollectionDetailView.as_view(), name='collection-detail'),
    path('media-serve/', WardrobeMediaServeView.as_view(), name='media-serve'),
]
