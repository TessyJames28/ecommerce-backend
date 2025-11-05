from django.dispatch import receiver, Signal
from django.db.models.signals import post_save, post_delete
from .models import (
    Order, OrderShipment,
    OrderReturnRequest,
)
from support.utils import (
    generate_received_subject
)
from collections import defaultdict
from .utils import format_variant
from products.models import ProductIndex, ProductVariant
from notifications.tasks import send_email_task
from django.conf import settings
from django.utils.timezone import now
from users.models import CustomUser
from .tasks import create_fez_shipment_on_each_shipment
import logging

logger = logging.getLogger(__name__)

shipment_delivered = Signal()


@receiver(shipment_delivered)
def handle_shipment_delivered(sender, shipment, reminder=None, **kwargs):
    """
    Signal to send email to customer for delivered shipment,
    either as informational completion notice or review reminder.
    """
    if not shipment.delivered_at:
        return

    # Build product list
    products = []
    for item in shipment.items.all():
        product = ProductIndex.objects.get(id=item.variant.object_id)
        products.append({
            "image": product.image if product.image else None,
            "name": product.title,
            "seller": shipment.seller.user.full_name,
            "review_url": f"https://www.horal.ng/product/{product.slug}",
        })

    recipient = shipment.order.user.email
    user = shipment.order.user.full_name
    from_email = f"Horal Order <{settings.DEFAULT_FROM_EMAIL}>"

    if reminder is None:
        # Informational email for completed order
        heading = "Your Order is Completed!"
        body_paragraphs = [
            "Your order has been marked as completed.",
            "The seller has been paid successfully.",
            "We hope you enjoyed your shopping experience!"
        ]
        show_other_reviews = False  # no review CTA here
    else:
        # Reminder emails for reviews
        show_other_reviews = shipment.order.user.orders.exclude(id=shipment.order.id).filter(
            shipments__status__in=[
                OrderShipment.Status.DELIVERED_TO_CUSTOMER_ADDRESS,
                OrderShipment.Status.DELIVERED_TO_PICKUP_POINT,
                OrderShipment.Status.DELIVERED_TO_TERMINAL
            ]
        ).exists()

        if reminder == "2h":
            heading = "Reminder: Share Your Feedback!"
            body_paragraphs = [
                "It’s been a couple of hours since your order was delivered.",
                "Help us improve by leaving a review for your purchase."
            ]
        elif reminder == "24h":
            heading = "24-Hour Reminder: Leave a Review"
            body_paragraphs = [
                "We noticed you haven’t left a review yet.",
                "Sharing your experience helps other buyers and the seller."
            ]
        elif reminder == "48h":
            heading = "Final Reminder: Tell Us About Your Order"
            body_paragraphs = [
                "This is a friendly final reminder to leave a review for your recent purchase.",
                "Your feedback makes a difference!"
            ]
        else:
            heading = "Your Recent Horal Order"
            body_paragraphs = [
                "We would love to hear your thoughts on your recent purchase."
            ]

    send_email_task.delay(
        recipient=recipient,
        subject=heading,
        from_email=from_email,
        template_name="notifications/emails/review_order_email.html",
        context={
            "user": user,
            "heading": heading,
            "body_paragraphs": body_paragraphs,
            "products": products,
            "show_other_reviews": show_other_reviews,
        }
    )

    logger.info(f"Shipment email sent to user (reminder: {reminder})")


@receiver(post_save, sender=OrderReturnRequest)
def send_return_received_email(sender, instance, created, **kwargs):
    """
    Signal to send automated message once a return request is made
    """
    from support.models import Message

    if created:
        subject = generate_received_subject(instance)
        body = f"We have received your return request for item #{instance.order_item.id} " \
                "Our team will review and update you within 7 business days"

        # Get user email
        returns = OrderReturnRequest.objects.get(
            id=instance.id,
            order_item=instance.order_item
        )

        user = returns.order_item.order.user

        from_email = f"returns@{settings.MAILGUN_DOMAIN}"
        # Trigger async email
        body_paragraphs = [
            f"We have received your return request for item {instance.order_item.id}",
            "Our team will review and update you within 7 business days"
        ]
        footer_note = "Note: All further correspondence will be via this email thread"

        send_email_task.delay(
            recipient=instance.order_item.order.user.email,
            subject=subject,
            from_email=f"Horal Returns <returns@{settings.MAILGUN_DOMAIN}>",
            template_name="notifications/emails/general_email.html",
            context={
                "user": instance.order_item.order.user.full_name,
                "title": subject,
                "body_paragraphs": body_paragraphs,
                "footer_note": footer_note
            }
        )

        sender = CustomUser.objects.get(email=from_email)

        # Create the message
        Message.objects.create(
            parent=instance,
            sender=sender,
            subject=subject,
            body=body,
            sent_at=now(),
            from_staff=True,
        )


@receiver(post_save, sender=Order)
def create_fez_shipment_on_paid(sender, instance: Order, created, **kwargs):
    """
    Auto-create GIGL shipments when an order is marked as PAID for the first time,
    and send a customized receipt email. If this is the user's first order, 
    add a special message.
    """

    # Don't trigger on creation only update
    if created or instance.status != Order.Status.PAID:
        return
    
    create_fez_shipment_on_each_shipment.delay(str(instance.id))

    from_email = f"Horal Order <{settings.DEFAULT_FROM_EMAIL}>"
    order_items = []

    for shipment_data in instance.shipments.all():
        for item in shipment_data.items.all(): 
            product = ProductIndex.objects.get(id=item.variant.object_id)
            variant = ProductVariant.objects.get(id=item.variant.id)
            order_items.append({
                "name": product.title,
                "quantity": item.quantity,
                "price": item.total_price,
                "variant": format_variant(variant),
            })

    totals = {
        "product_total": instance.product_total,
        "shipping_total": instance.shipping_total,
        "grand_total": instance.total_amount
    }

    first_paid_order = not Order.objects.filter(
        user=instance.user,
        status=Order.Status.PAID
    ).exclude(id=instance.id).exists()

    if first_paid_order:
        subject = "🎉 Congratulations on Your First Order!"
        body_paragraphs = [
            "Thank you for placing your first order with Horal! 🎉",
            f"Your order #{instance.id} is being processed. We’ll keep you updated.",
            "Here is your receipt:"
        ]
    else:
        subject = "Your Horal Order Receipt"
        body_paragraphs = [
            "Thank you for your purchase!",
            f"Your order #{instance.id} is being processed. We’ll keep you updated.",
            "Here is your receipt:"
        ]

    send_email_task.delay(
        recipient=instance.user.email,
        subject=subject,
        from_email=from_email,
        template_name="notifications/emails/order_receipt_email.html",
        context={
            "user": instance.user.full_name,
            "body_paragraphs": body_paragraphs,
            "order_items": order_items,
            "totals": totals
        }
    )

    
    # ======== Email each seller once with all their items ========

    # Group seller data
    sellers_data = defaultdict(lambda: {
        "email": "",
        "name": "",
        "items": [],
    })

    # Build seller data per shipment
    for shipment in instance.shipments.all():
        seller = shipment.seller
        seller_id = seller.user.id
        
        if seller_id not in sellers_data:
            sellers_data[seller_id]["email"] = seller.user.email
            sellers_data[seller_id]["name"] = seller.user.full_name

        # Add shipment items
        for item in shipment.items.all():
            product = ProductIndex.objects.get(id=item.variant.object_id)
            variant = ProductVariant.objects.get(id=item.variant.id)
            sellers_data[seller_id]["items"].append({
                "name": product.title,
                "quantity": item.quantity,
                "price": f"₦{item.total_price}",
                "variant": format_variant(variant),
            })

    # Send emails to each seller
    for seller_id, data in sellers_data.items():
        seller_subject = f"New order from {instance.user.full_name}"
        body_paragraphs = [
            f"You have a new order from {instance.user.full_name}.",
            f"Order ID: {instance.id}",
            "Here are the items you need to prepare:"
        ]

        send_email_task.delay(
            recipient=data["email"],
            subject=seller_subject,
            from_email=from_email,
            template_name="notifications/emails/order_receipt_email.html",
            context={
                "user": data["name"],
                "body_paragraphs": body_paragraphs,
                "order_items": data["items"]
            }
        )



# @receiver(post_delete, sender=OrderItem)
# def restore_reserved_stock(sender, instance, **kwargs):
#     """
#     Restore reserved stock when an OrderItem is deleted
#     """
#     variant = instance.variant
#     if variant:
#         # Prevent reserved_quantity from going negative
#         if variant.reserved_quantity >= instance.quantity:
#             variant.reserved_quantity -= instance.quantity
#         else:
#             # fallback: reset to 0 if bad data
#             variant.reserved_quantity = 0

#         # Always return the quantity to stock
#         variant.stock_quantity += instance.quantity

#         variant.save()
#         update_quantity(variant.product)



@receiver(post_save, sender=OrderShipment)
def send_order_status_email(sender, instance, created, **kwargs):
    """
    Send email notification to customers based on
    Shipment status updates.
    """
    if created:
        return
    
    status = instance.status
    recipient = instance.order.user.email
    from_email = f"Horal Shipment <{settings.DEFAULT_FROM_EMAIL}>"
    # pickup_station = Station.objects.get(station_id=instance.buyer_station)

    # Email customers based on status
    # if status == OrderShipment.Status.PENDING_RECIPIENT_PICKUP:
    #     subject = "Your order is ready for pickup"
    #     message = [
    #         f"Your order #{instance.order.id} is now available for pickup at the designated location.",
    #         f"Our partner will reach out with pickup address." ,
    #         f"Please collect it as soon as possible.",
    #         "Thank you!"
    #     ]
    if status == OrderShipment.Status.DELIVERED:
        subject = "Your order has been delivered"
        message = [
            f"Your order #{instance.order.id} has been delivered to your address.",
            f"Please check your package and leave a review within 3 days.",
            f"If there are any issues, you may initiate a return request within this period.",
            "Thank you!"
        ]
    # elif status in DELAY_STATUSES:
    #     subject = "Delivery Delay Notification"
    #     message = [
    #         f"There has been a delay with your order #{instance.order.id}.",
    #         "We sincerely apologize for the inconvenience and appreciate your patience.",
    #         "Thank you!"
    #     ]
    # elif status in DELAY_STATUSES_CUSTOMER:
    #     subject = "Delivery Delay Notification"
    #     message = [
    #         f"Your order shipment #{instance.id} has arrived at the pickup station.",
    #         f"Kindly go to the address provided by our partner to pick up your order",
    #         "Thank you!"
    #     ]
    else:
        return


    send_email_task.delay(
        recipient=recipient,
        subject=subject,
        from_email=from_email,
        template_name="notifications/emails/general_email.html",
        context={
            "user": instance.order.user.full_name,
            "title": subject,
            "body_paragraphs": message
        }
    )
