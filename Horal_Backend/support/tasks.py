from celery import shared_task
import requests
from django.conf import settings
from celery import shared_task
from django.template.loader import render_to_string
from django.conf import settings
import requests

@shared_task
def send_support_email(to_email, subject, template=None, context=None, ticket_type=None, attachment=None):
    """
    Celery task to send support email using a template or plain text.
    
    Parameters:
        to_email: recipient email
        subject: email subject
        template: Django template path (optional)
        context: context dict for rendering template (optional)
        ticket_type: "support", "returns", etc.
        attachment: file path (optional)
    """
    # Determine sender
    if ticket_type == "support":
        from_email = f"Horal Support <support@{settings.MAILGUN_DOMAIN}>"
    elif ticket_type == "returns":
        from_email = f"Horal Returns <returns@{settings.MAILGUN_DOMAIN}>"
    else:
        return

    # Render template if provided, else use plain text body from context
    if template and context:
        body = render_to_string(template, context)
    elif context and "body_paragraphs" in context:
        # fallback plain text
        body = "\n\n".join(context["body_paragraphs"])
    else:
        body = context.get("body", "") if context else ""

    # Prepare Mailgun data
    data = {
        "from": from_email,
        "to": [to_email],
        "subject": subject,
        "html": body,  # send HTML content
        "text": body   # also include plain text for clients that don't render HTML
    }

    # Optional attachment
    files = [("attachment", (attachment, open(attachment, "rb").read()))] if attachment else None

    # Send email via Mailgun
    response = requests.post(
        settings.MAILGUN_API_URL,
        auth=("api", settings.MAILGUN_API_KEY),
        data=data,
        files=files
    )

    return response.status_code, response.text

    