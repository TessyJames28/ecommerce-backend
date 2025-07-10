from django.conf import settings
from .models import PaystackTransaction, OrderStatusLog
from notification.emails import send_refund_email
from .models import OrderStatusLog
import requests

def trigger_refund(reference, retry=False):
    """Function to trigger refund for cancelled order"""
    url = "https://api.paystack.co/refund"
    headers = {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "transaction": reference
    }

    response = requests.post(url, headers=headers, json=data)
    result = response.json()

    try:
        tx = PaystackTransaction.objects.get(reference=reference)
        tx.refund_attempted = True
        tx.refund_response = result
        if result.get("status"):
            tx.refund_successful = True
            send_refund_email(tx.email, tx.order.id)
        tx.save()
    except PaystackTransaction.DoesNotExist:
        pass

    return result


def update_order_status(order, new_status, changed_by=None, force=False):
    """
    Update the order status and log the change.
    
    Args:
        order (Order): The order instance
        new_status (str): New status (e.g. 'paid', 'cancelled')
        changed_by (User or None): The user who triggered the change
    """
    if force or order.status != new_status:
        OrderStatusLog.objects.create(
            order=order,
            old_status=order.status,
            new_status=new_status,
            changed_by=changed_by
        )
        order.status = new_status
        order.save()
