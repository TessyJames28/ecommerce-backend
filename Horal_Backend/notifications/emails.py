from django.core.mail import send_mail
from django.conf import settings


def send_otp_email(to_email, otp_code):
    """Send an OTP email to the user."""
    subject = 'Your OTP Code'
    message = (
        f"Hi there,\n\n"
        f"Here is your OTP code from Horal: {otp_code}\n"
        f"This code will expire in 5 minutes.\n\n"
        f"If you didn't request this code, please ignore this email.\n\n"
        f"Thanks,\n"
        f"The Horal Team"
    )

    # from_email = "noreply@example.com"
    send_mail(
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



def send_refund_email(user_email, order_id):
    """
    Function to send confirmation for order cancellation
    and refund
    """
    subject = "Refund Processed Successfully"
    message = f"Your return for order {order_id} has been approved\n and refund processed"
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user_email])


# def send_refund_email(user_email, order_id):
#     subject = "Refund Processed"
#     message = f"Your refund for Order #{order_id} has been processed."
    
#     if settings.DEBUG:
#         print(f"[Email MOCK] To: {user_email} | Subject: {subject} | Message: {message}")
#     else:
#         send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user_email])


def send_kyc_info_completed_email(user):
    """
    Send email to users on successful kyc verification submission
    """
    send_mail(
        subject="KYC Verification Submitted",
        message="You have successfully submitted all required KYC information",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
    )


def send_kyc_final_status_email(user, status):
    """
    Send email that confirms seller veririfation status
    """
    message = "Congratulations! Your KYC was verified." if status == 'verified' else \
              "Unfortunately, your KYC verification failed. Please try again."

    send_mail(
        subject="KYC Verification Confirmation",
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
    )
