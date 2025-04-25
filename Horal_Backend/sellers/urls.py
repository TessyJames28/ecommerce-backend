from django.urls import path
from .views import SellerKYCIDVerificationView, SellerSocialsView, SellerKYCProofOfAddressView
from django.conf.urls.static import static
from django.conf import settings


urlpatterns = [
    path("kyc/id-verification/", SellerKYCIDVerificationView.as_view(), name="seller_kyc"),
    path("kyc/proof-of-address/", SellerKYCProofOfAddressView.as_view(), name="seller_kyc_proof_of_address"),
    path("socials/", SellerSocialsView.as_view(), name="seller_socials"),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)