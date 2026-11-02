from django.urls import path
from .views import WardrobeListCreateView, WardrobeDetailView

app_name = 'wardrobe'

urlpatterns = [
    path('', WardrobeListCreateView.as_view(), name='wardrobe-list-create'),
    path('<int:pk>/', WardrobeDetailView.as_view(), name='wardrobe-detail'),
]
