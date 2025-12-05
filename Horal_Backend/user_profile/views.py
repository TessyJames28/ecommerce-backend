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
from users.views import BaseConfirmResendOTPView
from products.utils import IsAdminOrSuperuser
import json

# Create your views here.
class BaseProfileView(GenericAPIView):
    """
    View to retrieve the complete seller profile
    """
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
                new_email = data["email"]
                print(f"New email: {new_email}")

                # Get new mobile if provided
                if "phone_number" in data:
                    mobile = data["phone_number"]
                    print(f"Mobile in data: {mobile}")
                else:
                    mobile = request.user.phone_number
                    print(f"Mobile: {mobile}")

                # Generate otp
                otp = generate_otp()
                
                safe_cache_set(f"email_update:{new_email}", json.dumps(data), timeout=1800)
                safe_cache_set(f"email_update_otp:{new_email}", otp, timeout=600) # OTP valid for 10 mins

                # Send otp email: both email and sms will be sent via the function
                if mobile:
                    send_otp_email(new_email, otp, request.user.full_name, mobile)
                else:
                    send_otp_email(new_email, otp, request.user.full_name)

                return Response({
                    "status": "success",
                    "message": f"Please verify your new email address"
                }, status=status.HTTP_200_OK)

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
            import traceback
            return Response({
                    "status": "error",
                    "message": f"{str(e)}\nTraceback: {traceback.format_exc()}",
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class GetUserProfileView(BaseProfileView):
    """Get user profile details"""
    serializer_class = ProfileSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [CookieTokenAuthentication]
        

class BaseConfirmEmailUpdateOTPView(GenericAPIView, BaseResponseMixin):
    """
    Base class to confirms user otp and registers new user
    Inherited by normal user profile and seller profile
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [CookieTokenAuthentication]

    # Override by child classes
    serializer_class = None

    def get_profile(self):
        """Override if a different profile instance"""
        return get_object_or_404(Profile, user=self.request.user)


    def post(self, request, *args, **kwargs):
        """
        Confirms the otp sent to the user
        If correct update user new email successfully
        If invalid or expired, discard users data on redis
        """
        try:
            data = request.data
            print(f"Data: {data}")
            email = data["email"]
            otp = data["otp"]
            print(f"Email: {email}\tOTP: {otp}")

            if not (email or otp):
                return self.get_response(
                    status.HTTP_400_BAD_REQUEST,
                    "Please provide the email and otp for verification"
                )
            
            profile = self.get_profile()

            cache_key = f"email_update_otp:{email}"

            stored_otp = verify_registration_otp(cache_key, otp)
            if not stored_otp:
                return self.get_response(
                    status.HTTP_400_BAD_REQUEST,
                    "Invalid or expired OTP",
                )
            
            update_email = f"email_update:{email}"
            user_data_json = safe_cache_get(update_email)
            if not user_data_json:
                return self.get_response(
                    status.HTTP_400_BAD_REQUEST,
                    "Update data expired",
                )
            
            user_update_data = json.loads(user_data_json)

            serializer = self.get_serializer(profile, data=user_update_data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()

            cache.delete(f"email_update:{email}")
            cache.delete(f"email_update_otp:{email}") 

            return self.get_response(
                status.HTTP_200_OK,
                "User profile updated successfully",
                serializer.data
            )
        except Exception as e:
            import traceback
            return self.get_response(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                f"Error updating profile: {str(e)}\nTraceback: {traceback.format_exc()}"
            )
        

class ConfirmEmailUpdateOTPView(BaseConfirmEmailUpdateOTPView):
    serializer_class = ProfileSerializer


class ResendOTPView(BaseConfirmResendOTPView):
    """
    Resends the OTP for a registration email if user hasn't confirmed yet
    """
    otp_cache_prefix = "email_update_otp"
    redis_key_prefix = "email_update"
    otp_expiry = 600 # 10 mins

    class InputSerializer(serializers.Serializer):
        email = serializers.EmailField()

    input_serializer_class = InputSerializer  # simple serializer for email only


    def send_otp(self, email, otp, user_name, mobile):
        send_otp_email(email, otp, user_name, mobile)

    

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
    