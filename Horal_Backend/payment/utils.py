from django.conf import settings
from .models import PaystackTransaction, OrderStatusLog
from notifications.emails import send_refund_email
from .models import OrderStatusLog
from django.contrib.contenttypes.models import ContentType
from wallet.models import Bank
import requests


def trigger_refund(reference, amount=None, retry=False):
    """
    Trigger refund for a specific transaction (full or partial)
    If amount is provided, a partial refund is processed.
    """
    url = "https://api.paystack.co/refund"
    headers = {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "transaction": reference
    }

    # Pass the item price (in kobo) if refunding per item
    if amount:
        data["amount"] = int(amount * 100)

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


def update_order_status(order, new_status, changed_by=None, \
                        order_type=None, force=False):
    """
    Update the order status and log the change.
    
    Args:
        order (Order): The order instance
        new_status (str): New status (e.g. 'paid', 'cancelled')
        changed_by (User or None): The user who triggered the change
    """
    from orders.models import Order, OrderReturnRequest

    if force or order.status != new_status:

        if order_type == OrderStatusLog.OrderType.ORDERRETURNREQUEST:
            OrderStatusLog.objects.create(
                content_type=ContentType.objects.get_for_model(OrderReturnRequest),
                object_id=order.id,
                old_status=order.status,
                order_type=order_type,
                new_status=new_status,
                changed_by=changed_by
            )
        else:
            print("Updating order status in Orderlog")
            try:
                log, created = OrderStatusLog.objects.get_or_create(
                    content_type=ContentType.objects.get_for_model(Order),
                    object_id=order.id,
                    old_status=order.status,
                    new_status=new_status,
                    changed_by=changed_by
                )
            except Exception as e:
                print(f"Order log not creating: {str(e)}")
        order.status = new_status
        order.save(update_fields=["status"])


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
