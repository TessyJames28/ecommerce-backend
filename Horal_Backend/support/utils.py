from django.contrib.contenttypes.models import ContentType
from django.utils.timezone import now
from orders.models import OrderReturnRequest
import requests
from django.conf import settings
import uuid, re

def create_message_for_instance(instance):
    from .models import Message, SupportAttachment, Support
    """Helper to create a Message for any parent instance"""
    model_class = type(instance)
    content_type = ContentType.objects.get_for_model(model_class)
    subject = generate_received_subject(instance)
    # Determine subject and body
    if isinstance(instance, Support):
        body = instance.body
        sender = getattr(instance, "customer", None)
    elif isinstance(instance, OrderReturnRequest):
        print("In returns instance")
        body = instance.reason
        sender = instance.order_item.order.user
    else:
        return

    message = Message.objects.create(
        parent=instance,
        content_type=content_type,
        object_id=instance.id,
        sender=sender,
        subject=subject,
        body=body,
        from_staff=False,
        sent_at=now()
    )

    attachments = getattr(instance, "_attachments_data", [])
    
    for att in attachments:
        SupportAttachment.objects.create(message=message, **att)


def generate_received_subject(instance):
    """
    Generate the email subject including the unique reference.
    Works for:
    - Support tickets
    - OrderReturnRequest tickets
    - Generic Tickets referencing Support or OrderReturnRequest
    """
    # Determine model type
    from .models import Support, Tickets
    from orders.models import OrderReturnRequest
    # Determine the actual object to reference
    try:
        related_obj = getattr(instance, 'parent', instance)
    except Tickets.DoesNotExist:
        related_obj = instance

    if isinstance(related_obj, Support):
        reference = getattr(related_obj, "reference", "N/A")
        subject_text = getattr(related_obj, "subject", "No subject")
        return f"Re: [{reference}] {subject_text}"

    elif isinstance(related_obj, OrderReturnRequest):
        reference = getattr(related_obj, "reference", "N/A")
        order_item = getattr(related_obj, "order_item", "N/A")
        return f"Re: [{reference}] for return request {order_item}"



def generate_reference():
    return f"SUP-{uuid.uuid4().hex[:8].upper()}"


def get_service_token(email, password):
    """
    Log in with service account credentials and return an access token.
    """
    login_url = f"{settings.API_BASE_URL}user/login/"
    payload = {
        "email": email,
        "password": password,
    }

    response = requests.post(login_url, data=payload)
    print(f"login response: {response}")

    if response.status_code == 200:
        data = response.json().get("data", {})
        print(f"Data: {data}")
        # adjust depending on how your login response looks
        tokens = data.get("tokens", {})
        print(f"Access token: {tokens.get("access")}")
        return tokens.get("access")

    raise Exception(f"Failed to get service token: {response.status_code}, {response.text}")


def handle_mailgun_attachments(attachments, msg, type=None):
    """Function to handle attachments from mailgun email webhook"""
    from .models import SupportAttachment
    if type == "returns":
        password = settings.RETURNS_PASSWORD
        email = settings.RETURNS_EMAIL
        token = get_service_token(email, password)
    else:
        password = settings.SUPPORT_PASSWORD
        email = settings.SUPPORT_EMAIL
        token = get_service_token(email, password)
    print(f"Token: {token}")
    headers = {"Authorization": f"Bearer {token}"}

    for key in attachments:
        file_list = attachments.getlist(key)
        for f in file_list:
            response = requests.post(
                f"{settings.API_BASE_URL}media/upload/",
                headers=headers,
                files={"file": (f.name, f, f.content_type)},
            )

            if response.status_code == 201:
                uploaded_asset = response.json().get("url")
                SupportAttachment.objects.create(
                    message=msg,
                    url=uploaded_asset
                )
                print(f"URL Added: {uploaded_asset}")
            else:
                print("Upload failed:", response.status_code, response.text)


def extract_reply_body(full_body: str) -> str:
    """
    Extract only the new message content from an email reply body.
    Stops at the first quoted line or common reply patterns.
    """
    # Split at common reply markers
    reply_markers = [
        r"\r?\nOn .* wrote:",       # On Thu, 21 Aug 2025, Someone <...> wrote:
        r"\r?\n> ",                 # quoted lines
        r"\r?\nFrom: .*",           # From: ...
        r"\r?\nSent: .*",           # Sent: ...
    ]
    pattern = "|".join(reply_markers)
    split_body = re.split(pattern, full_body, flags=re.IGNORECASE)
    return split_body[0].strip()



# CustomUser.objects.create_user(
#     full_name="returns-bot",
#     email="returns@mail.horal.ng",
#     password="Returns@123",
#     is_staff=True,
# )
