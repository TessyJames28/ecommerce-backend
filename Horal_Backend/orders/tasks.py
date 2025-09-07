from celery import shared_task
from .order_utils import (
    cancel_expired_pending_orders,
    automatic_order_completion
)
from orders.models import OrderItem, OrderShipment, Order
from sellers.models import SellerKYC, SellerKYCAddress
from logistics.utils import create_gigl_shipment_for_shipment
from shops.models import Shop
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


@shared_task
def expire_pending_orders_task():
    """
    Celery task to cancel pending orders older than 30 minutes.
    """
    cancel_expired_pending_orders()
    logger.info("✅ Expired pending orders processed.")


@shared_task
def auto_complete_orders_tasks():
    """
    Celery tasks to auto complete orders more than or equal 3 days
    """
    automatic_order_completion()
    logger.info("✅ Automatic order completion processed.")


@shared_task
def create_gigl_shipment_on_each_shipment(order_id):
    """
    Task to auto-create GIGL shipments when
    an order is markedas PAID
    """
       
    try:
        order = Order.objects.get(id=order_id)
    except Order.DoesNotExist as e:
        logger.error(f"Order with ID {order_id} does not exist: {str(e)}")
        return
    except Exception as e:
        logger.error(f"Error retrieving order with ID {order_id}: {str(e)}")

    # call GIGL API
    try:
        result = create_gigl_shipment_for_shipment(str(order.id))
    except Exception as e:
        logger.error(f"Error creating GIGL shipment for order {order.id}: {str(e)}")

    
    if result:
        logger.info(f"GIGL Shipment created for order {order.id}")
    else:
        logger.error(f"Failed to create GIGL shipment for order {order.id}")


@shared_task
def check_delivered_shipments():
    """
    Handles reminders per shipment (2h, 24h, 48h)
    and auto-completion per item (72h).
    """
    from .signals import shipment_delivered
    now = timezone.now()

    # --- Reminders per shipment ---
    reminder_windows = {
        "2h": (now - timedelta(hours=4), now - timedelta(hours=2)),
        "24h": (now - timedelta(hours=25), now - timedelta(hours=24)),
        "48h": (now - timedelta(hours=49), now - timedelta(hours=48)),
    }

    for label, (start, end) in reminder_windows.items():
        flag = f"reminder_{label}_sent"
        shipments = OrderShipment.objects.filter(
            status__in=[
                OrderShipment.Status.DELIVERED_TO_CUSTOMER_ADDRESS,
                OrderShipment.Status.DELIVERED_TO_PICKUP_POINT,
                OrderShipment.Status.DELIVERED_TO_TERMINAL,
            ],
            delivered_at__gte=start,
            delivered_at__lt=end,
        ).exclude(**{flag: True})

        for shipment in shipments:
            shipment_delivered.send(sender=OrderShipment, shipment=shipment, reminder=label)
            setattr(shipment, flag, True)
            shipment.save(update_fields=[flag])

    # --- Notify already auto-completed shipments ---
    auto_shipments = OrderShipment.objects.filter(auto_completion=True)

    for shipment in auto_shipments:
        shipment_delivered.send(sender=OrderShipment, shipment=shipment)


