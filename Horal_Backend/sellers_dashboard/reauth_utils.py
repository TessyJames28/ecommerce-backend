from django.conf import settings
from django.core.cache import cache
from redis.exceptions import ConnectionError as RedisConnectionError, TimeoutError as RedisTimeoutError
from django.core.cache.backends.base import InvalidCacheBackendError
from rest_framework.exceptions import APIException
import time, secrets
import hashlib, hmac
import logging


logger = logging.getLogger(__name__)

# TTL constants (from settings or defaults)
IDLE_TIMEOUT = getattr(settings, "IDLE_TIMEOUT", 6 * 60 * 60)
REAUTH_TTL = getattr(settings, "REAUTH_TTL", 6*60*60)
OTP_TTL = getattr(settings, "OTP_TTL", 5*60)
MAX_OTP_SENDS_PER_HOUR = getattr(settings, "MAX_OTP_SENDS_PER_HOUR", 5)
MAX_OTP_VERIFY_ATTEMPTS = getattr(settings, "MAX_OTP_VERIFY_ATTEMPTS", 5)

PEPPER = getattr(settings, "OTP_PEPPER")  # store in env vars


def _otp_hash(otp: str, user_id: int) -> str:
    """Combine otp with pepper + user id and hash using HMAC-SHA256"""
    key = PEPPER.encode()
    msg = f"{user_id}:{otp}".encode()
    return hmac.new(key, msg, hashlib.sha256).hexdigest()


def sendable(user_id: int) -> bool:
    key = f"seller: otp_sent_count:{user_id}"
    try:
        sent = cache.get(key)
        return (int(sent) if sent else 0) < MAX_OTP_SENDS_PER_HOUR
    except (RedisConnectionError, RedisTimeoutError, InvalidCacheBackendError) as e:
        logging.warning(f"Caching error: {e}")


def record_send(user_id: int):
    key = f"seller:otp_sent_count:{user_id}"
    # increment and set expire if first
    try:
        if not cache.get(key):
            # initialize count with 1, expires in 5 minutes
            cache.set(key, 1, timeout=300)
            return 1
        else:
            return cache.incr(key)
    except (RedisConnectionError, RedisTimeoutError, InvalidCacheBackendError) as e:
        logging.warning(f"Caching error: {e}")
        pass


def generate_otp() -> str:
    """6-digit secure numeric OTP"""
    return f"{secrets.randbelow(10**6):06d}"


def store_otp(user_id: int, otp: str):
    key = f"seller:otp_hash:{user_id}"
    try:
        cache.set(key, _otp_hash(otp, user_id), timeout=OTP_TTL)
        """Set verify attempts counter"""
        cache.set(f"seller:otp_verify_attempts:{user_id}", 0, timeout=OTP_TTL)
    except (RedisConnectionError, RedisTimeoutError, InvalidCacheBackendError) as e:
        logging.warning(f"Caching error: {e}")


def verify_otp(user_id: int, otp: str) -> bool:
    attempts_key = f"seller:otp_verify_attempts:{user_id}"
    try:
        att = cache.incr(attempts_key)
        if att == 1:
            cache.expire(attempts_key, OTP_TTL)

        if att > MAX_OTP_VERIFY_ATTEMPTS:
            return False
        
        key = f"seller:otp_hash:{user_id}"
        stored = cache.get(key)
        if not stored:
            return False
        if hmac.compare_digest(stored, _otp_hash(otp, user_id)):
            # success: remove otp keys
            cache.delete(key)
            cache.delete(attempts_key)
            return True
        return False
    except (RedisConnectionError, RedisTimeoutError, InvalidCacheBackendError) as e:
        logging.warning(f"Caching error: {e}")


def issue_reauth_token(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    key = f"seller:reauth:{user_id}"
    try:
        # Store in cache with TTL (e.g., 6 hours minutes)
        cache.set(key, token, timeout=getattr(settings, "REAUTH_TTL", 6*60*60))
        # Update last activity too
        set_last_activity(user_id)
        return token
    except (RedisConnectionError, RedisTimeoutError, InvalidCacheBackendError) as e:
        logging.warning(f"Caching error: {e}")


def validate_reauth(user_id: int, token: str) -> bool:
    key = f"seller:reauth:{user_id}"
    try:
        stored = cache.get(key)
        valid = stored and secrets.compare_digest(stored, token)
        return valid
    except (RedisConnectionError, RedisTimeoutError, InvalidCacheBackendError) as e:
        logging.warning(f"Caching error: {e}")


def revoke_reauth(user_id: int):
    try:
        cache.delete(f"seller:reauth:{user_id}")
    except (RedisConnectionError, RedisTimeoutError, InvalidCacheBackendError) as e:
        logging.warning(f"Caching error: {e}")


def set_last_activity(user_id: int):
    key = f"seller:last_activity:{user_id}"
    try:
        cache.set(key, str(int(time.time())), timeout=IDLE_TIMEOUT + 30)
    except (RedisConnectionError, RedisTimeoutError, InvalidCacheBackendError) as e:
        logging.warning(f"Caching error: {e}")


def is_idle(user_id: int) -> bool:
    key = f"seller:last_activity:{user_id}"
    try:
        ts = cache.get(key)
        if not ts:
            return True
        return int(time.time()) - int(ts) > IDLE_TIMEOUT
    except (RedisConnectionError, RedisTimeoutError, InvalidCacheBackendError) as e:
        logging.warning(f"Caching error: {e}")


class ReauthRequired(APIException):
    status_code = 403
    default_detail = "reauth_required"
    default_code = "reauth_required"
