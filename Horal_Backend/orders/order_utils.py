from django.utils.timezone import now
from django.db import transaction

from .models import Order, OrderItem
from products.models import ProductVariant
from datetime import timedelta


def cancel_expired_pending_orders():
    """
    Cancels pending orders older than 30 minutes and updates reserved product variant quantities.
    """
    expired_time = now() - timedelta(minutes=30)
    expired_orders = Order.objects.filter(
        status=Order.Status.PENDING,
        created_at__lte=expired_time
    ).prefetch_related('order_items__variant')

    variants_to_update = {}
    orders_to_update = []

    with transaction.atomic():
        for order in expired_orders:
            for item in order.order_items.all():
                variant = item.variant
                if variant.id not in variants_to_update:
                    variants_to_update[variant.id] = variant
                variant.reserved_quantity = max(variant.reserved_quantity - item.quantity, 0)

            order.status = Order.Status.CANCELLED
            orders_to_update.append(order)

        if variants_to_update:
            ProductVariant.objects.bulk_update(variants_to_update.values(), ['reserved_quantity'])
        if orders_to_update:
            Order.objects.bulk_update(orders_to_update, ['status'])

    print(f"✅ {len(orders_to_update)} expired orders processed.")


def authomatic_order_completion():
    """
    Automatically complete delivered orders if buyers
    Didn't review within 3 days
    """
    completion_time = now() - timedelta(days=3)
    updated_count = OrderItem.objects.filter(
        order__status=Order.Status.DELIVERED,
        delivered_at__lte=completion_time
    ).update(is_completed=True)
    
    print(f"{updated_count} order items automatically marked as completed.")
