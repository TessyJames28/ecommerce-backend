from celery import shared_task
from .expire_pending_orders import cancel_expired_pending_orders

@shared_task
def expire_pending_orders_task():
    """
    Celery task to cancel pending orders older than 30 minutes.
    """
    cancel_expired_pending_orders()
    print("✅ Expired pending orders task completed.")