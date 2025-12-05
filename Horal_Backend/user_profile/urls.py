from django.urls import path
from .views import (
    AllUserProfileView, GetUserProfileView,
    ConfirmEmailUpdateOTPView, ResendOTPView
)


urlpatterns = [
    path("", GetUserProfileView.as_view(), name="user-profile-detail"),
    path("all/", AllUserProfileView.as_view(), name="All-user-profile"),
    path("confirm-otp/", ConfirmEmailUpdateOTPView.as_view(), name="email-update-otp-confirmation"),
    path("resend-otp/", ResendOTPView.as_view(), name="resend-update-data-otp"),

]