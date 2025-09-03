from rest_framework.authentication import BaseAuthentication
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
