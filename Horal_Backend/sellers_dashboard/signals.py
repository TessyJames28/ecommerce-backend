from .models import (
    ProductRatingSummary, RawSale,
    SalesAdjustment
)
from django.dispatch import receiver
from django.db.models.signals import post_save, post_delete
from django.db.models import Count, Avg
from ratings.models import UserRating
from orders.models import Order, OrderItem
from django.utils.timezone import now
from products.models import ProductIndex, ProductVariant


@receiver(post_save, sender=UserRating)
def update_rating_summary(sender, instance, **kwargs):
    product = instance.product
    seller = product.shop.owner.user

    agg = UserRating.objects.filter(product=product).aggregate(
        avg=Avg('rating'),
        total=Count('id')
    )

    summary, created = ProductRatingSummary.objects.get_or_create(product=product, defaults={"seller": seller})
    summary.average_rating = agg['avg'] or 0.0
    summary.total_ratings = agg['total']
    summary.seller = seller  # ensure update even if reassigned
    summary.save()


@receiver(post_save, sender=OrderItem)
def update_raw_sales(sender, instance, **kwargs):
    """
    Signal to populate raw order model once an order is paid for
    Will skip if RawSale already exists for that order
    """
    status_req = ["paid", "shipped", "at_pick_up", "delivered"]
    order = instance.order
    
    if order.status not in status_req:
        return
    
    # Avoid duplicating entries if already populated
    # Prepare is_valid flag
    is_valid = not instance.is_returned
    
    variant = instance.variant
    product_index = ProductIndex.objects.get(id=variant.object_id)
    product = product_index.get_real_product()

    raw_sale, created = RawSale.objects.get_or_create(
        order_item=instance,
        defaults={
            "shop":variant.shop,
            "variant": variant,
            "quantity": instance.quantity,
            "category": product.category,
            "product": product_index,
            "unit_price": instance.unit_price,
            "is_valid": is_valid,
            "total_price": instance.quantity * float(instance.unit_price),
            "created_at": order.created_at
        }
    )

    # If it's not newly created, update the fields you need
    if not created and instance.is_returned and raw_sale.is_valid != is_valid:
        raw_sale.is_valid = False
        if raw_sale.processed_flags:
            reset_flags = {k: False for k in raw_sale.processed_flags.keys()}
        else:
            reset_flags = {}

        raw_sale.invalidated_at = now()
        raw_sale.processed_flags = reset_flags
        raw_sale.save(update_fields=["is_valid", "invalidated_at", "processed_flags"])

        SalesAdjustment.objects.create(raw_sales=raw_sale)



# @receiver(post_save, sender=OrderItem)
# def handle_order_status_change(sender, instance, **kwargs):
#     """Track cancellations and returns for sales validity."""

#     # Only proceed if this is a new return (not already invalidated)
#     if instance.is_returned:
#         raw_sales = RawSale.objects.filter(
#             order_item=instance,
#             variant=instance.variant,
#             is_valid=True
#         )
#         for sale in raw_sales:
#             # Reset processed_flags to all False
#             if sale.processed_flags:
#                 reset_flags = {k: False for k in sale.processed_flags.keys()}
#             else:
#                 reset_flags = {}

#             sale.is_valid = False
#             sale.invalidated_at = now()
#             sale.processed_flags = reset_flags
#             sale.save(update_fields=["is_valid", "invalidated_at", "processed_flags"])

#             # Prevent duplicate adjustment records
#             if not SalesAdjustment.objects.filter(raw_sales=sale).exists():
#                 SalesAdjustment.objects.create(raw_sales=sale)

