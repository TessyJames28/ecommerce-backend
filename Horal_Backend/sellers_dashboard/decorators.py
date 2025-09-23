from functools import wraps
from django.core.cache import cache
from django.http import JsonResponse
from .reauth_utils import validate_reauth
import logging


logger = logging.getLogger(__name__)

def redis_lock(key_prefix: str, timeout: int = 600):
    """
    Decorator to ensure a celery task doesn't run concurrently.
    Uses Django's cache (Redis) as locking mechanism.

    Args:
        key_prefix (str): Unique name per task or task.
        timeout (int): Lock expiration in seconds.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            lock_key = f"lock:{key_prefix}"
            if not cache.add(lock_key, "locked", timeout):
                logger.warning(f"[SKIPPED] Task {key_prefix} already running.")
                return None
            
            try:
                logger.info(f"[STARTED] Task {key_prefix}")
                return func(*args, **kwargs)
            except Exception as e:
                logger.exception(f"[ERROR] in task {key_prefix}: {e}")
                raise
            finally:
                cache.delete(lock_key)
                logger.info(f"[RELEASED locked for {key_prefix}")
        return wrapper
    
    return decorator


def require_reauth(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        user = request.user
        if not user.is_authenticated or not getattr(user, "is_seller", False):
            return JsonResponse({
                "detail": "auth_required"
            }, status=401)
        # check cookie or header
        token = request.COOKIES.get("reauth_token") or request.headers.get("X-REAUTH_TOKEN")
        if not token or not validate_reauth(user.id, token):
            # return 401 for FE to trigger OTP modal
            return JsonResponse({
                "detail": "reauth_required"
            }, status=401)
        return view_func(request, *args, **kwargs)
    return _wrapped
