from django.dispatch import receiver
from django.db.models.signals import post_save
from .models import UserRating


@receiver(post_save, sender=UserRating)
def update_order_on_product_review(sender, instance, **kwargs):
    """
    Signal to update order item once a user leaves a review.
    Marks the order item as completed and the shipment as auto_completed
    only when all items in that shipment have been reviewed.
    """
    item = instance.order_item
    shipment = item.shipment

    if not shipment:
        return  # in case shipment is missing for some reason

    # Mark this specific item as completed
    item.is_completed = True
    item.save(update_fields=["is_completed"])

    # Check if all items in the shipment are reviewed
    all_items = shipment.items.all()
    all_reviewed = all(hasattr(order_item, "order_item") for order_item in all_items)

    if all_reviewed:
        shipment.auto_completion = True
        shipment.save(update_fields=["auto_completion"])

