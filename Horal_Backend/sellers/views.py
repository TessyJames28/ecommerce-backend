from django.shortcuts import get_object_or_404
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from .models import SellerKYC, SellerSocials, KYCStatus, SellerKYCNIN
from .serializers import (
    SellerSocialsSerializer,
    SellerKYCAddressSerializer,
    SellerKYCCACSerializer,
    SellerKYCNINSerializer,
    SellerSerializer
)
from django.utils.timezone import now
from rest_framework.response import Response
from rest_framework import status
from users.authentication import CookieTokenAuthentication
from products.utils import (
    IsSuperAdminPermission, BaseResponseMixin,
    StandardResultsSetPagination, product_models
)
from shops.models import Shop
from shops.serializers import ShopSerializer
from users.models import CustomUser
from django.db.models.signals import post_save
from .signals import trigger_related_kyc_verification, notify_kyc_info_completed, notify_kyc_status_change


# Create your views here.
class KYCIDVerificationWebhook(GenericAPIView, BaseResponseMixin):
    """Webhook that receives users NIN verification with slefie"""
    serializer_class = SellerKYCNINSerializer


    def post(self, request, *args, **kwargs):
        """Handle NIN and Selfie image KYC verification"""
        # Extract data from request
        payload = request.data

        # Basic validation
        if payload.get("verification_type") != "NIN":
            return self.get_response(
                status.HTTP_400_BAD_REQUEST,
                "Invalid verification type"
            )

        # Extract relevant fields        
        nin_number = payload.get("value")
        selfie_url = payload.get("selfie_url")
        user_id = payload.get("metadata", {}).get("user_id")
        verification_status = payload.get("verification_status")
        success_status = payload.get("status")
        entity = payload.get("data", {}) \
            .get("government_data", {}) \
            .get("data", {}) \
            .get("nin", {}) \
            .get("entity", {})

        if not (nin_number and selfie_url and user_id):
            return self.get_response(
                status.HTTP_400_BAD_REQUEST,
                "Missing required fields: 'nin', 'selfie_url', or 'user_id'"
            )

        # Create and update NIN entry
        data = {
            "nin": nin_number,
            "selfie": selfie_url
        }

        try:
            user = CustomUser.objects.get(id=user_id)
        except CustomUser.DoesNotExist:
            return self.get_response(
                status.HTTP_404_NOT_FOUND,
                "User not found"
            )


        serializer = self.get_serializer(data=data, context={"user": user})
        serializer.is_valid(raise_exception=True)
        kyc_nin = serializer.create_or_update(serializer.validated_data)

        post_save.connect(receiver=notify_kyc_info_completed, sender=SellerKYC)
        post_save.connect(receiver=notify_kyc_status_change, sender=SellerKYC)
        post_save.connect(receiver=trigger_related_kyc_verification, sender=SellerKYCNIN)
        if success_status is True and verification_status == "Completed":
            try:
                seller = SellerKYC.objects.get(user__id=user_id)
                address = seller.address

                # Normalize name to facilitate loose match
                first_name_match = address.first_name.lower() == entity.get("first_name", "").lower()
                last_name_match = address.last_name.lower() == entity.get("last_name", "").lower()

                if not (first_name_match and last_name_match):
                    kyc_nin.status = KYCStatus.FAILED
                    kyc_nin.nin_verified = False
                    kyc_nin.save(update_fields=['status', 'nin_verified'])

                    return Response({
                        "status": "ok",
                        "message": "KYC verification failed. Provided name does not match",
                    }, status=status.HTTP_200_OK)
                
            except SellerKYC.DoesNotExist:
                return Response({
                    "status": "ok",
                    "message": "Seller KYC record not found",
                },status=status.HTTP_200_OK)
            
            kyc_nin.status = KYCStatus.VERIFIED
            kyc_nin.nin_verified = True
            kyc_nin.save(update_fields=['status', 'nin_verified'])
            
            return Response({
                "status": "success",
                "message": "KYC verification completed",
            }, status=status.HTTP_200_OK)

        elif success_status is False and verification_status == "Completed":
            kyc_nin.status = KYCStatus.FAILED
            kyc_nin.nin_verified = False
            kyc_nin.save(update_fields=["status", "nin_verified"])# Cross-check seller name with kyc data

            return Response({
                "status": "ok",
                "message": "KYC verification failed.",
            }, status=status.HTTP_200_OK)
        


class SellerAddressCreateView(GenericAPIView, BaseResponseMixin):
    """
    Class to handle the creation of seller address
    """
    serializer_class = SellerKYCAddressSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [CookieTokenAuthentication]

    def post(self, request, *args, **kwargs):
        """Method to create or update seller address"""

        serializer = SellerKYCAddressSerializer(
            data=request.data,
            context={'request': request}
        )

        serializer.is_valid(raise_exception=True)
        address = serializer.create_or_update(serializer.validated_data)

        return self.get_response(
            status.HTTP_201_CREATED,
            "Seller address created successfully",
            SellerKYCAddressSerializer(address).data
        )


    def patch(self, request, *args, **kwargs):
        """Method to partially update seller address"""
        serializer = self.get_serializer(
            user=request.user,
            data=request.data,
            partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return self.get_response(
            status.HTTP_200_OK,
            "User address updated successfully"
        )

class DojahCACWebhook(GenericAPIView, BaseResponseMixin):
    """
    Webhook to handle CAC verification and update from dojah
    """
    serializer_class = SellerKYCCACSerializer


    def post(self, request, *args, **kwargs):
        """Post method to handle cac verification webhook"""
        payload = request.data

        # Basic verification
        verification_type = payload.get("metadata", {}).get("verification_type")
        if verification_type != "cac":
            return self.get_response(
                status.HTTP_200_OK,
                "Invalid verification type"
            )
        
        # Extract relevant values
        rc_number = payload.get("verification_value")
        verification_status = payload.get("verification_status")
        user_id = payload.get("metadata", {}).get("user_id")
        success_status = payload.get("status")
        company_type = payload.get("data", {}) \
            .get("business_data", {}).get("business_type")
        business_name = payload.get("data", {}).get("business_data", {}).get("business_name")

        
        if not (rc_number and company_type):
            return self.get_response(
                status.HTTP_400_BAD_REQUEST,
                "The payload must include 'rc_number and 'business_type"
            )
        
        data = {
            "rc_number": rc_number,
            "company_type": company_type,
            "company_name": business_name
        }

        try:
            user = CustomUser.objects.get(id=user_id)
        except CustomUser.DoesNotExist:
            return self.get_response(
                status.HTTP_404_NOT_FOUND,
                "User not found"
            )

        serializer = self.get_serializer(data=data, context={"user": user})
        serializer.is_valid(raise_exception=True)
        kyc_cac = serializer.create_or_update(serializer.validated_data)

        if success_status is True and verification_status == "Completed":
            kyc_cac.status = KYCStatus.VERIFIED
            kyc_cac.company_name = business_name
            kyc_cac.cac_verified = True
            kyc_cac.save(update_fields=['status', 'cac_verified', 'company_name'])
        elif success_status is False and verification_status == "Completed":
            kyc_cac.status = KYCStatus.FAILED
            kyc_cac.save(update_fields=['status'])

        return Response({
            "status": "ok",
            "message": "CAC verification successful.",
        }, status=status.HTTP_200_OK)



class SellerSocialsView(GenericAPIView):
    """API endpoint for the seller's social media links"""
    serializer_class = SellerSocialsSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [CookieTokenAuthentication]

    def post(self, request, *args, **kwargs):
        """Handle the creation of social media links"""
        serializer = self.get_serializer(data=request.data)
        serializer.context['request'] = request #Set the request context for the serializer
        serializer.is_valid(raise_exception=True)
        socials = serializer.create_or_update(serializer.validated_data)
        
        response_data = {
            "status": "success",
            "status_code": 201,
            "message": "Social media links saved",
            "data": SellerSocialsSerializer(socials).data
        }
        return Response(response_data, status=status.HTTP_201_CREATED)
    

    def patch(self, request, *args, **kwargs):
        """Handle the update of social media links"""
        try:
            socials_instance = SellerSocials.objects.get(user=request.user)
        except SellerSocials.DoesNotExist:
            return Response({
                "status": "failed",
                "message": "Social media links instance does not exist."
            }, status=status.HTTP_404_NOT_FOUND)
        
        serializer = self.get_serializer(socials_instance, data=request.data, partial=True)
        serializer.context['request'] = request
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({
            "status": "success",
            "status_code": 200,
            "message": "Social media links updated successfully",
            "data": serializer.data
        }, status=status.HTTP_200_OK)
    

class GetSellerKYCView(GenericAPIView, BaseResponseMixin):
    """Get sellers kyc"""
    permission_classes = [IsAuthenticated]
    serializer_class = SellerSerializer

    def get(self, request, *args, **kwargs):
        """Method to retrieve sellers kyc"""
        try:
            kyc = SellerKYC.objects.get(user=request.user)
        except SellerKYC.DoesNotExist:
            return self.get_response(
                status.HTTP_404_NOT_FOUND,
                "There is no kyc for this seller"
            )
        
        serializer = self.get_serializer(kyc)

        return self.get_response(
            status.HTTP_200_OK,
            "Seller kyc retrieved successfully",
            serializer.data
        )
    