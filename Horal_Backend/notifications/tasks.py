# tasks.py
from celery import shared_task
from django.core.mail import send_mail
from .models import Notification
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

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
def send_email_task(
    recipient, 
    subject, 
    body=None, 
    from_email=None, 
    template_name=None, 
    context=None
):
    """
    Send an email asynchronously.
    
    :param recipient: str or list of email addresses
    :param subject: str
    :param body: plain text message (optional if template_name provided)
    :param from_email: sender email, defaults to settings.DEFAULT_FROM_EMAIL
    :param template_name: optional Django template path for HTML email
    :param context: dict context to render template
    """
    from_email = from_email or settings.DEFAULT_FROM_EMAIL

    if isinstance(recipient, str):
        recipient = [recipient]

    if template_name:
        context = context or {}
        html_content = render_to_string(template_name, context)
        msg = EmailMultiAlternatives(subject=subject, body=body or "", from_email=from_email, to=recipient)
        msg.attach_alternative(html_content, "text/html")
        msg.send()
    else:
        # fallback to plain text
        from django.core.mail import send_mail
        send_mail(
            subject=subject,
            message=body or "",
            from_email=from_email,
            recipient_list=recipient,
            fail_silently=False
        )


