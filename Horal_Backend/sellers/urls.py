from django.urls import path
from .views import (
    SellerKYCIDVerificationView, SellerSocialsView,
    SellerKYCProofOfAddressView, VerifiedSeller,
    ShopManagementView, CreateShop
)
from django.conf.urls.static import static
from django.conf import settings


urlpatterns = [
    path("kyc/id-verification/", SellerKYCIDVerificationView.as_view(), name="seller_kyc"),
    path("kyc/proof-of-address/", SellerKYCProofOfAddressView.as_view(), name="seller_kyc_proof_of_address"),
    path("socials/", SellerSocialsView.as_view(), name="seller_socials"),
    path('seller-verified/', VerifiedSeller.as_view(), name='verified_seller'),

    # Shop management (superadmin only)
    path('shop/', ShopManagementView.as_view(), name='shop-list'),
    path('shop/create/', CreateShop.as_view(), name="create-shop"),
    # superadmin can delete the shop
    path('shop/<uuid:pk>/', ShopManagementView.as_view(), name='shop-detail'),
    
]