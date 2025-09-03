from celery import shared_task
import requests
from django.conf import settings


@shared_task
def send_support_email(to_email, subject, body, ticket_type=None, attachment=None):
    """Celery tasks to send support email"""
    if ticket_type == "support":
        from_email = f"Support <support@{settings.MAILGUN_DOMAIN}>"
    elif ticket_type == "returns":
        from_email = f"Returns <returns@{settings.MAILGUN_DOMAIN}>",
    data = {
        "from": from_email,
        "to": [to_email],
        "subject": subject,
        "text": body,
    }
    if attachment:
        files = [("attachment", (attachment, open(attachment, "rb").read()))]
    else:
        files = None

    requests.post(
        settings.MAILGUN_API_URL,
        auth=("api", settings.MAILGUN_API_KEY),
        data=data,
        files=files
    )
    