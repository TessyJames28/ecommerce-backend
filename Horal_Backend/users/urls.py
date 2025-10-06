from django.urls import path
from .views import(
    RegisterUserView,
    AgentRegisterUserView,
    UserLoginView,
    UserLogoutView,
    GoogleLoginView,
    PasswordResetRequestView,
    VerifyOTPView,
    PasswordResetConfirmView,
    CreateLocationView,
    SingleLocationView,
    LocationUpdateDeleteView,
    ConfirmRegistrationOTPView,
    CookieTokenRefreshView,
    ResendRegistrationOTPView,
    get_csrf_token,
)
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView
from django.conf import settings

urlpatterns = [
    path("register/", RegisterUserView.as_view(), name="register"),
    path("agent/register/", AgentRegisterUserView.as_view(), name="agent-registration"),
    path("confirm-registration/", ConfirmRegistrationOTPView.as_view(), name='confirm-registration'),
    path("resend-registration-otp/", ResendRegistrationOTPView.as_view(), name='resend-registration-otp'),
    path("login/", UserLoginView.as_view(), name="login"),
    path("google-login/", GoogleLoginView.as_view(), name="google_login"),
    path("logout/", UserLogoutView.as_view(), name="logout"),
    path("token/verify/", TokenVerifyView.as_view(), name="token_verify"),
    path("token/refresh/", CookieTokenRefreshView.as_view(), name="token_refresh"),
    path('password-reset/request/', PasswordResetRequestView.as_view(), name='password-reset-request'),
    path('password-reset/verify-otp/', VerifyOTPView.as_view(), name='password-reset-verify-otp'),
    path('password-reset/confirm/', PasswordResetConfirmView.as_view(), name='password-reset-confirm'),
    path('location/add/', CreateLocationView.as_view(), name="user_location"),
    path('location/<uuid:pk>/view/', SingleLocationView.as_view(), name="single_user_location"),
    path('location/<uuid:pk>/', LocationUpdateDeleteView.as_view(), name="location_update_delete"),
    path('get-csrf-token/', get_csrf_token, name="get-csrf-token"),
    
]

