from django.dispatch import receiver
from django.db.models.signals import post_save
from .models import Order, OrderItem, OrderReturnRequest
from support.utils import (
    create_message_for_instance,
    generate_received_subject
)
from notifications.tasks import send_email_task
from django.conf import settings
from django.utils.timezone import now
from users.models import CustomUser


@receiver(post_save, sender=Order)
def update_order_on_delivery(sender, instance, **kwargs):
    """
    Signal to update order item once an order is delivered
    """

    if instance.status == Order.Status.DELIVERED:
        OrderItem.objects.filter(
            order=instance.id
        ).update(delivered_at=instance.updated_at)


@receiver(post_save, sender=OrderReturnRequest)
def send_return_received_email(sender, instance, created, **kwargs):
    """
    Signal to send automated message once a return request is made
    """
    from support.models import Message

    if created:
        subject = generate_received_subject(instance)
        body = f"Hello {instance.order_item.order.user.full_name},\n\n" \
               f"We have received your return request for item {instance.order_item.id}:\n\n" \
               f"{instance.reason}\n\n" \
               "Our team will review it and get back to you shortly." \
               "\n\nNote: All further correspondence will be via this email"

        # Get user email
        returns = OrderReturnRequest.objects.get(
            id=instance.id,
            order_item=instance.order_item
        )

        user = returns.order_item.order.user
        print(f"User: {user}")

        from_email = f"returns@{settings.MAILGUN_DOMAIN}"
        # Trigger async email
        send_email_task.delay(
            recipient=instance.order_item.order.user.email,
            subject=subject,
            body=body,
            from_email=f"Returns <{from_email}>"
        )

        sender = CustomUser.objects.get(email=from_email)

        # Create the message
        Message.objects.create(
            parent=instance,
            sender=sender,
            subject=subject,
            body=body,
            sent_at=now(),
            from_staff=True,
        )
