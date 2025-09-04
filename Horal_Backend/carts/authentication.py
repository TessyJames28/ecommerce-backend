from rest_framework.authentication import SessionAuthentication, BaseAuthentication
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import AuthenticationFailed


# class SessionOrAnonymousAuthentication(BaseAuthentication):
#     """
#     Custom authentication class that handles both JWT-authenticated and anonymous users.
#     For anonymous users, it allows the request to continue without authentication.
#     """
#     def authenticate(self, request):
#         # Try to authenticate with JWT
#         jwt_authenticator = JWTAuthentication()
#         try:
#             # This will return (user, token) if successful
#             jwt_auth = jwt_authenticator.authenticate(request)
#             if jwt_auth is not None:
#                 return jwt_auth
#         except Exception:
#             # Any JWT authentication errors, just continue as anonymous
#             pass

#         # Tru session auth for httponly auth
#         session_authenticator = SessionAuthentication()
#         try:
#             session_auth = session_authenticator.authenticate(request)
#             if session_auth is not None:
#                 return session_auth
#         except Exception:
#             pass
        
#         # If JWT authentication fails, return None to indicate anonymous access
#         # DRF will set request.user to AnonymousUser
#         return None


class CookieJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        # Try Authorization header first (default behavior)
        header = self.get_header(request)
        if header is not None:
            raw_token = self.get_raw_token(header)
            if raw_token is not None:
                validated_token = self.get_validated_token(raw_token)
                return self.get_user(validated_token), validated_token

        # If no header, try cookies
        raw_token = request.COOKIES.get("access_token")
        if raw_token is not None:
            validated_token = self.get_validated_token(raw_token)
            return self.get_user(validated_token), validated_token

        return None


class SessionOrAnonymousAuthentication(BaseAuthentication):
    """
    Custom authentication class that handles both JWT-authenticated and anonymous users.
    """
    def authenticate(self, request):
        jwt_authenticator = CookieJWTAuthentication()
        try:
            jwt_auth = jwt_authenticator.authenticate(request)
            if jwt_auth is not None:
                return jwt_auth
        except Exception:
            pass
        
        return None
