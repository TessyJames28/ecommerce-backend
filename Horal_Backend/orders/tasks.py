from celery import shared_task
from .order_utils import (
    cancel_expired_pending_orders,
    authomatic_order_completion
)

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
