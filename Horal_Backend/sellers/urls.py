from django.urls import path
from .views import (
    SellerSocialsView, SellerAddressCreateView,
    DojahCACWebhook, KYCIDVerificationWebhook,
    GetSellerKYCView
)


urlpatterns = [
    path("webhook/nin/", KYCIDVerificationWebhook.as_view(), name="seller_kyc"),
    path("webhook/cac/", DojahCACWebhook.as_view(), name="cac_webhook"),
    path('kyc/address/', SellerAddressCreateView.as_view(), name="seller_address"),
    path("kyc/socials/", SellerSocialsView.as_view(), name="seller_socials"),
    path("", GetSellerKYCView.as_view(), name="get-seller-kyc"),
    
]