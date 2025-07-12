from datetime import timezone
import json
from django.utils.timezone import now
from django.shortcuts import get_object_or_404, render
from rest_framework.generics import GenericAPIView
from django_redis import get_redis_connection
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.core.exceptions import PermissionDenied
from .utility import generate_token_for_user, verify_google_token
from users.models import CustomUser, Location
from django.contrib.auth.signals import user_logged_in
from rest_framework.exceptions import ValidationError
from redis.exceptions import ConnectionError as RedisConnectionError
from users.serializers import (
    CustomUserSerializer,
    LoginSerializer,
    LogoutSerializer,
    PasswordResetConfirmSerializer,
    OTPVerificationSerializer,
    PasswordResetRequestSerializer,
    LocationSerializer,
    RegistrationOTPVerificationSerializer,
)
from rest_framework.response import Response
from rest_framework import status
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from django.conf import settings
from rest_framework_simplejwt.tokens import RefreshToken
from notification.utility import (
    send_otp_email, generate_otp, store_otp,
    verify_registration_otp,
)
from django.core.cache import cache
import requests


def exchange_code_for_token(code):
    token_url = 'https://oauth2.googleapis.com/token'
    data = {
        'code': code,
        'client_id': settings.GOOGLE_OAUTH['WEB_CLIENT_ID'],
        'client_secret': settings.GOOGLE_OAUTH['CLIENT_SECRET'],
        'redirect_uri': settings.GOOGLE_OAUTH['REDIRECT_URI'],
        'grant_type': 'authorization_code'
    }

    response = requests.post(token_url, data=data)
    return response.json()

class RegisterUserView(GenericAPIView):
    """API endpoint to register users"""
    queryset = CustomUser.objects.all()
    serializer_class = CustomUserSerializer

    def post(self, request, *args, **kwargs):
        """
        Handles user registration and send otp to the email used
        OTP needs to be verified before account can be registered
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        email = serializer.validated_data["email"]
        otp = generate_otp()

        # Store registration data temporarily
        try:
            cache.set(f"reg_data:{email}", json.dumps(serializer.validated_data), timeout=300) #5 mins expiry
            cache.set(f"otp:{email}", otp, timeout=300) # OTP valid for 5 mins too
        except RedisConnectionError:
            return Response({
                "error": "Temporary issue accessing verification service. Try again shortly."
            }, status=503)

        # Send OTP
        send_otp_email(email, otp)

        return Response({
            "status": "success",
            "message": "OTP sent to email. Verify to complete registration.",
            "email": email
        }, status=status.HTTP_200_OK)


class ConfirmRegistrationOTPView(GenericAPIView):
    """
    Confirms user otp and registers new user
    """
    serializer_class = RegistrationOTPVerificationSerializer


    def post(self, request, *args, **kwargs):
        """
        Confirms the otp sent to the user
        If correct registered user successfully
        If invalid or expired, discard users data on redis
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"]
        otp = serializer.validated_data["otp"]

        stored_otp = verify_registration_otp(email, otp)
        if not stored_otp:
            return Response({
                "status": "error",
                "status_code": status.HTTP_400_BAD_REQUEST,
                "message": "Invalid or expired OTP",
            }, status=status.HTTP_400_BAD_REQUEST)
        
        user_data_json = cache.get(f"reg_data:{email}")
        if not user_data_json:
            return Response({
                "status": "error",
                "status_code": status.HTTP_400_BAD_REQUEST,
                "message": "Registration data expired",
            }, status=status.HTTP_400_BAD_REQUEST)
        
        user_data = json.loads(user_data_json)

        # activate user and save
        user_serializer = CustomUserSerializer(data=user_data)
        user_serializer.is_valid(raise_exception=True)
        user = user_serializer.save()
        user.save()

        # Explicitly update is_active and last_login
        user.is_active = True
        user.last_login = now()
        user.save(update_fields=['last_login', 'is_active'])

        # Generate access and refresh token
        tokens = generate_token_for_user(user)

        # Cleanup Redis
        cache.delete(f"reg_data:{email}")
        cache.delete(f"otp:{email}") 

        response_data = {
            "status": "success",
            "status_code": status.HTTP_201_CREATED,
            "message": "User registered successfully",
            "data": {
                "id": str(user.id),
                "email": user.email,
                "full_name": user.full_name,
                "phone_number": user.phone_number,
                "is_staff": user.is_staff,
                "is_superuser": user.is_superuser,
                "is_seller": user.is_seller,
                "is_active": user.is_active,
                "token": {
                    "access": tokens["access"],
                    "refresh": tokens["refresh"],
                }
            }
        }

        return Response(response_data, status=status.HTTP_201_CREATED)


class UserLoginView(GenericAPIView):
    """API endpoint for user login"""
    queryset = CustomUser.objects.all()
    serializer_class = LoginSerializer


    def post(self, request, *args, **kwargs):
        """Override the post method to handle user login"""
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            return Response({
                "status": "error",
                "status_code": status.HTTP_400_BAD_REQUEST,
                "message": e.detail if isinstance(e.detail, str) else "Invalid email or password",
                "errors": e.detail
            }, status=status.HTTP_400_BAD_REQUEST)
        user = serializer.validated_data['user']

        response_data = {
            "status": "success",
            "status_code": status.HTTP_200_OK,
            "message": "Login successful",
            "data": {
                "id": str(user.id),
                "email": user.email,
                "full_name": user.full_name,
                "phone_number": user.phone_number,
                "is_staff": user.is_staff,
                "is_superuser": user.is_superuser,
                "is_seller": user.is_seller,
                "is_active": user.is_active,
                'tokens': {
                    "access": serializer.get_access_token(user),
                    "refresh": serializer.get_refresh_token(user)
                }
            }
        }
        
        # Manually send log in signal
        user_logged_in.send(sender=user.__class__, request=request, user=user)

        return Response(response_data, status=status.HTTP_200_OK)
    


class GoogleLoginView(GenericAPIView):
    """Handles google login by accepting token_id from the frontend"""
    serializer_class = LoginSerializer
    def get(self, request, *args, **kwargs):
        """Handle redirect from Google with authorization code"""
        code = request.GET.get('code')

        if not code:
            return Response({
                "error": "No code provided",
                "status": "failed"
            }, status=status.HTTP_400_BAD_REQUEST)

        token_response = exchange_code_for_token(code)

        if 'id_token' in token_response:
            id_info = id_token.verify_oauth2_token(
                token_response['id_token'],
                google_requests.Request(),
                settings.GOOGLE_OAUTH['WEB_CLIENT_ID']
            )
            email = id_info.get('email')
            full_name = id_info.get('name')
            refresh_token = token_response.get('refresh_token')

            # Logic to create or update the user
            user, created = CustomUser.objects.get_or_create(email=email)
            if created:
                user.full_name = full_name
            user.is_active = True
            user.save()

            # Manually send log in signal
            user_logged_in.send(sender=user.__class__, request=request, user=user)

            return Response({
                "status": "success",
                "message": "Google login successful",
                "data": {
                    "email": email,
                    "full_name": full_name,
                    "refresh_token": refresh_token,
                    "id_token": token_response['id_token']
                }
            }, status=status.HTTP_200_OK)

        return Response({
            "status": "failed",
            "message": "Failed to exchange code for token",
            "error": token_response
        }, status=status.HTTP_400_BAD_REQUEST)
    

    def post(self, request, *args, **kwargs):
        """Override the post method to handle Google login"""
        
        token_id = request.data.get('token_id')
        refresh_token = request.data.get('refresh_token')
        platform = request.data.get('platform') # "web" or "mobile"
        
        if not token_id and not refresh_token:
            return Response({"error": "Token ID or Refresh Token is required"}, status=status.HTTP_400_BAD_REQUEST)

        if platform == "mobile":
            client_id = settings.GOOGLE_OAUTH['MOBILE_CLIENT_ID']
        else:
            client_id = settings.GOOGLE_OAUTH['WEB_CLIENT_ID']

        if token_id:
            try:
                # Verify the token using Google's API
                id_info = verify_google_token(token_id, refresh_token, client_id)
                            
                email = id_info['email']
                full_name = id_info['name']
                # picture_url = id_info['picture']

                # You can also extract other fields like 'picture' if needed

                # Check if user already exists
                user, created = CustomUser.objects.get_or_create(email=email)

                if created:
                    print("User created")
                    pass
                    
                user.full_name = full_name
                user.is_active = True  # Assuming Google login means the user is verified
                user.last_login = now()  # Update last login time
                user.save()
                
                serializer = LoginSerializer()
                response_data = {
                    "status": "success",
                    "status_code": status.HTTP_200_OK,
                    "message": "Google login successful",
                    "data": {
                        "id": str(user.id),
                        "email": user.email,
                        "full_name": user.full_name,
                        "phone_number": user.phone_number,
                        "is_staff": user.is_staff,
                        "is_superuser": user.is_superuser,
                        "is_seller": user.is_seller,
                        "is_active": user.is_active,
                        'tokens': {
                            "access": serializer.get_access_token(user),
                            "refresh": serializer.get_refresh_token(user)
                        }
                    }
                }

                # include the refresh token in the response if available
                if refresh_token:
                    response_data['data']['google_tokens'] = {
                        "token_id": id_info.pop('refreshed_token', None)
                    }

                return Response(response_data, status=status.HTTP_200_OK)

            except ValueError as e:
                return Response({
                    "error": str(e),
                    "status": "failed",
                    "message": "Invalid Google token"
                }, status=status.HTTP_400_BAD_REQUEST)
            

class UserLogoutView(GenericAPIView):
    """API endpoint for user logout"""
    permission_classes = [IsAuthenticated]
    serializer_class = LogoutSerializer

    def post(self, request, *args, **kwargs):
        """Override the post method to handle user logout"""
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            
            return Response({
                "status": "success",
                "status_code": status.HTTP_200_OK,
                "message": "Logout successful"
            }, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



class PasswordResetRequestView(GenericAPIView):
    """API endpoint for password reset request"""
    serializer_class = PasswordResetRequestSerializer

    def post(self, request, *args, **kwargs):
        """Override the post method to handle password reset request"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Placeholder for sending OTP
        email = serializer.validated_data['email']
        user = CustomUser.objects.get(email=email)
        
        
        # Generate OTP and send it to the user's email
        otp_code = generate_otp() # Generate a random OTP code
        send_otp_email(email, otp_code) # Send the OTP email
        store_otp(user.id, otp_code) # Store the OTP in Redis with a 5-minute expiry time

        return Response({
            "status": "success",
            "status_code": status.HTTP_200_OK,
            "message": "Password reset OTP sent successfully",
            "data": {
                "user_id": user.id,
            }
        }, status=status.HTTP_200_OK)
    
        # if settings.DEBUG:
        #     stored.otp = get_stored_otp_for_testing(user.id)
        #     if stored_otp:
        #         response_data['debug'] = {"otp": stored_otp}

        # return Response(response_data, status=status.HTTP_200_OK)
    

class VerifyOTPView(GenericAPIView):
    """API endpoint for verifying OTP"""
    serializer_class = OTPVerificationSerializer

    def post(self, request, *args, **kwargs):
        """Override the post method to handle OTP verification"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user_id = serializer.validated_data['user_id']
        
        return Response({
            "status": "success",
            "status_code": status.HTTP_200_OK,
            "message": "OTP verified successfully",
            "data": {"user_id": user_id}
        }, status=status.HTTP_200_OK)
    

class PasswordResetConfirmView(GenericAPIView):
    """API endpoint for confirming password reset"""
    serializer_class = PasswordResetConfirmSerializer

    def post(self, request, *args, **kwargs):
        """Override the post method to handle password reset confirmation"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Save the password rest
        serializer.save()

        return Response({
            "status": "success",
            "status_code": status.HTTP_200_OK,
            "message": "Password reset successful"
        }, status=status.HTTP_200_OK)
    
            

class CreateLocationView(GenericAPIView):
    """Handle the Location creation"""
    serializer_class = LocationSerializer
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        """Create user location"""

        # Check if location already exists for the user
        if hasattr(request.user, 'location'):
            return Response({
                "status": "error",
                "status code": status.HTTP_400_BAD_REQUEST,
                "message": "Location already exists. Please update it instead."
            }, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        location = serializer.save(user=request.user)

        response_data = {
            "status": "success",
            "status code": status.HTTP_201_CREATED,
            "message": "User location registered successfully",
            "data": serializer.data
        }

        return Response(response_data, status=status.HTTP_201_CREATED)
    

    # def perform_create(self, serializer):
    #     """Automatically assign request.user to the Location instance"""
    #     return serializer.save(user=self.request.user)


class LocationUpdateDeleteView(GenericAPIView):
    """View endpoint to handle user location update and deletion"""
    serializer_class = LocationSerializer
    permission_classes = [IsAuthenticated]
    queryset = Location.objects.all()


    def get_object(self, pk, request):
        """Check for permission"""
        location = get_object_or_404(Location, pk=pk)
        if request.method in ['PUT', 'PATCH']:
            if location.user != request.user:
                raise PermissionDenied("You do not have permission to access this location.")
        return location
    

    def put(self, request, pk, *args, **kwargs):
        """Update user location"""
        location = self.get_object(pk, request)
        serializer = self.get_serializer(location, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        response_data = {
            "status": "success",
            "status code": status.HTTP_200_OK,
            "message": "User location updated successfully",
            "location": serializer.data
        }

        return Response(response_data, status=status.HTTP_200_OK)
    

    def patch(self, request, pk, *args, **kwargs):
        """partially update user location"""
        location = self.get_object(pk, request)
        serializer = self.get_serializer(location, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        response_data = {
            "status": "success",
            "status code": status.HTTP_200_OK,
            "message": "User location updated successfully",
            "location": serializer.data
        }

        return Response(response_data, status=status.HTTP_200_OK)
    

    def delete(self, request, pk, *args, **kwargs):
        """Delete user location"""
        # Check for permission, only staff and superuser can delete user location
        if not request.user.is_staff and not request.user.is_superuser:
            raise PermissionDenied("Only staff or superusers can delete user locations")
        
        location = self.get_object(pk, request)
        location.delete()

        response_data = {
            "status": "success",
            "status code": status.HTTP_204_NO_CONTENT,
            "message": "User location deleted successfully",
        }

        return Response(response_data, status=status.HTTP_204_NO_CONTENT)



class SingleLocationView(GenericAPIView):
    """View endpoint to handle single user location view"""
    serializer_class = LocationSerializer
    permission_classes = [IsAuthenticated]
    queryset = Location.objects.all()

    def get(self, request, pk, *args, **kwargs):
        """Get a single user location by location ID"""
        location = get_object_or_404(Location, pk=pk)

        if location.user != request.user:
            return Response({
                "status": "error",
                "status code": status.HTTP_403_FORBIDDEN,
                "message": "You do not have permission to view this location."
            }, status=status.HTTP_403_FORBIDDEN)

        serializer = self.get_serializer(location)
        user = request.user

        response_data = {
            "status": "success",
            "status code": status.HTTP_200_OK,
            "message": "User location retrieved successfully",
            "user": {
                "id": str(user.id),
                "full_name": user.full_name,
                "email": user.email,
                "phone_number": user.phone_number,
            },
            'location': serializer.data,
        }

        return Response(response_data, status=status.HTTP_200_OK)
