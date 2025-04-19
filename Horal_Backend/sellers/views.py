from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from .models import SellerKYC, SellerSocials
from .serializers import SellerKYCFirstScreenSerializer, SellerKYCProofOfAddressSerializer, SellerSocialsSerializer
from rest_framework.response import Response
from rest_framework import status

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
