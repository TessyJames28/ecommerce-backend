from django.shortcuts import get_object_or_404
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from .models import SellerKYC, SellerSocials
from .serializers import SellerKYCFirstScreenSerializer, SellerKYCProofOfAddressSerializer, SellerSocialsSerializer
from rest_framework.response import Response
from rest_framework import status
from users.models import CustomUser
from products.utility import IsSuperAdminPermission, BaseResponseMixin
from .models import Shop
from .serializers import ShopSerializer

# Create your views here.
class SellerKYCIDVerificationView(GenericAPIView):
    """API endpoint for the first screen of KYC"""
    serializer_class = SellerKYCFirstScreenSerializer
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        """Handle the KYC submission"""
        serializer = self.get_serializer(data=request.data)
        serializer.context['request'] = request
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        response_data = {
            "status": "success",
            "status_code": 201,
            "message": "KYC submitted successfully",
            "data": serializer.data
        }
        return Response(response_data, status=status.HTTP_201_CREATED)
    

    def patch(self, request, *args, **kwargs):
        """Handle the KYC update"""
        try:
            kyc_instance = SellerKYC.objects.get(user=request.user)
        except SellerKYC.DoesNotExist:
            return Response({
                "status": "failed",
                "message": "KYC instance does not exist."
            }, status=status.HTTP_404_NOT_FOUND)
        
        serializer = self.get_serializer(kyc_instance, data=request.data, partial=True)
        serializer.context['request'] = request #Set the request context for the serializer
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        response_data = {
            "status": "success",
            "status_code": 200,
            "message": "KYC updated successfully",
            "data": serializer.data
        }
        return Response(response_data, status=status.HTTP_200_OK)
    

class SellerKYCProofOfAddressView(GenericAPIView):
    """API endpoint for the proof of address screen of KYC"""
    serializer_class = SellerKYCProofOfAddressSerializer
    permission_classes = [IsAuthenticated]

    def patch(self, request, *args, **kwargs):
        """Handle the proof of address update"""
        try:
            kyc_instance = SellerKYC.objects.get(user=request.user)
        except SellerKYC.DoesNotExist:
            return Response({
                "status": "failed",
                "message": "KYC instance does not exist."
            }, status=status.HTTP_404_NOT_FOUND)
        
        serializer = self.get_serializer(kyc_instance, data=request.data, partial=True)
        serializer.context['request'] = request #Set the request context for the serializer
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        response_data = {
            "status": "success",
            "status_code": 200,
            "message": "Proof of address updated successfully",
            "data": serializer.data
        }
        return Response(response_data, status=status.HTTP_200_OK)
    

class SellerSocialsView(GenericAPIView):
    """API endpoint for the seller's social media links"""
    serializer_class = SellerSocialsSerializer
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        """Handle the creation of social media links"""
        serializer = self.get_serializer(data=request.data)
        serializer.context['request'] = request #Set the request context for the serializer
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        response_data = {
            "status": "success",
            "status_code": 201,
            "message": "Social media links saved",
            "data": serializer.data
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
    

class VerifiedSeller(GenericAPIView):
    """API endpoint that handles seller verification once KYC is passed"""
    permission_classes = [IsAuthenticated]
    serializer_class = ShopSerializer

    def post(self, request, *args, **kwargs):
        user = request.user

        # user = CustomUser.objects.get(id=user)

        if user.is_seller:
            return Response(
                {"detail": "Already a seller."}
            )
        
        # Get or create SellerKYC record
        kyc, _ = SellerKYC.objects.get_or_create(user=user)
        kyc.is_verified = True
        kyc.save()

        # Update user
        user.is_seller = True
        user.save()

        # Create default shop
        shop = Shop.objects.create(
            owner = kyc,
            name = f"{user.full_name}'s Shop",
            location=kyc.country
        )

        return Response(
            {
                "message": "Seller account activated and shop created successfully",
                "shop": self.get_serializer(shop).data
            },
            status=status.HTTP_201_CREATED
        )
    

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