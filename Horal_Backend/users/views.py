import json
from django.utils.timezone import now
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import get_object_or_404
from rest_framework.generics import GenericAPIView
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from django.core.exceptions import PermissionDenied
from .utils import generate_token_for_user, verify_google_token, exchange_code_for_token
from users.models import CustomUser, Location
from django.contrib.auth.signals import user_logged_in
from rest_framework.exceptions import ValidationError
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
from .authentication import CookieTokenAuthentication
from django.core.cache import cache
from rest_framework.response import Response
from rest_framework import status
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from django.conf import settings
from notifications.utils import (
    generate_otp, store_otp,
    verify_registration_otp,
    safe_cache_set, safe_cache_get
)
from notifications.emails import (
    send_otp_email, send_registration_otp_email,
    send_registration_url_email
)
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie


@method_decorator(csrf_exempt, name='dispatch')
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
        user_name = serializer.validated_data["full_name"]
        mobile = serializer.validated_data["phone_number"]
        otp = generate_otp()

        # Store registration data temporarily for 30mins
        safe_cache_set(f"reg_data:{email}", json.dumps(serializer.validated_data), timeout=1800)
        safe_cache_set(f"otp:{email}", otp, timeout=600) # OTP valid for 10 mins

        # Send OTP
        send_registration_otp_email(email, otp, user_name, mobile)

        return Response({
            "status": "success",
            "message": "OTP sent to email. Verify to complete registration.",
            "email": email
        }, status=status.HTTP_200_OK)
    


@method_decorator(csrf_exempt, name='dispatch')
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

        cache_key = f"otp:{email}"

        stored_otp = verify_registration_otp(cache_key, otp)
        if not stored_otp:
            return Response({
                "status": "error",
                "status_code": status.HTTP_400_BAD_REQUEST,
                "message": "Invalid or expired OTP",
            }, status=status.HTTP_400_BAD_REQUEST)
        
        reg_key = f"reg_data:{email}"
        user_data_json = safe_cache_get(reg_key)
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
            }
        }

        # Determine platform (pass from frontend)
        platform = request.data.get("platform", "web")  # default to web

        if platform.lower() == "mobile":
            # Include tokens in response body for mobile
            response_data["data"]["tokens"] = {
                "access": tokens["access"],
                "refresh": tokens["refresh"],
            }

        # Create response object
        response = Response(response_data, status=status.HTTP_201_CREATED)
        # set HttpOnly cookies
        response.set_cookie(
            key="access_token",
            value=tokens["access"],
            httponly=True,
            secure=True, # Use True in production (HTTPS)
            samesite="None"
        )
        
        response.set_cookie(
            key="refresh_token",
            value=tokens["refresh"],
            httponly=True,
            secure=True, # Use True in production (HTTPS)
            samesite="None"
        )

        return response
    

class BaseConfirmResendOTPView(GenericAPIView):
    """
    Base class for resending OTP codes.
    Child classes must set:
        - redis key prefix eg "reg_data" (or something else)
        - otp cache prefix = "otp"
        - otp_expiry = 600 (default)
        - send_otp_func 
    
    Child class may override:
        - get_user_data(redis_raw) 
    """

    # default configurations
    redis_key_prefix = None           # MUST BE SET in child class
    otp_cache_prefix = "otp"
    otp_expiry = 600                  # 10 minutes default
    input_serializer_class = None     # MUST BE SET in child class


    def get_user_data(self, redis_raw: str):
        """This function parse data stored in redis (Can be overriden)."""
        return json.loads(redis_raw)
    

    def get_input_data(self, request):
        """Validates input using child-defined serializer"""
        if not self.input_serializer_class:
            raise NotImplemented("input_serializer_class must be defined by child view")
        
        serializer = self.input_serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data
    

    def send_otp(self, otp, user_name, mobile=None, email=None):
        """Child class MUST override this."""
        raise NotImplementedError("Child class must implement send_otp()")
    

    def get_redis_key(self, email):
        """Build redis key for stored pending data"""
        if not self.redis_key_prefix:
            raise NotImplementedError("redis_key_prefix must be defined in child view")
        return f"{self.redis_key_prefix}:{email}"
    

    def post(self, request, *args, **kwargs):
        """
        POST method to resend otp email if user hasn't confirmed yet
        """
        try:
            data = self.get_input_data(request)
            email = data["email"]
            

            # Fetch stored data from redis
            redis_key = self.get_redis_key(email)
            raw = safe_cache_get(redis_key)

            if not raw:
                return Response({
                    "status": "error",
                    "status_code": status.HTTP_400_BAD_REQUEST,
                    "message": "No pending registration found or registration expired."
                }, status=status.HTTP_400_BAD_REQUEST)
            
            user_data = self.get_user_data(raw)
            user_name = user_data.get("full_name", None)
            mobile = user_data.get("phone_number", None)

            if not user_name:
                user_name = request.user.full_name
            if not mobile:
                mobile = request.user.phone_number
            try:
                if request.user.is_seller:
                    seller = SellerKYC.objects.get(user=request.user)
                    mobile = seller.address.mobile
            except Exception:
                pass

            # Generate OTP
            otp = generate_otp()
            otp_key = f"{self.otp_cache_prefix}:{email}"

            safe_cache_set(otp_key, otp, timeout=self.otp_expiry)

            # Send email/SMS implemented by child class
            self.send_otp(otp, user_name, mobile=mobile, email=email)

            return Response({
                "status": "success",
                "message": "OTP resent successfully. Check your email or phone number",
                # "email": email
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                "status": "error",
                "message": f"An error occurred: {str(e)}.",
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    

@method_decorator(csrf_exempt, name='dispatch')
class ResendRegistrationOTPView(BaseConfirmResendOTPView):
    """
    Resends the OTP for a registration email if user hasn't confirmed yet
    """
    otp_cache_prefix = "otp"
    redis_key_prefix = "reg_data"
    otp_expiry = 600 # 10 mins

    class InputSerializer(serializers.Serializer):
        email = serializers.EmailField()

    input_serializer_class = InputSerializer  # simple serializer for email only


    def send_otp(self, otp, user_name, mobile=None, email=None):
        send_registration_otp_email(email, otp, user_name, mobile)



@method_decorator(csrf_exempt, name='dispatch')
class UserLoginView(GenericAPIView):
    """API endpoint for user login"""
    queryset = CustomUser.objects.all()
    serializer_class = LoginSerializer


    def post(self, request, *args, **kwargs):
        """Override the post method to handle user login"""
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
            user = serializer.validated_data['user']

        except ValidationError as e:
            detail = e.detail

            if isinstance(detail, list):
                msg = detail[0]
            elif isinstance(detail, dict):
                # Take first value
                key = next(iter(detail))
                val = detail[key]

                if isinstance(val, list):
                    msg = val[0]
                else:
                    msg = val
            else:
                msg = str(detail)

            return Response({
                "status": "error",
                "status_code": status.HTTP_400_BAD_REQUEST,
                "message": msg
            }, status=status.HTTP_400_BAD_REQUEST)
        
        except ObjectDoesNotExist:
            return Response({
                "status": "error",
                "status_code": status.HTTP_404_NOT_FOUND,
                "message": "User not found"
            }, status=status.HTTP_404_NOT_FOUND)

        except Exception as e:
            # Catch-all for any unexpected error
            return Response({
                "status": "error",
                "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": f"An unexpected error occurred during login. Please try again: {str(e)}",
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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
            }
        }

        # Determine platform (pass from frontend)
        platform = request.data.get("platform", "web")  # default to web

        if platform.lower() == "mobile":
            # Include tokens in response body for mobile
            response_data["data"]["tokens"] = {
                "access": serializer.get_access_token(user),
                "refresh": serializer.get_refresh_token(user),
            }

        # Create response object
        response = Response(response_data, status=status.HTTP_200_OK)

        # set HttpOnly cookies
        response.set_cookie(
            key="access_token",
            value=serializer.get_access_token(user),
            httponly=True,
            secure=True, # Use True in production (HTTPS)
            samesite="None"
        )

        response.set_cookie(
            key="refresh_token",
            value=serializer.get_refresh_token(user),
            httponly=True,
            secure=True, # Use True in production (HTTPS)
            samesite="None"
        )
        
        # Manually send log in signal
        user_logged_in.send(sender=user.__class__, request=request, user=user)

        return response
    

@method_decorator(csrf_exempt, name='dispatch')
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
        refresh_token = request.data.get('refresh_token', "")
        platform = request.data.get('platform') # "web" or "mobile"
        
        if not token_id:
            return Response({"error": "Token ID is required"}, status=status.HTTP_400_BAD_REQUEST)

        if platform == "mobile":
            client_id = settings.GOOGLE_OAUTH['MOBILE_CLIENT_ID']
        elif platform == "ios":
            client_id = settings.GOOGLE_OAUTH['IOS_CLIENT_ID']
        else:
            client_id = settings.GOOGLE_OAUTH['WEB_CLIENT_ID']

        if token_id:
            try:
                # Verify the token using Google's API
                id_info = verify_google_token(token_id, client_id)
                            
                email = id_info['email']
                full_name = id_info['name']
                # picture_url = id_info['picture']

                # You can also extract other fields like 'picture' if needed

                if not email:
                    return Response({
                        "error": "Google account email not found",
                        "status": "failed",
                        "message": "Could not retrieve email from Google account"
                    }, status=status.HTTP_400_BAD_REQUEST)

                # Check if user already exists, or create a new one
                user, created = CustomUser.objects.get_or_create(
                    email=email,
                    defaults={
                        "full_name": full_name,
                        "is_active": True,
                        "last_login": now()
                    }
                )

                if created:
                    user.full_name = full_name
                    user.is_active = True
                    user.last_login = now()
                    user.save()

                # Update only if the user already existed
                # user.full_name = full_name
                user.is_active = True
                user.last_login = now()
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
                    }
                }
                print(f"Access token: {serializer.get_access_token(user)}")

                # Determine platform (pass from frontend)
                platform = request.data.get("platform", "web")  # default to web

                if platform.lower() == "mobile":
                    # Include tokens in response body for mobile
                    response_data["data"]["tokens"] = {
                        "access": serializer.get_access_token(user),
                        "refresh": serializer.get_refresh_token(user),
                    }

                # Create response object
                response = Response(response_data, status=status.HTTP_200_OK)

                # set HttpOnly cookies
                response.set_cookie(
                    key="access_token",
                    value=serializer.get_access_token(user),
                    httponly=True,
                    secure=True, # Use True in production (HTTPS)
                    samesite="None"
                )

                response.set_cookie(
                    key="refresh_token",
                    value=serializer.get_refresh_token(user),
                    httponly=True,
                    secure=True, # Use True in production (HTTPS)
                    samesite="None"
                )

                # Save refresh token in the DB
                if refresh_token:
                    user.google_refresh_token = refresh_token
                    user.save(update_fields=["google_refresh_token"])

                return response

            except ValueError as e:
                return Response({
                    "error": str(e),
                    "status": "failed",
                    "message": "Invalid Google token"
                }, status=status.HTTP_400_BAD_REQUEST)
            
            except Exception as e:
                return Response({
                    "error": str(e),
                    "status": "failed",
                    "message": "An unexpected error occurred during Google login"
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            

class UserLogoutView(GenericAPIView):
    """API endpoint for user logout"""
    permission_classes = [IsAuthenticated]
    serializer_class = LogoutSerializer

    def post(self, request, *args, **kwargs):
        """Override the post method to handle user logout"""            
        response = Response({
            "status": "success",
            "status_code": status.HTTP_200_OK,
            "message": "Logout successful"
        }, status=status.HTTP_200_OK)
        response.delete_cookie("access_token")
        response.delete_cookie("refresh_token")

        return response


@method_decorator(csrf_exempt, name='dispatch')
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
        user_name = user.full_name
        mobile = user.phone_number
        print(f"Mobile: {mobile}")
        
        
        # Generate OTP and send it to the user's email
        otp_code = generate_otp() # Generate a random OTP code
        send_otp_email(otp_code, user_name, mobile=mobile, to_email=email) # Send the OTP email
        store_otp(user.id, otp_code) # Store the OTP in Redis with a 5-minute expiry time

        return Response({
            "status": "success",
            "status_code": status.HTTP_200_OK,
            "message": "Password reset OTP sent successfully",
            "data": {
                "user_id": user.id,
            }
        }, status=status.HTTP_200_OK)
    

@method_decorator(csrf_exempt, name='dispatch')
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
    

@method_decorator(csrf_exempt, name='dispatch')
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
    authentication_classes = [CookieTokenAuthentication]

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
        serializer.save(user=request.user)

        response_data = {
            "status": "success",
            "status code": status.HTTP_201_CREATED,
            "message": "User location registered successfully",
            "data": serializer.data
        }

        return Response(response_data, status=status.HTTP_201_CREATED)
    

class LocationUpdateDeleteView(GenericAPIView):
    """View endpoint to handle user location update and deletion"""
    serializer_class = LocationSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [CookieTokenAuthentication]
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
    authentication_classes = [CookieTokenAuthentication]
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


class CookieTokenRefreshView(TokenRefreshView):
    """Handle refreshing of JWT tokens for web (cookies) and mobile (body)."""
    serializer_class = TokenRefreshSerializer

    def post(self, request, *args, **kwargs):
        platform = request.data.get("platform", "web")  # default to web

        if platform.lower() == "mobile":
            # Expect refresh token from request body
            refresh_token = request.data.get("refresh")
        else:
            # Expect refresh token from cookies
            refresh_token = request.COOKIES.get("refresh_token")

        if not refresh_token:
            return Response({"detail": "Refresh token missing"}, status=401)

        # Build data for serializer
        data = {"refresh": refresh_token}
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)

        # Standard DRF-SimpleJWT validated data
        access = serializer.validated_data.get("access")
        refresh = serializer.validated_data.get("refresh")

        response = Response(status=200)

        if platform.lower() == "mobile":
            # Mobile → send tokens back in body
            response.data = {
                "access": access,
                "refresh": refresh,
            }
        else:
            # Web → no tokens in body, just set cookies
            response.data = {"detail": "Token refreshed"}
            response.set_cookie(
                key="access_token",
                value=access,
                httponly=True,
                secure=True,
                samesite="None",
            )
            response.set_cookie(
                key="refresh_token",
                value=refresh,
                httponly=True,
                secure=True,
                samesite="None",
            )

        return response
    

@ensure_csrf_cookie
def get_csrf_token(request):
    """
    View that sets and returns a CSRF token in JSON.
    Frontend should call this endpoint first to get the token.
    """
    return JsonResponse({"csrfToken": request.META.get("CSRF_COOKIE")})


#======== New Registration endpoint for agents scouting for sellers =======
@method_decorator(csrf_exempt, name='dispatch')
class AgentRegisterUserView(GenericAPIView):
    """API endpoint to register users"""
    queryset = CustomUser.objects.all()
    serializer_class = CustomUserSerializer

    def post(self, request, *args, **kwargs):
        """
        Handles user registration and send registration url to the email used
        Url contains otp that needs to be verified before account can be registered
        """
        data = request.data.copy()
        
        # Get url to redirect users to complete registration
        url = data.pop("url", "")
        print("Registration URL:", url)

        if not url:
            return Response({
                "status": "error",
                "status_code": status.HTTP_400_BAD_REQUEST,
                "message": "URL is required for agent registration"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        
        email = serializer.validated_data["email"]
        user_name = serializer.validated_data["full_name"]
        
        # Generate OTP and send it to the user's email
        otp = generate_otp()

        # Store registration data temporarily for 30mins
        safe_cache_set(f"reg_data:{email}", json.dumps(serializer.validated_data), timeout=86400) # 24 hours livespan
        safe_cache_set(f"otp:{email}", otp, timeout=86400) # OTP valid for 24 hours

        # Send registration otp url
        reg_url = f"{url}?email={email}&otp={otp}"
        send_registration_url_email(email, reg_url, user_name)

        return Response({
            "status": "success",
            "message": "Regitration url sent to email. Verify to complete registration."
        }, status=status.HTTP_200_OK)
