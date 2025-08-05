from django.utils import timezone
from django.db import transaction
from products.utils import update_quantity
from .models import Order
from payment.utils import update_order_status

def approve_return(order_return_request, user):
    """
    Handles admin manual approval plus restocking of order
    quantity upon cancellation and return approval
    after assessment of returned product and reason
    """
    with transaction.atomic():
        req = order_return_request
        order = req.order

        for item in order.order_items.all():
            variant = item.variant
            variant.stock_quantity += item.quantity
            variant.save()
            update_quantity(variant.product)

        update_order_status(order, Order.Status.CANCELLED, user)
        req.approved = True
        req.processed_at = timezone.now()
        req.save()

