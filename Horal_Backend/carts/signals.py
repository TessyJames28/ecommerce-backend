from django.dispatch import Signal, receiver
from notifications.tasks import send_email_task
from products.models import ProductIndex
from django.conf import settings

cart_abandoned = Signal()

@receiver(cart_abandoned)
def handle_cart_abandonment(sender, cart, **kwargs):
    """Signal to notify users of abandoned carts"""
    if not cart.user:
        return
    
    print(f"Cart: {cart}")

    # Get all items in the cart
    items = cart.cart_item.all()
    if not items.exists():
        print(f"Cart {cart.id} is empty, skipping abandoned cart email.")
        return  # Exit early if there are no items

    item_list = []
    for item in items:
        print("Looping over cart.item")
        product = ProductIndex.objects.get(id=item.variant.object_id)
        name = product.title
        quantity = item.quantity
        price = item.item_total_price
        item_list.append(f"{name} x {quantity}  (₦{price})")
        print(f"Item list: {item_list}")
    
    item_lines = "\n".join(item_list)
    print(f"Items from shipments: {item_lines}")
    
    receipt_box = (
        f"+{'-'*40}+\n"
        f"|{'HORAL CART'.center(40)}|\n"
        f"+{'-'*40}+\n"
        f"| Cart ID: {str(cart.id).ljust(28)}|\n"
        f"|{'-'*40}|\n"
        f"{item_lines}\n"
        f"|{'-'*40}|\n"
        f"| Total Items: {str(cart.total_item).ljust(22)}|\n"
        f"| Total Price: ₦{str(cart.total_price).ljust(27)}|\n"
        f"+{'-'*40}+"
    )

    subject = "Hello Friend, You left something in your cart!"
    greeting = f"Hello {cart.user.full_name},\n\nYou left items in your cart!"

    body = (
        f"{greeting}\n\n"
        f"Here are a summary of the items in your cart:\n\n"
        f"{receipt_box}\n\n"
        f"Thank you for your interest in shopping with Horal!"
    )

    recipient = cart.user.email
    from_email = f"Horal Cart <{settings.DEFAULT_FROM_EMAIL}>"
    
    send_email_task.delay(recipient, subject, body, from_email)
    print("Email sent to user")


