from django.core.mail import send_mail
from django.conf import settings

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
