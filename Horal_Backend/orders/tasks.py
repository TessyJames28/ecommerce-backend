from celery import shared_task
from .order_utils import (
    cancel_expired_pending_orders,
    authomatic_order_completion
)
from orders.models import OrderItem, OrderShipment, Order
from sellers.models import SellerKYC, SellerKYCAddress
from logistics.utils import create_gigl_shipment_for_shipment
from shops.models import Shop
from django.utils import timezone
from datetime import timedelta

@shared_task
def expire_pending_orders_task():
    """
    Celery task to cancel pending orders older than 30 minutes.
    """
    cancel_expired_pending_orders()
    print("✅ Expired pending orders task completed.")


@shared_task
def auto_complete_orders_tasks():
    """
    Celery tasks to auto complete orders more than or equal 3 days
    """
    authomatic_order_completion()
    print("✅ Orders delivered over the past 3 days marked as completed.")


@shared_task
def create_gigl_shipment_on_each_shipment(order_id):
    """
    Task to auto-create GIGL shipments when
    an order is markedas PAID
    """
    print("Task to create shipment called")
       
    try:
        order = Order.objects.get(id=order_id)
    except Order.DoesNotExist:
        print(f"No order found for this order id: {order_id}")
        return
    except Exception as e:
        print(f"General error: {e}")

    # call GIGL API
    print("About to create the shipment")
    result = create_gigl_shipment_for_shipment(str(order.id))
    if result:
        print(f"Shipment creation successful")
    else:
        print("Shipment creation failed")


