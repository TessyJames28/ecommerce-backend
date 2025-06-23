from django.urls import path
from .views import (
    SellerKYCIDVerificationView, SellerSocialsView,
    SellerKYCProofOfAddressView, VerifiedSeller,
)


urlpatterns = [
    path("kyc/id-verification/", SellerKYCIDVerificationView.as_view(), name="seller_kyc"),
    path("kyc/proof-of-address/", SellerKYCProofOfAddressView.as_view(), name="seller_kyc_proof_of_address"),
    path("socials/", SellerSocialsView.as_view(), name="seller_socials"),
    path('seller-verified/', VerifiedSeller.as_view(), name='verified_seller'),
]