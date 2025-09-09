from django.utils import timezone
from django.db import transaction
from products.utils import update_quantity
from payment.utils import update_order_status
from payment.models import OrderStatusLog
from logistics.utils import group_order_items_by_seller
import uuid


def approve_return(order_return_request, user):
    """
    Handles admin manual approval plus restocking of order
    quantity upon cancellation and return approval
    after assessment of returned product and reason
    """
    from .models import OrderReturnRequest
    with transaction.atomic():
        req = order_return_request
        order_item = req.order_item

        variant = order_item.variant
        variant.stock_quantity += order_item.quantity
        variant.save()
        update_quantity(variant.product)

        update_order_status(
            req, OrderReturnRequest.Status.APPROVED,
            user, OrderStatusLog.OrderType.ORDERRETURNREQUEST
        )

        req.status = OrderReturnRequest.Status.APPROVED
        req.processed_at = timezone.now()
        req.save(update_fields=["status", "processed_at"])


def generate_reference():
    return f"RET-{uuid.uuid4().hex[:8].upper()}"


def create_shipments_for_order(order):
    """
    Group order items by seller and create OrderShipment records.
    Returns list of created shipments.
    """
    from .models import OrderShipment
    grouped = group_order_items_by_seller(order)
    shipments = []

    for seller, data in grouped.items():
        items = data["items"]

        total_price = sum(i.unit_price * i.quantity for i in items)
        total_weight = data["weight"]
        total_quantity = sum(i.quantity for i in items)

        shipment = OrderShipment.objects.create(
            order=order,
            seller=seller,
            quantity=total_quantity,
            total_price=total_price,
            total_weight=total_weight
        )

        # Attach items to this shipment
        for item in items:
            shipment.items.add(item)
        shipments.append(shipment)

    return shipments


def get_consistent_checkout_payload(order):
    """Ensure consistent checkout payload"""
    shipments = []

    for shipment in order.shipments.all():
        shipment_data = {
            "shipment_id": str(shipment.id),
            "seller": shipment.seller.user.full_name,
            "shipping_cost": str(getattr(shipment, "shipping_cost", 0)),
            "items": []
        }

        for item in shipment.items.all():
            variant_obj = item.variant
            product_title = getattr(getattr(variant_obj, "product", None), "title", str(variant_obj))
            product_image = getattr(getattr(variant_obj, "product", None), "image", str(variant_obj))

            shipment_data["items"].append({
                "item_id": str(item.id),
                "product": product_title,
                "image": product_image,
                "unit_price": str(item.unit_price),
                "quantity": item.quantity,
            })

        shipments.append(shipment_data)

    return shipments

