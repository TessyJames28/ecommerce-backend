from django.core.mail import send_mail
from django.core.cache import cache
from django.conf import settings
from django.core.cache.backends.base import InvalidCacheBackendError
from redis.exceptions import ConnectionError as RedisConnectionError
from rest_framework.response import Response
import random
import logging

logger = logging.getLogger(__name__)


def generate_otp(length=6):
    """Generate a random 4-digit OTP."""
    return ''.join([str(random.randint(0, 9)) for _ in range(length)])



# Redis helper
def store_otp(user_id, otp_code):
    """Store OTP in Redis with an expiry time."""
    try:
        cache_key = f"otp:{user_id}"
        cache.set(cache_key, otp_code, timeout=300) # 5 minutes expiration
    except Exception as e:
        logger.warning(f"OTP Redis cache failed: {e}")
        pass


def verify_otp(user_id, otp_code):
    """Verify the OTP from Redis and delete if correct."""
    try:
        cache_key = f"otp:{user_id}"
        stored_otp = cache.get(cache_key)
    except RedisConnectionError:
        logger.warning(f"Redis connection error: {RedisConnectionError}")
        return Response({
            "error": "Temporary issue accessing verification service. Try again shortly."
        }, status=503)
    if stored_otp == otp_code:
        cache.delete(cache_key)  # Delete OTP after verification
        return True


# # for testing in development environment
# def get_stored_otp_for_testing(user_id):
#     """Get the stored OTP for testing purposes."""
   
#     if not settings.DEBUG:
#         return None
    
#     cache_key = f"otp:{user_id}"
#     stored_otp = cache.get(cache_key)

#     if stored_otp:
#         return stored_otp
    
#     # chcek in-memory store
#     if hasattr(store_otp, 'otp_store'):
#         return store_otp.otp_store.get(cache_key)
    
#     return None


def verify_registration_otp(email, otp_code):
    """
    Verify registration OTP and delete if correct.
    """
    try:
        cache_key = f"otp:{email}"
        stored_otp = cache.get(cache_key)
    except RedisConnectionError:
        logger.warning(f"Redis connection error: {RedisConnectionError}")
        return Response({
            "error": "Temporary issue accessing verification service. Try again shortly."
        }, status=503)

    if stored_otp == otp_code:
        cache.delete(cache_key)
        return True

    return False


def safe_cache_get(key, default=None):
    """Safe cache for retriving cache data"""
    try:
        return cache.get(key)
    except (RedisConnectionError, TimeoutError, InvalidCacheBackendError) as e:
        logging.warning(f"caching error: {e}")
        return default
    

def safe_cache_set(key, value, timeout=86400):
    """Safe cache to set cache data"""
    try:
        cache.set(key, value, timeout)
    except (RedisConnectionError, TimeoutError, InvalidCacheBackendError) as e:
        logging.warning(f"Caching error: {e}")
        pass




