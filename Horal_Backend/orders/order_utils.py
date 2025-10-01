from django.utils.timezone import now
from django.db import transaction

from .models import Order, OrderShipment
from products.models import ProductVariant
from products.utils import update_quantity
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


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
    products_to_update = set()
    orders_to_update = []

    with transaction.atomic():
        for order in expired_orders:
            for item in order.order_items.all():
                variant = item.variant
                if variant.id not in variants_to_update:
                    variants_to_update[variant.id] = variant
                variant.reserved_quantity = max(variant.reserved_quantity - item.quantity, 0)
                products_to_update.add(variant.product)

            order.status = Order.Status.CANCELLED
            orders_to_update.append(order)
            
            # delete related shipments to keep things clean
            order.shipments.all().delete()

        if variants_to_update:
            ProductVariant.objects.bulk_update(variants_to_update.values(), ['reserved_quantity'])

        # Update product quantities
        for product in products_to_update:
            update_quantity(product)
            
        if orders_to_update:
            Order.objects.bulk_update(orders_to_update, ['status'])

    logger.info(f"{len(orders_to_update)} expired orders processed.")



def automatic_order_completion():
    """
    Automatically complete delivered orders if buyers
    didn't review within 3 days
    """
    completion_time = now() - timedelta(days=3)

    shipments = OrderShipment.objects.filter(
        status__in=[
            OrderShipment.Status.DELIVERED_TO_CUSTOMER_ADDRESS,
            OrderShipment.Status.DELIVERED_TO_PICKUP_POINT,
            OrderShipment.Status.DELIVERED_TO_TERMINAL,
        ],
        delivered_at__lte=completion_time,
        auto_completion=False,  # only process once
    )

    completed_items_count = 0

    for shipment in shipments:
        shipment.auto_completion = True
        shipment.save(update_fields=["auto_completion"])

        for item in shipment.items.filter(is_completed=False):
            item.is_completed = True
            item.save(update_fields=["is_completed"])
            completed_items_count += 1

    logger.info(f"{completed_items_count} order items automatically marked as completed.")

