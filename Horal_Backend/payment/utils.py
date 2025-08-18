from django.conf import settings
from .models import PaystackTransaction, OrderStatusLog
from notification.emails import send_refund_email
from .models import OrderStatusLog
from wallet.models import Bank
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


def fetch_and_store_bank():
    """
    Function to fetch bank details from paystack
    Store in the Bank DB for use
    """
    url = f"{settings.PAYSTACK_BASE_URL}/bank?country=nigeria"
    headers = {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"
    }

    try:
        response = requests.get(url, headers=headers)
        data = response.json()
    except Exception as e:
        raise Exception(f"Paystack bank fetch issue: {e}")

    if data.get("status") is True:
        for bank in data.get("data", []):
            Bank.objects.update_or_create(
                name=bank["name"].strip(),
                defaults={
                    "code": bank["code"],
                    "slug": bank.get("slug"),
                    "active": bank.get("active", True)
                }
            )

        return F"Fetched and store {len(data.get("data", []))} banks."
    else:
        raise Exception(f"Failed to fetch banks: {data}")
    

def get_bank_code(bank_name):
    """Function to get bank code based on provided name"""
    try:
        bank = Bank.objects.get(name__iexact=bank_name.strip())
        return bank.code
    except Bank.DoesNotExist:
        return None
