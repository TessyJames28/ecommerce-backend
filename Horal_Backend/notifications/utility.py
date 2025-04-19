from django.core.mail import send_mail
from django.core.cache import cache
from django.conf import settings
import requests, random


def send_otp_email(to_email, otp_code):
    """Send an OTP email to the user."""
    subject = 'Your OTP Code'
    message = f"Hello!\n\nYour OTP code is: {otp_code}\nIt will expire in 5 minutes.\n\nThanks!"
    from_email = "noreply@example.com"
    send_mail(
        subject,
        message,
        from_email,
        # "noreply@sandbox781b98c0491f446194023f66a9dafcc2.mailgun.org", # from
        [to_email], # To
        fail_silently=False,
    )

    # For development/testing, you can also print the OTP directly
    # or store it somewhere accessible for testing
    if settings.DEBUG:
        print(f"DEBUG - OTP for {to_email}: {otp_code}")
    
    return True


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


def generate_otp(length=4):
    """Generate a random 4-digit OTP."""
    return ''.join([str(random.randint(0, 9)) for _ in range(length)])



# Redis helper
def store_otp(user_id, otp_code):
    """Store OTP in Redis with an expiry time."""
    cache_key = f"otp:{user_id}"
    cache.set(cache_key, otp_code, timeout=300) # 5 minutes expiration

    # For development/testing without Redis
    if not cache.get(cache_key) and settings.DEBUG:
        # Follow in memory storage if cache is not working

        if not hasattr(store_otp, 'otp_store'):
            store_otp.otp_store = {}
        store_otp.otp_store[cache_key] = otp_code
        print(f"DEBUG - OTP stored in memory for {user_id}: {otp_code}")


def verify_otp(user_id, otp_code):
    """Verify the OTP from Redis and delete if correct."""
    cache_key = f"otp:{user_id}"
    stored_otp = cache.get(cache_key)
    if stored_otp == otp_code:
        cache.delete(cache_key)  # Delete OTP after verification
        return True
    
    # For development/testing without Redis
    if settings.DEBUG and hasattr(store_otp, 'otp_store'):
        stored_otp = store_otp.otp_store.get(user_id)
        if stored_otp and store_otp == otp_code:
            # Delete OTP after verification
            del store_otp.otp_store[cache_key]
            return True
    return False


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