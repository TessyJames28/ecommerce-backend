from django.urls import path
from .views import(
    RegisterUserView,
    UserLoginView,
    UserLogoutView,
    GoogleLoginView,
    PasswordResetRequestView,
    VerifyOTPView,
    PasswordResetConfirmView,
    CreateLocationView,
    SingleLocationView,
    LocationUpdateDeleteView
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
    path('location/add/', CreateLocationView.as_view(), name="user_location"),
    path('location/<uuid:pk>/view/', SingleLocationView.as_view(), name="single_user_location"),
    path('location/<uuid:pk>/', LocationUpdateDeleteView.as_view(), name="location_update_delete"),

]


# Only add in DEBUG mode
if settings.DEBUG:
    from .views import OTPTestingView
    urlpatterns += [
        path('dev/get-otp/', OTPTestingView.as_view(), name='get-otp-for-testing'),
    ]