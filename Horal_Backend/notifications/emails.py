from django.core.mail import send_mail
from django.conf import settings
import requests
from .tasks import send_email_task


def send_registration_otp_email(to_email, otp_code, name):
    """Send an OTP email to the user."""
    # subject = 'Your OTP Code'
    # message = (
    #     f"Hi there,\n\n"
    #     f"Here is your OTP code from Horal: {otp_code}\n"
    #     f"This code will expire in 5 minutes.\n\n"
    #     f"If you didn't request this code, please ignore this email.\n\n"
    #     f"Thanks,\n"
    #     f"The Horal Team"
    # )
    from_email = f"Horal <{settings.DEFAULT_FROM_EMAIL}>"

    send_email_task.delay(
        recipient=to_email,
        subject="Horal Registration Verification",
        from_email=from_email,
        template_name="notifications/emails/otp_email.html",
        context={
            "user": name,
            "title": "Your One-Time Passcode",
            "body_text": "This is your one-time Horal verification code. Enter this code below to complete your registration. Code expires in 5 minutes.",
            "otp": otp_code
        }
    )


def send_registration_url_email(to_email, url, name):
    """Send registration url email to the user."""

    from_email = f"Horal <{settings.DEFAULT_FROM_EMAIL}>"

    send_email_task.delay(
        recipient=to_email,
        subject="Horal Registration Verification",
        from_email=from_email,
        template_name="notifications/emails/otp_email.html",
        context={
            "user": name,
            "title": "Your One-Time Verification Link",
            "body_text": "This is your one-time Horal verification link. Click the link below to complete your registration. Link expires in 24hours.",
            "otp": url
        }
    )


def send_otp_email(to_email, otp_code, name):
    """Send an OTP email to the user."""
    from_email = f"Horal <{settings.DEFAULT_FROM_EMAIL}>"

    send_email_task.delay(
        recipient=to_email,
        subject="Password Reset OTP",
        from_email=from_email,
        template_name="notifications/emails/otp_email.html",
        context={
            "user": name,
            "title": "Password Reset Passcode",
            "body_text": "This is your one-time password reset passcode. Code expires in 5 minutes. Please do not share it with anyone.",
            "otp": otp_code,
            "footer_note": "If you didn’t request a password reset, please ignore this email."
        }
    )


def send_reauth_email(to_email, otp_code, subject, name):
    """Send an OTP email to the user."""
    from_email = f"Horal <{settings.DEFAULT_FROM_EMAIL}>"

    send_email_task(
        recipient=to_email,
        subject=subject,
        from_email=from_email,
        template_name="notifications/emails/otp_email.html",
        context={
            "user": name,
            "title": subject,
            "body_text": "This is your one-time password reset passcode. Code expires in 5 minutes. Please do not share it with anyone.",
            "otp": otp_code,
            "footer_note": "If you didn’t request a reauthentication to your dashboard, please ignore this email."
        }
    )


def send_refund_email(user_email, order_id, username):
    """
    Function to send confirmation for order cancellation
    and refund
    """
    subject = "Refund Processed Successfully"
    body_paragraphs = [
        f"Your return for order {order_id} has been approved and refund is being processed",
        "We are sorry for this unfavorable experience and know the next purchase will be exception.",
        "We hope to see your next purchase soon."
    ]

    send_email_task.delay(
        recipient=user_email,
        subject=subject,
        from_email=f"Horal <{settings.DEFAULT_FROM_EMAIL}>",
        template_name="notifications/emails/general_email.html",
        context={
            "user": username,
            "title": subject,
            "body_paragraphs": body_paragraphs
        }
    )


def send_kyc_info_completed_email(user):
    """
    Send email to users on successful kyc verification submission
    """
    from users.models import CustomUser

    # Get user details
    try:
        user = CustomUser.objects.get(id=user)
    except CustomUser.DoesNotExist:
        pass

    subject = "KYC Verification Submitted"
    username = user.full_name
    email = user.email
    body_paragraphs = [
        "You have successfully submitted all required KYC information.",
        "We’re reviewing them and will notify you once verification is complete.",
        "We appreciate your interest in selling on Horal."
    ]

    send_email_task.delay(
        recipient=email,
        subject=subject,
        from_email=f"Horal Marketplace <{settings.DEFAULT_FROM_EMAIL}>",
        template_name="notifications/emails/general_email.html",
        context={
            "user": username,
            "title": subject,
            "body_paragraphs": body_paragraphs
        }
    )


def send_kyc_final_status_email(user, status):
    """
    Send dynamic KYC status email to user.
    :param user: CustomUser instance
    :param status: str, one of ["verified", "failed"]
    """
    from users.models import CustomUser

    # Get user details
    try:
        user = CustomUser.objects.get(id=user)
    except CustomUser.DoesNotExist:
        pass
    
    subject = ""
    body_paragraphs = []
    cta = None
    email = user.email
    username = user.full_name

    if status == "verified":
        subject = "KYC Verification Successful"
        body_paragraphs = [
            "Congratulations! Your KYC verification has been successfully completed."
            " Your account is now KYC-verified, unlocking full access to Horal."
        ]
        cta = {
            "text": "Start Listing More Products",
            "url": "https://www.horal.ng/sellers-dashboard/shop-products"
        }

    elif status == "failed":
        subject = "KYC Verification Failed"
        body_paragraphs = [
            "Unfortunately, your KYC verification could not be completed.",
            "Please re-submit clear and valid documents to complete your KYC.",
            "For assistance, <a href='mailto:support@mail.horal.ng'>contact support</a>."

        ]
        cta = {
            "text": "Retry Verification",
            "url": "https://www.horal.ng/kyc-verification"
        }

    else:
        raise ValueError("Invalid KYC status")

    send_email_task.delay(
        recipient=email,
        subject=subject,
        from_email=f"Horal Marketplace <{settings.DEFAULT_FROM_EMAIL}>",
        template_name="notifications/emails/general_email.html",
        context={
            "user": username,
            "title": subject,
            "body_paragraphs": body_paragraphs,
            "cta": cta
        }
    )


def send_seller_registration_email(user, status):
    """
    Send seller registration email to user.
    :param user: CustomUser instance
    :param status: str, one of ["True", "False"]
    """
    from users.models import CustomUser

    # Get user details
    try:
        user = CustomUser.objects.get(id=user)
    except CustomUser.DoesNotExist:
        pass
    
    subject = ""
    body_paragraphs = []
    cta = None
    email = user.email
    username = user.full_name

    if status == True:
        subject = "Seller Registration Successful"
        body_paragraphs = [
            "Congratulations! Your seller registration has been successfully completed."
            " Your account is now partially verified as a seller. You can now list up to 5 products on Horal."
            "To unlock full seller privileges, please complete your KYC verification."
        ]
        cta = {
            "text": "Start Listing Your Products",
            "url": "https://www.horal.ng/sellers-dashboard/shop-products"
        }

    send_email_task.delay(
        recipient=email,
        subject=subject,
        from_email=f"Horal Marketplace <{settings.DEFAULT_FROM_EMAIL}>",
        template_name="notifications/emails/general_email.html",
        context={
            "user": username,
            "title": subject,
            "body_paragraphs": body_paragraphs,
            "cta": cta
        }
    )
