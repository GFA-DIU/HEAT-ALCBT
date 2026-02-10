from django.urls import path
from .views import update_profile, verify_email, resend_confirmation_email

urlpatterns = [
    path('update/', update_profile, name='update_profile'),
    path('verify-email/', verify_email, name='verify_email'),
    path('resend-confirmation/', resend_confirmation_email, name='resend_confirmation_email'),
]