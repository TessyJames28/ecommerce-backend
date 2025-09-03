# tasks.py
from celery import shared_task
from django.core.mail import send_mail
from .models import Notification
from django.conf import settings

@shared_task
def send_notification_email(notification_id):
    """Celery tasks to send notification email"""
    try:
        notification = Notification.objects.get(id=notification_id)
        send_mail(
            subject=notification.title,
            message=notification.message,
            from_email=f"Support <support@{settings.MAILGUN_DOMAIN}>",
            recipient_list=[notification.user.email],
        )
    except Notification.DoesNotExist:
        pass


@shared_task
def send_email_task(recipient, subject, body, from_email=None):
    """
    Send an email asynchronously.
    
    :param recipient: str or list of email addresses
    :param subject: str
    :param body: str
    :param from_email: optional sender email, defaults to settings.DEFAULT_FROM_EMAIL
    """
    if from_email is None:
        from_email = settings.DEFAULT_FROM_EMAIL

    if isinstance(recipient, str):
        recipient = [recipient]

    send_mail(
        subject=subject,
        message=body,
        from_email=from_email,
        recipient_list=recipient,
        fail_silently=False
    )

