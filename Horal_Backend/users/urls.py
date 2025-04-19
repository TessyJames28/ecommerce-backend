from django.urls import path
from .views import(
    RegisterUserView,
    UserLoginView,
    UserLogoutView,
    GoogleLoginView,
    PasswordResetRequestView,
    VerifyOTPView,
    PasswordResetConfirmView,
)
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView
from django.conf import settings

urlpatterns = [
    path("register/", RegisterUserView.as_view(), name="register"),
    path("login/", UserLoginView.as_view(), name="login"),
    path("google-login/", GoogleLoginView.as_view(), name="google_login"),
    path("logout/", UserLogoutView.as_view(), name="logout"),
    path("token/verify/", TokenVerifyView.as_view(), name="token_verify"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path('password-reset/request/', PasswordResetRequestView.as_view(), name='password-reset-request'),
    path('password-reset/verify-otp/', VerifyOTPView.as_view(), name='password-reset-verify-otp'),
    path('password-reset/confirm/', PasswordResetConfirmView.as_view(), name='password-reset-confirm'),

]


# Only add in DEBUG mode
if settings.DEBUG:
    from .views import OTPTestingView
    urlpatterns += [
        path('dev/get-otp/', OTPTestingView.as_view(), name='get-otp-for-testing'),
    ]