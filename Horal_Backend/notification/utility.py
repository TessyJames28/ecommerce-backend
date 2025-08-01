from django.core.mail import send_mail
from django.core.cache import cache
from django.conf import settings
from redis.exceptions import ConnectionError as RedisConnectionError
from rest_framework.response import Response
import requests, random


def send_otp_email(to_email, otp_code):
    """Send an OTP email to the user."""
    subject = 'Your OTP Code'
    message = f"Hello!\n\nYour OTP code is: {otp_code}\nIt will expire in 5 minutes.\n\nThanks!"
    # from_email = "noreply@example.com"
    result = send_mail(
        subject,
        message,
        # from_email,
        settings.DEFAULT_FROM_EMAIL, # from
        [to_email], # To
        fail_silently=False,
    )


# def send_password_reset_otp(email, otp_code):
#     """Send a password reset email to the user."""
#     return requests.post(
#         f"https://api.mailgun.net/v3/{settings.MAILGUN_DOMAIN}/messages",
#         auth=("api", settings.MAILGUN_API_KEY),
#         data={
#             "from": f"YourApp <mailgun@{settings.MAILGUN_DOMAIN}>",
#             "to": [email],
#             "subject": "Your Password Reset OTP",
#             "text": f"Your OTP is: {otp_code}",  # Replace with your real OTP logic
#         }
#     )


def generate_otp(length=6):
    """Generate a random 4-digit OTP."""
    return ''.join([str(random.randint(0, 9)) for _ in range(length)])



# Redis helper
def store_otp(user_id, otp_code):
    """Store OTP in Redis with an expiry time."""
    cache_key = f"otp:{user_id}"
    cache.set(cache_key, otp_code, timeout=300) # 5 minutes expiration



def verify_otp(user_id, otp_code):
    """Verify the OTP from Redis and delete if correct."""
    try:
        cache_key = f"otp:{user_id}"
        stored_otp = cache.get(cache_key)
    except RedisConnectionError:
        return Response({
            "error": "Temporary issue accessing verification service. Try again shortly."
        }, status=503)
    if stored_otp == otp_code:
        cache.delete(cache_key)  # Delete OTP after verification
        return True


# for testing in development environment
def get_stored_otp_for_testing(user_id):
    """Get the stored OTP for testing purposes."""
   
    if not settings.DEBUG:
        return None
    
    cache_key = f"otp:{user_id}"
    stored_otp = cache.get(cache_key)

    if stored_otp:
        return stored_otp
    
    # chcek in-memory store
    if hasattr(store_otp, 'otp_store'):
        return store_otp.otp_store.get(cache_key)
    
    return None


def verify_registration_otp(email, otp_code):
    """
    Verify registration OTP and delete if correct.
    """
    try:
        cache_key = f"otp:{email}"
        stored_otp = cache.get(cache_key)
    except RedisConnectionError:
        return Response({
            "error": "Temporary issue accessing verification service. Try again shortly."
        }, status=503)

    if stored_otp == otp_code:
        cache.delete(cache_key)
        return True

    return False


def store_order_otp(order_id, otp_code):
    """
    Store order OTP in Redis with an expiry time.
    """
    try:
        cache_key = f"otp:order:{order_id}"
        cache.set(cache_key, otp_code, timeout=300)  # 5 minutes expiration
    except RedisConnectionError:
        return Response({
            "error": "Temporary issue accessing verification service. Try again shortly."
        }, status=503)


def verify_order_otp(order_id, otp_code):
    """
    Verify the order OTP from Redis and delete if correct.
    """
    try:
        cache_key = f"otp:order:{order_id}"
        stored_otp = cache.get(cache_key)
    except RedisConnectionError:
        return Response({
            "error": "Temporary issue accessing verification service. Try again shortly."
        }, status=503)

    if stored_otp == otp_code:
        cache.delete(cache_key)  # Delete OTP after verification
        return True

    return False