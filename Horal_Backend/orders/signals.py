from django.dispatch import receiver
from django.db.models.signals import post_save, post_delete
from .models import (
    Order, OrderItem, OrderShipment,
    DELAY_STATUSES, OrderReturnRequest,
    DELAY_STATUSES_CUSTOMER,
    DELIVERED_STATUSES, PICKUP_STATUSES
)
from support.utils import (
    create_message_for_instance,
    generate_received_subject
)
from logistics.models import Station
from collections import defaultdict
from .utils import update_quantity
from products.models import ProductIndex
from notifications.tasks import send_email_task
from django.conf import settings
from django.utils.timezone import now
from users.models import CustomUser
from logistics.utils import group_order_items_by_seller
from sellers.models import SellerKYC, SellerKYCAddress
from shops.models import Shop
from .tasks import create_gigl_shipment_on_each_shipment
from logistics.utils import calculate_shipping_for_order, get_experience_centers


@receiver(post_save, sender=OrderReturnRequest)
def send_return_received_email(sender, instance, created, **kwargs):
    """
    Signal to send automated message once a return request is made
    """
    from support.models import Message

    if created:
        subject = generate_received_subject(instance)
        body = f"Hello {instance.order_item.order.user.full_name},\n\n" \
               f"We have received your return request for item {instance.order_item.id}:\n\n" \
               f"{instance.reason}\n\n" \
               "Our team will review it and get back to you shortly." \
               "\n\nNote: All further correspondence will be via this email"

        # Get user email
        returns = OrderReturnRequest.objects.get(
            id=instance.id,
            order_item=instance.order_item
        )

        user = returns.order_item.order.user
        print(f"User: {user}")

        from_email = f"returns@{settings.MAILGUN_DOMAIN}"
        # Trigger async email
        send_email_task.delay(
            recipient=instance.order_item.order.user.email,
            subject=subject,
            body=body,
            from_email=f"Returns <{from_email}>"
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
def create_gigl_shipment_on_paid(sender, instance: Order, created, **kwargs):
    """
    Auto-create GIGL shipments when an order is marked as PAID for the first time,
    and send a customized receipt email. If this is the user's first order, 
    add a special message.
    """
    print("Shipment creation signal called")

    # Don't trigger on creation only update
    if created or instance.status != Order.Status.PAID:
        return
    
    # Check if status just changed to PAID
    # previous = Order.objects.get(pk=instance.pk)
    # if previous.status == Order.Status.PAID:
    #     return  # Already marked as paid before, skip
    print("About to create shipment")
    create_gigl_shipment_on_each_shipment.delay(str(instance.id))
    print("Shipment created")

    print("Preping customer email")
    # Prepare a receipt-like order summary
    item_list = []
    for shipment_data in instance.shipments.all():
        for item in shipment_data.items.all(): 
            product = ProductIndex.objects.get(id=item.variant.object_id)
            name = product.title
            quantity = item.quantity
            price = item.total_price
            item_list.append(f"{name} x {quantity}  (₦{price})")
            print(f"Item list: {item_list}")
    item_lines = "\n".join(item_list)
    print(f"Items from shipments: {item_lines}")
    receipt_box = (
        f"+{'-'*40}+\n"
        f"|{'HORAL ORDER RECEIPT'.center(40)}|\n"
        f"+{'-'*40}+\n"
        f"| Order ID: {str(instance.id).ljust(28)}|\n"
        f"|{'-'*40}|\n"
        f"{item_lines}\n"
        f"|{'-'*40}|\n"
        f"| Product Total: {str(instance.product_total).ljust(22)}|\n"
        f"| Shipping: {str(instance.shipping_total).ljust(27)}|\n"
        f"| Grand Total: {str(instance.total_amount).ljust(25)}|\n"
        f"+{'-'*40}+"
    )

    # Check if this is the user's first successful payment
    first_paid_order = not Order.objects.filter(
        user=instance.user,
        status=Order.Status.PAID
    ).exclude(id=instance.id).exists()
    print("Prepping email sending")
    # Customize subject and greeting if first paid order
    if first_paid_order:
        subject = "🎉 Congratulations on Your First Order!"
        greeting = f"Hello {instance.user.full_name},\n\nThank you for placing your first order with Horal! 🎉"
    else:
        subject = "Your Horal Order Receipt"
        greeting = f"Hello {instance.user.full_name},\n\nThank you for your purchase!"

    body = (
        f"{greeting}\n\n"
        f"Here is your receipt:\n\n"
        f"{receipt_box}\n\n"
        f"Thank you for shopping with Horal!"
    )

    recipient = instance.user.email
    from_email = f"Horal Order <{settings.DEFAULT_FROM_EMAIL}>"
    
    send_email_task.delay(recipient, subject, body, from_email)
    print("Email sent for buyer")

    
    # ======== Email each seller once with all their items ========
    print("In seller data section")

    # Group seller data
    sellers_data = defaultdict(lambda: {
        "email": "",
        "name": "",
        "items": [],
        "addresses": ""
    })

    # Build seller data per shipment
    for shipment in instance.shipments.all():
        seller = shipment.seller
        seller_id = seller.user.id
        
        if seller_id not in sellers_data:
            sellers_data[seller_id]["email"] = seller.user.email
            sellers_data[seller_id]["name"] = seller.user.full_name
        
            # Get seller state and addresses dynamically per seller
            seller_state = seller.address.state
            addresses = get_experience_centers(seller_state)
            sellers_data[seller_id]["addresses"] = addresses

        # Add shipment items
        for item in shipment.items.all():
            product = ProductIndex.objects.get(id=item.variant.object_id)
            sellers_data[seller_id]["items"].append(
                f"{product.title:<25} x{item.quantity:<3} ₦{item.total_price}"
            )

    print("About to send email to each seller")
    print(f"Sellers data: {sellers_data}")

    # Send emails to each seller
    for seller_id, data in sellers_data.items():
        items_str = "\n".join(data["items"])
        seller_subject = f"New order from {instance.user.full_name}"
        
        seller_body = (
            f"Hello {data['name']},\n\n"
            f"You have a new order from {instance.user.full_name}.\n\n"
            f"Order ID: {instance.id}\n"
            f"Items:\n{items_str}\n\n"
            f"Please get these items ready for shipment and drop them at any of the below location(s):\n"
            f"\t{data['addresses']}."
        )


        send_email_task.delay(data["email"], seller_subject, seller_body, from_email)
        print("Email sent to seller")

@receiver(post_delete, sender=OrderItem)
def restore_reserved_stock(sender, instance, **kwargs):
    """
    Restore reserved stock when an OrderItem is deleted
    """
    variant = instance.variant
    if variant:
        # Reduce reserved stock
        variant.reserved_quantity -= instance.quantity
        variant.stock_quantity += instance.quantity  # Deduct immediately upon reservation
        variant.save()
        update_quantity(variant.product)


@receiver(post_save, sender=OrderShipment)
def send_order_status_email(sender, instance, created, **kwargs):
    """
    Send email notification to customers based on
    Shipment status updates.
    """
    print("Signal for shipment status update called")
    if created:
        return
    
    status = instance.status
    print(f"Instance status: {status}")
    recipient = instance.order.user.email
    print(f"Recipient email: {recipient}")
    from_email = f"Horal Shipment <{settings.DEFAULT_FROM_EMAIL}>"
    # pickup_station = Station.objects.get(station_id=instance.buyer_station)

    # Email customers based on status
    if status in PICKUP_STATUSES:
        subject = "Your order is ready for pickup"
        message = f"Dear {instance.order.user.full_name},\n\n" \
                  f"Your order {instance.order.id} is now available for pickup at the designated location. " \
                  f"Our partner will reach out with pickup address.\n\n" \
                  f"Please collect it as soon as possible.\n\nThank you!"
    elif status in DELIVERED_STATUSES:
        subject = "Your order has been delivered"
        message = f"Dear {instance.order.user.full_name},\n\n" \
                  f"Your order {instance.order.id} has been delivered to your address. " \
                  f"Please check your package and leave a review within 3 days. " \
                  f"If there are any issues, you may initiate a return request within this period.\n\nThank you!"
    elif status in DELAY_STATUSES:
        subject = "Delivery Delay Notification"
        message = f"Dear {instance.order.user.full_name},\n\n" \
                  f"There has been a delay with your order {instance.order.id}. " \
                  f"We apologize for the inconvenience and appreciate your patience.\n\nThank you!"
    elif status in DELAY_STATUSES_CUSTOMER:
        subject = "Delivery Delay Notification"
        message = f"Dear {instance.order.user.full_name},\n\n" \
                  f"Your order shipment {instance.id} has arrived at the pickup station. " \
                  f"Kindly go to the address provided by our partner to pick up your order\n\nThank you!"
    else:
        return

    send_email_task.delay(recipient, subject, message, from_email)

