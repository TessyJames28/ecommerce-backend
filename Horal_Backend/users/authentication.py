from rest_framework.authentication import BaseAuthentication
from rest_framework.permissions import BasePermission
from rest_framework.exceptions import AuthenticationFailed
from sellers_dashboard.reauth_utils import validate_reauth, is_idle, set_last_activity
from rest_framework import exceptions
from django.conf import settings
import jwt

class CookieTokenAuthentication(BaseAuthentication):
    """
    Authenticate DRF requests using access token stored in HttpOnly cookie.
    """
    def authenticate(self, request):
        from .models import CustomUser
        # 1. Try Authorization header first (mobile)
        auth_header = request.headers.get("Authorization")
        token = None

        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
        else:
            # 2. Fallback to cookie (web)
            token = request.COOKIES.get("access_token")
    
        if not token:
            return None  # no token, DRF will try other authenticators or return 401

        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])

        except jwt.ExpiredSignatureError:
            raise exceptions.AuthenticationFailed("Token has expired")
        except jwt.InvalidTokenError:
            raise exceptions.AuthenticationFailed("Invalid token")

        try:
            user = CustomUser.objects.get(id=payload["user_id"])
        except CustomUser.DoesNotExist:
            raise exceptions.AuthenticationFailed("User not found")

        return (user, None)
    

class ReauthRequiredPermission(BasePermission):
    """
    Enforces reauthentication for seller dashboard routes.
    Runs after the user is already authenticated by DRF.
    """
    message = "reauth_required"

    def has_permission(self, request, view):
        user = getattr(request, "user", None)

        # Only sellers must reauth
        if not user or not user.is_authenticated or not getattr(user, "is_seller", False):
            return True  # allow non-sellers

        path = request.path

        # Skip OTP endpoints themselves
        if path.startswith("/api/v1/dashboard/seller/") and not path.startswith("/api/v1/dashboard/seller/reauth/"):
            token = request.COOKIES.get("reauth_token") or request.headers.get("X-REAUTH_TOKEN")

            # CASE 1: No token → force OTP
            if not token:
                print("No token seen")
                raise AuthenticationFailed("reauth_required")

            # CASE 2: Invalid/expired token → force OTP
            if not validate_reauth(user.id, token):
                print("Token not validated")
                raise AuthenticationFailed("reauth_required")

            # CASE 3: Idle too long → force OTP
            if is_idle(user.id):
                print("User idle")
                raise AuthenticationFailed("reauth_required")
            
            set_last_activity(user.id)
        return True  # ✅ permission granted

