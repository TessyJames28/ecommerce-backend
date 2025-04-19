from datetime import timezone
from django.utils.timezone import now
from django.shortcuts import render
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from .utility import refresh_google_token, verify_google_token
from users.models import CustomUser
from users.serializers import (
    CustomUserSerializer,
    LoginSerializer,
    LogoutSerializer,
    PasswordResetConfirmSerializer,
    OTPVerificationSerializer,
    PasswordResetRequestSerializer,
)
from rest_framework.response import Response
from rest_framework import status
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from django.conf import settings
from rest_framework_simplejwt.tokens import RefreshToken
from notifications.utility import send_otp_email, store_otp, generate_otp, get_stored_otp_for_testing
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
        """Override the create method to handle user registration"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

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
                "is_seller": user.is_seller,
                "is_active": user.is_active
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
        serializer.is_valid(raise_exception=True)
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
                "is_seller": user.is_seller,
                "is_active": user.is_active,
                'tokens': {
                    "access": serializer.get_access_token(user),
                    "refresh": serializer.get_refresh_token(user)
                }
            }
        }
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

            # Now use your logic to create or update the user
            # Example:
            user, created = CustomUser.objects.get_or_create(email=email)
            if created:
                user.full_name = full_name
            user.is_active = True
            user.save()

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
                        "is_verified": user.is_verified,
                        "is_staff": user.is_staff,
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
            "message": "Password reset OTP sent successfully"
        }, status=status.HTTP_200_OK)
    
        if settings.DEBUG:
            stored.otp = get_stored_otp_for_testing(user.id)
            if stored_otp:
                response_data['debug'] = {"otp": stored_otp}

        return Response(response_data, status=status.HTTP_200_OK)
    

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
    


# For testing and development environment
# Only include this view in development/testing environments
from django.conf import settings
if settings.DEBUG:
    class OTPTestingView(GenericAPIView):
        """Testing utility - DO NOT USE IN PRODUCTION"""
        
        def post(self, request, *args, **kwargs):
            """Get stored OTP for a user by email (for testing only)"""
            email = request.data.get('email')
            if not email:
                return Response({"error": "Email parameter required"}, status=400)
                
            try:
                user = CustomUser.objects.get(email=email)
                otp = get_stored_otp_for_testing(user.id)
                if otp:
                    return Response({"email": email, "user_id": user.id, "otp": otp})
                return Response({"email": email, "error": "No OTP found"}, status=404)
            except CustomUser.DoesNotExist:
                return Response({"error": "User not found"}, status=404)
