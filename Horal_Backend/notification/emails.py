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
    