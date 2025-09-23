from django.conf import settings
from django.http import JsonResponse
from ..reauth_utils import is_idle, set_last_activity, validate_reauth


class DashboardReauthMiddleware:
    """Middleware to enforce reauth on dashboard routes"""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user and user.is_authenticated and getattr(user, "is_seller", False):
            path = request.path

            if path.startswith("api/v1/dashboard/seller/"):
                if is_idle(user.id):
                    # check cookie or header
                    token = request.COOKIES.get("reauth_token") or request.headers.get("X-REAUTH_TOKEN")
                    if not token or not validate_reauth(user.id, token):
                        # return 401 for FE to trigger OTP modal
                        return JsonResponse({
                            "detail": "reauth_required"
                        }, status=401)
                    else:
                        # not idle: updte last activity for server
                        set_last_activity(user.id)
        return self.get_response(request)
