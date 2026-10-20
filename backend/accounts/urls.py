from django.urls import path
from accounts.views import (
    CustomerRegisterView,
    LoginView,
    LogoutView,
    MeView,
    AdminCreateStaffView
)

app_name = 'accounts'

urlpatterns = [
    path('register/', CustomerRegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('me/', MeView.as_view(), name='me'),
    path('staff/create/', AdminCreateStaffView.as_view(), name='staff-create'),
]
