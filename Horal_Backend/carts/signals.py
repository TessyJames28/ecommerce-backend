from django.dispatch import Signal, receiver
from notifications.tasks import send_email_task
from products.models import ProductIndex
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

cart_abandoned = Signal()

@receiver(cart_abandoned)
def handle_cart_abandonment(sender, cart, reminder=None, **kwargs):
    """Signal to notify users of abandoned carts with dynamic nudges"""
    if not cart.user:
        return

    items = cart.cart_item.all()
    if not items.exists():
        return

    item_list = []
    for item in items:
        product = ProductIndex.objects.get(id=item.variant.object_id)
        item_list.append({
            "image_url": product.image if product.image else None,
            "name": product.title,
            "quantity": item.quantity,
            "price": item.item_total_price  # template adds ₦
        })

    recipient = cart.user.email
    user = cart.user.full_name
    from_email = f"Horal Cart <{settings.DEFAULT_FROM_EMAIL}>"

    # Set dynamic heading and body based on reminder
    if reminder == "2h":
        heading = "Did You Forget Something?"
        body_paragraphs = [
            "You left some items in your cart. Complete your purchase before they sell out!"
        ]
    elif reminder == "24h":
        heading = "Your Cart is Waiting!"
        body_paragraphs = [
            "Your cart still has items waiting. These products are popular and might sell out soon!"
        ]
    elif reminder == "48h":
        heading = "Last Chance to Grab Your Items!"
        body_paragraphs = [
            "Your cart hasn't been checked out yet. Complete your purchase before it's too late!"
        ]
    else:
        heading = "Did You Forget Something?"
        body_paragraphs = [
            "You have items in your cart. Don't miss out—complete your order today!"
        ]

    # Send email
    send_email_task.delay(
        recipient=recipient,
        subject=heading,
        from_email=from_email,
        template_name="notifications/emails/cart_abandoned_email.html",
        context={
            "user": user,
            "title": heading,
            "body_paragraphs": body_paragraphs,
            "cart_items": item_list,
            "cta": {
                "url": "https://www.horal.ng/cart",
                "text": "Complete Your Order"
            }
        }
    )

    # mark reminder as sent
    if reminder:
        if reminder == '2h':
            cart.reminder_2h_sent = True
        elif reminder == '24h':
            cart.reminder_24h_sent = True
        elif reminder == '48h':
            cart.reminder_48h_sent = True
        cart.save(update_fields=[f'reminder_{reminder}_sent'])

    logger.info(f"Cart abandonment email sent to user (reminder: {reminder})")

