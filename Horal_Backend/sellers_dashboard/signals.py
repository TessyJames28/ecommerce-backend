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
    status_req = ["paid", "shipped", "at_pick_up", "delivered", "cancelled"]
    order = instance.order
    if order.status not in status_req:
        return
    
    # Avoid duplicating entries if already populated
    if RawSale.objects.filter(order=order, variant=instance.variant).exists():
        return
    
    variant = instance.variant
    product_index = ProductIndex.objects.get(id=variant.object_id)
    product = product_index.get_real_product()

    if instance.order.status in status_req and\
        (not instance.is_return_requested or not instance.is_returned):
        RawSale.objects.create(
            shop=variant.shop,
            order=order,
            category=product.category,
            product=product_index,
            variant=variant,
            quantity=instance.quantity,
            unit_price=instance.unit_price,
            total_price=instance.quantity * float(instance.unit_price),
            created_at=order.created_at
        )


@receiver(post_save, sender=Order)
@receiver(post_save, sender=OrderItem)
def handle_order_status_change(sender, instance, **kwargs):
    """Track cancellations and returns for sales validity."""

    # Handle cancelled orders
    if isinstance(instance, Order) and instance.status == Order.Status.CANCELLED:
        raw_sales = RawSale.objects.filter(order=instance, is_valid=True)
        for sale in raw_sales:
            sale.is_valid = False
            sale.invalidated_at = now()
            sale.save(update_fields=["is_valid", "invalidated_at"])
            SalesAdjustment.objects.create(raw_sales=sale)
        return

    # Handle returned items (only mark invalid when actually returned/completed)
    if isinstance(instance, OrderItem) and instance.is_returned:
        raw_sales = RawSale.objects.filter(
            order=instance.order,
            variant=instance.variant,
            is_valid=True
        )
        for sale in raw_sales:
            sale.is_valid = False
            sale.invalidated_at = now()
            sale.save(update_fields=["is_valid", "invalidated_at"])
            SalesAdjustment.objects.create(raw_sales=sale)


@receiver([post_save, post_delete], sender=RawSale)
def reset_processed_flags(sender, instance, **kwargs):
    if kwargs.get('raw', False):  # skip during fixture loading
        return

    if instance.processed_flags:
        # Set all existing keys to False
        reset_flags = {k: False for k in instance.processed_flags.keys()}
    else:
        reset_flags = {}

    RawSale.objects.filter(pk=instance.pk).update(processed_flags=reset_flags)
