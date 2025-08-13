from django.dispatch import receiver
from django.db.models.signals import post_save
from .models import Order, OrderItem, OrderReturnRequest


@receiver(post_save, sender=Order)
def update_order_on_delivery(sender, instance, **kwargs):
    """
    Signal to update order item once an order is delivered
    """

    if instance.status == Order.Status.DELIVERED:
        OrderItem.objects.filter(
            order=instance.id
        ).update(delivered_at=instance.updated_at)
        