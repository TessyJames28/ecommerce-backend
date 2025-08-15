from django.shortcuts import get_object_or_404
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from .models import SellerKYC, SellerSocials, KYCStatus
from .serializers import (
    SellerSocialsSerializer,
    SellerKYCAddressSerializer,
    SellerKYCCACSerializer,
    SellerKYCNINSerializer
)
from django.utils.timezone import now
from rest_framework.response import Response
from rest_framework import status
from products.utils import (
    IsSuperAdminPermission, BaseResponseMixin,
    StandardResultsSetPagination, product_models
)
from shops.models import Shop
from shops.serializers import ShopSerializer
from users.models import CustomUser


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
            print(f"nin: {nin_number}\nselfie_url: {selfie_url}\nuser_id: {user_id}")
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

        if success_status is True and verification_status == "Completed":
            kyc_nin.status = KYCStatus.VERIFIED
            kyc_nin.nin_verified = True
            kyc_nin.save(update_fields=['status', 'nin_verified'])
        
        elif success_status is False and verification_status == "Completed":
            kyc_nin.status = KYCStatus.FAILED
            kyc_nin.save(update_fields=["status"])

        # Cross-check seller name with kyc data
        try:
            seller = SellerKYC.objects.get(user__id=user_id)
            address = seller.address
            nin = seller.nin

            # Normalize name to facilitate loose match
            first_name_match = address.first_name.lower() == entity.get("first_name", "").lower()
            last_name_match = address.last_name.lower() == entity.get("last_name", "").lower()

            if not (first_name_match and last_name_match):
                nin.status = KYCStatus.FAILED
                nin.nin_verified = False
                nin.save(update_fields=['status', 'nin_verified'])
                seller.status = KYCStatus.FAILED
                seller.save(update_fields=["status"])

                return Response({
                    "status": "failed",
                    "status_code": status.HTTP_400_BAD_REQUEST,
                    "message": "KYC verification failed. Provided name does not match",
                    "data": SellerKYCNINSerializer(kyc_nin).data,
                    "dojah_response": payload
                }, status=status.HTTP_400_BAD_REQUEST)
            
        except SellerKYC.DoesNotExist:
            return self.get_response(
                status.HTTP_404_NOT_FOUND,
                "Seller KYC record not found"
            )

        return Response({
            "status": "success",
            "status_code": status.HTTP_201_CREATED,
            "message": "KYC verification completed",
            "data": SellerKYCNINSerializer(kyc_nin).data,
            "dojah_response": payload
        }, status=status.HTTP_201_CREATED)
        


class SellerAddressCreateView(GenericAPIView, BaseResponseMixin):
    """
    Class to handle the creation of seller address
    """
    serializer_class = SellerKYCAddressSerializer
    permission_classes = [IsAuthenticated]

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
                status.HTTP_400_BAD_REQUEST,
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
            "company_type": company_type
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

        # update seller profile and create shop
        user.is_seller = True
        user.save(update_fields=['is_seller'])

        try:
            kyc = SellerKYC.objects.get(user=user)
            address = kyc.address
        except SellerKYC.DoesNotExist:
            return self.get_response(
                status.HTTP_404_NOT_FOUND,
                "SellerKYC not found for this user"
            )
        print(address.business_name)
        shop, _ = Shop.objects.get_or_create(
            owner=kyc,
            defaults= {
                "name": f"{address.business_name}" if address.business_name else \
                    f"{user.full_name}'s shop",
                "location": f"{address.street}, {address.lga}, {address.landmark}, {address.state}"
            }
        )

        return Response({
            "status": "success",
            "status_code": status.HTTP_200_OK,
            "message": "KYC verification completed",
            "data": SellerKYCCACSerializer(kyc_cac).data,
            "dojah_response": payload
        })



class SellerSocialsView(GenericAPIView):
    """API endpoint for the seller's social media links"""
    serializer_class = SellerSocialsSerializer
    permission_classes = [IsAuthenticated]

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
    

class CreateShop(GenericAPIView):
    """
    API endpoints for the superadmins to create shop
    To use and create platform base products for sale.
    """
    serializer_class = ShopSerializer
    queryset = Shop.objects.all()
    permission_classes = [IsSuperAdminPermission]

    def post(self, request, *args, **kwargs):
        """
        A post method to create a shop by the superuser
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        response_data = {
            "status": "success",
            "status_code": status.HTTP_201_CREATED,
            "message": "Successfully created shop",
            "data": {
                "id": str(user.id),
                "owner_type": user.owner_type,
                "owner": user.owner,
                "name": user.name,
                "created_by_admin": user.created_by_admin,
                "location": user.location
            }
        }

        return Response(response_data, status=status.HTTP_201_CREATED)


class ShopManagementView(GenericAPIView, BaseResponseMixin):
    """
    API endpoints for superadmins to manage shops
    """
    serializer_class = ShopSerializer
    queryset = Shop.objects.all()
    permission_classes = [IsSuperAdminPermission]


    def get(self, request, *args, **kwargs):
        """Get all shops"""
        shops = self.get_queryset()
        serializer = self.get_serializer(shops, many=True)
        return self.get_response(
            status.HTTP_200_OK,
            "ALL shops retrieved successfully",
            serializer.data
        )
    

    def delete(self, request, pk, *args,**kwargs):
        """Delete a shop and all its products"""
        shop = get_object_or_404(Shop, pk=pk)
        shop.delete() # This will cascade delete all products belonging to the shop
        return Response({
            "status": "success",
            "status_code": status.HTTP_204_NO_CONTENT,
            "message": "Shop deleted successfully with all its products"
        })
    

class ShopProductListView(GenericAPIView, BaseResponseMixin):
    """
    API endpoint to list all products of a shop
    """ 
    permission_classes = [AllowAny]
    authentication_classes = []
    pagination_class = StandardResultsSetPagination

    def get(self, request, shop_id, *args, **kwargs):
        """Get all products of a shop"""
        shop = get_object_or_404(Shop, pk=shop_id)

        products_data = []

        for model, serializer_class, category_name in product_models:
            products = model.published.filter(shop=shop)
            if products.exists():
                serializer = serializer_class(products, many=True)
                for product_data in serializer.data:
                    product_data['category_name'] = category_name
                    products_data.append(product_data)
                    print(products_data)

        page = self.paginate_queryset(products_data)
        if page is not None:
            paginated_response = self.get_paginated_response(products_data)
            paginated_response.data["status"] = "success"
            paginated_response.data["status_code"] = status.HTTP_200_OK
            paginated_response.data["message"] = "Shop products retrieved successfully"
        
        return paginated_response
