from .models import (
    ProductRatingSummary, RawSale,
    SalesAdjustment
)
from django.dispatch import receiver
from django.db.models.signals import post_save
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
    order = instance.order
    if order.status not in ["paid", "shipped", "delivered"]:
        return
    
    # Avoid duplicating entries if already populated
    if RawSale.objects.filter(order=order, variant=instance.variant).exists():
        return
    
    variant = instance.variant
    product_index = ProductIndex.objects.get(id=variant.object_id)
    product = product_index.get_real_product()

    if instance.order.status in ["paid", "shipped", "delivered"]:
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
def handle_order_status_change(sender, instance, **kwargs):
    """Signal to track changes in order status"""
    if instance.status in ["cancelled", 'returned']:
        RawSale.objects.filter(order=instance).update(
            is_valid=False,
            invalidated_at=now()
        )
        value = RawSale.objects.filter(order=instance).first()

        if value:
            # record data in Sales Adjustment table
            SalesAdjustment.objects.create(
                raw_sales=value
            )
