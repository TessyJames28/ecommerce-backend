from django.dispatch import receiver
from django.db.models.signals import post_save
from .models import UserRating


@receiver(post_save, sender=UserRating)
def update_order_on_product_review(sender, instance, **kwargs):
    """
    Signal to update order item once a user leaves a review
    Marks an order as completed after review
    """

    if instance.rating:
        item = instance.order_item # already an OrderItem object
        item.is_completed = True
        item.save(update_fields=["is_completed"])

