from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from rest_framework import status
from .serializers import ProfileSerializer
from rest_framework.generics import GenericAPIView
from .models import Profile
from django.core.cache import cache
from notifications.utils import (
    generate_otp, store_otp,
    verify_registration_otp,
    safe_cache_set, safe_cache_get
)
from notifications.emails import (
    send_otp_email
)
from rest_framework import serializers
from rest_framework.permissions import AllowAny, IsAuthenticated
from products.views import BaseResponseMixin
from users.authentication import CookieTokenAuthentication
from products.utils import IsAdminOrSuperuser
import json

# Create your views here.
class GetUserProfileView(GenericAPIView):
    """
    View to retrieve the complete seller profile
    """
    serializer_class = ProfileSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [CookieTokenAuthentication]


    def get_profile(self):
        return get_object_or_404(Profile, user=self.request.user)

    def get(self, request, *args, **kwargs):
        try:
            profile = self.get_profile()

            serializer = self.get_serializer(profile)
            return Response({
                "status": "success",
                "message": "Profile retrieved successfully",
                "data": serializer.data
            }, status=status.HTTP_200_OK)
        except ValidationError as e:
            return Response({
                    "status": "error",
                    "message": f"{str(e)}",
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({
                    "status": "error",
                    "message": f"{str(e)}",
            }, status=status.HTTP_400_BAD_REQUEST)
        

    def patch(self, request, *args, **kwargs):
        try:
            profile = self.get_profile()
            data = request.data

            if "email" in data:
                return Response({
                    "status": "error",
                    "message": f"You are not allowed to change your email."
                }, status=status.HTTP_400_BAD_REQUEST)

            serializer = self.get_serializer(
                profile,
                data=data,
                partial=True  # Allow partial updates
            )
            
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response({
                "status": "success",
                "message": "Profile updated successfully",
                "data": serializer.data
            }, status=status.HTTP_200_OK)
        except ValidationError as e:
            detail = e.detail

            # If detail is a dict like {"message": ErrorDetail(...)}
            if isinstance(detail, dict):
                # Extract the first value
                msg = list(detail.values())[0]
                # If it's a list like ["msg"]
                if isinstance(msg, list):
                    msg = msg[0]
                return Response({
                    "status": "error",
                    "message": str(msg),
                }, status=400)

            # If detail is a list like ["msg"]
            if isinstance(detail, list) and len(detail):
                return Response({
                    "status": "error",
                    "message": str(detail[0]),
                }, status=400)

            # Fallback
            return Response({
                "status": "error",
                "message": str(e),
            }, status=400)
        except Exception as e:
            return Response({
                    "status": "error",
                    "message": f"{str(e)}.",
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        

    

class AllUserProfileView(GenericAPIView, BaseResponseMixin):
    """Retrieve all user profile admin"""
    queryset = Profile.objects.all()
    serializer_class = ProfileSerializer
    permission_classes = [IsAdminOrSuperuser]
    authentication_classes = [CookieTokenAuthentication]

    def get(self, request):
        """Retrieve all user profile"""
        try:
            serializer = self.get_serializer(self.get_queryset(), many=True)

            return self.get_response(
                status.HTTP_200_OK,
                "All user profiles retrieve successfully",
                serializer.data
            )
        except Exception as e:
            return self.get_response(
                status.HTTP_404_NOT_FOUND,
                f"Error retrieving profiles: {str(e)}"
            )
    