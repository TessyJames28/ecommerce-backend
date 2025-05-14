from rest_framework.authentication import SessionAuthentication, BaseAuthentication
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import AuthenticationFailed


class SessionOrAnonymousAuthentication(BaseAuthentication):
    """
    Custom authentication class that handles both JWT-authenticated and anonymous users.
    For anonymous users, it allows the request to continue without authentication.
    """
    def authenticate(self, request):
        # Try to authenticate with JWT
        jwt_authenticator = JWTAuthentication()
        try:
            # This will return (user, token) if successful
            jwt_auth = jwt_authenticator.authenticate(request)
            if jwt_auth is not None:
                return jwt_auth
        except Exception:
            # Any JWT authentication errors, just continue as anonymous
            pass
        
        # If JWT authentication fails, return None to indicate anonymous access
        # DRF will set request.user to AnonymousUser
        return None