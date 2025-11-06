import os, sys
import django

# Add the base directory to sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)

# Set the settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Horal_Backend.settings')

# Setup Django
django.setup()

import random
import uuid
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType

from users.models import CustomUser
from products.models import ProductVariant, ProductIndex
from carts.models import Cart, CartItem
from orders.models import Order, OrderItem, OrderShipment
from ratings.models import UserRating


shipment_status = [
    OrderShipment.Status.SHIPMENT_INITIATED,
    OrderShipment.Status.ACCEPTED_AT_INVENTORY_FACILITY,
    OrderShipment.Status.ACCEPTED_AT_LAST_MILE_HUB,
    OrderShipment.Status.ASSIGNED_TO_A_RIDER,
    OrderShipment.Status.DELIVERED,
    OrderShipment.Status.DISPATCHED,
    OrderShipment.Status.ENROUTE_TO_LAST_MILE_HUB,
    OrderShipment.Status.ENROUTE_TO_FIRST_MILE_HUB,
    OrderShipment.Status.FAILED_PICKUP,
    OrderShipment.Status.IN_RETURN_TO_CUSTOMER,
    OrderShipment.Status.IN_RETURN_TO_FIRST_MILE_HUB,
    OrderShipment.Status.IN_RETURN_TO_LAST_MILE_HUB,
    OrderShipment.Status.PENDING_PICKUP,
    OrderShipment.Status.PICKED_UP,
    OrderShipment.Status.REJECTED_AT_INVENTORY_FACILITY,
    OrderShipment.Status.REJECTED_AT_LAST_MILE_HUB,
    OrderShipment.Status.RETURNED,
    OrderShipment.Status.RETURNED_TO_FIRST_MILE_HUB,
    OrderShipment.Status.RETURNED_TO_LAST_MILE_HUB,
]

user = CustomUser.objects.get(email="user25@mail.com")
print(f"[INFO] Using user: {user.email}")

all_variants = ProductVariant.objects.all()
print(f"[INFO] Total available product variants: {all_variants.count()}")

def create_twelve_orders():
    # Create 12 orders (one per shipment status)
    for i in range(19):
        print(f"\n[STEP] Creating order {i+1}/19 with shipment status: {shipment_status[i]}")

        # Create cart
        cart = Cart.objects.create(user=user)
        print(f"   -> Cart created (ID: {cart.id})")

        # Create cart items
        items = random.sample(list(all_variants), k=3)
        for item in items:
            if not CartItem.objects.filter(cart=cart, variant=item).exists():
                CartItem.objects.create(cart=cart, variant=item, quantity=1)
        print(f"   -> Added {len(items)} items to cart.")

        # Calculate totals
        total = sum(
            item.price_override or getattr(item.product, 'price', 0)
            for item in items if item.product is not None
        )
        print(f"   -> Cart total calculated: {total}")

        # Create order
        order = Order.objects.create(
            user=user,
            product_total=total,
            total_amount=total + total,
            shipping_total=total,
            status=Order.Status.PAID,
            street_address="123 Test St",
            local_govt=user.location.local_govt,
            landmark="Near Market",
            state=user.location.state,
            country=user.location.country,
            phone_number=user.phone_number,
            created_at=timezone.now()
        )
        print(f"   -> Order created (ID: {order.id})")

        # Delete cart
        cart.delete()
        print("   -> Cart deleted after checkout.")

        # Create order items
        for item in items:
            delivered_at = None
            is_completed = False

            order_item = OrderItem.objects.create(
                order=order,
                variant=item,
                quantity=1,
                unit_price=item.price_override or item.product.price,
            )
            print(f"      -> OrderItem created for variant {item.id}")

            # Create shipment
            shipment = OrderShipment.objects.create(
                order=order,
                seller=item.shop.owner if item.shop else None,
                status=shipment_status[i],
                quantity=len(items),
                total_price=order.total_amount,
                shipping_cost=order.shipping_total,
                total_weight=0.5 * len(items),
                unique_id = f"HOR_{str(uuid.uuid4())[:10]}",
                batch_id = f"HBAT_{str(uuid.uuid4())[:10]}",
                waybill_number = f"HTRC_{str(uuid.uuid4())[:10]}",
            )
            print(f"      -> Shipment created (Tracking: {shipment.waybill_number}, Status: {shipment.status})")

            order_item.shipment = shipment
            order_item.save(update_fields=["shipment"])
            print(f"      -> OrderItem linked to shipment {shipment.waybill_number}")
            
            # Handle delivered shipments
            if shipment.status == OrderShipment.Status.DELIVERED:
                days_ago = random.choice([0, 1, 2, 3, 4, 5])
                delivered_at = timezone.now() - timezone.timedelta(days=days_ago)

                product = item.product
                if not product:
                    print("      [WARN] Skipped rating: product missing.")
                    continue

                content_type = ContentType.objects.get_for_model(product.__class__)
                product_index = ProductIndex.objects.filter(content_type=content_type, object_id=product.id).first()

                if not product_index:
                    print(f"      [WARN] Skipped rating: product index missing for product {product.id}.")
                    continue

                if UserRating.objects.filter(user=user, order_item=order_item, product=product_index).exists():
                    print(f"      [INFO] Skipped duplicate rating for order_item {order_item.id}")
                    continue

                UserRating.objects.create(
                    user=user,
                    order_item=order_item,
                    product=product_index,
                    rating=random.randint(3, 5),
                    comment="Great product!"
                )
                print(f"      -> Rating created for product {product.id}")

                shipment.delivered_at = delivered_at
                shipment.save(update_fields=["delivered_at"])
                print(f"      -> Shipment marked delivered on {delivered_at.date()}")

                order_item.is_completed = True
                order_item.delivered_at = delivered_at
                order_item.save(update_fields=["delivered_at", "is_completed"])
                print(f"      -> OrderItem marked completed with delivery date {delivered_at.date()}")

    print("\n[COMPLETE] Orders, OrderItems, Shipments, and Ratings created successfully.")


def create_three_orders():
    # Create 3 orders with pending, failed, and cancelled statuses
    statuses = [Order.Status.PENDING, Order.Status.FAILED, Order.Status.CANCELLED]
    for i in range(3):
        print(f"\n[STEP] Creating order {i+1}/3 with shipment status: {shipment_status[i]}")

        # Create cart
        cart = Cart.objects.create(user=user)
        print(f"   -> Cart created (ID: {cart.id})")

        # Create cart items
        items = random.sample(list(all_variants), k=3)
        for item in items:
            if not CartItem.objects.filter(cart=cart, variant=item).exists():
                CartItem.objects.create(cart=cart, variant=item, quantity=1)
        print(f"   -> Added {len(items)} items to cart.")

        # Calculate totals
        total = sum(
            item.price_override or getattr(item.product, 'price', 0)
            for item in items if item.product is not None
        )
        print(f"   -> Cart total calculated: {total}")

        # Create order
        order = Order.objects.create(
            user=user,
            product_total=total,
            total_amount=total + total,
            shipping_total=total,
            status=statuses[i],
            street_address="123 Test St",
            local_govt=user.location.local_govt,
            landmark="Near Market",
            state=user.location.state,
            country=user.location.country,
            phone_number=user.phone_number,
            created_at=timezone.now()
        )
        print(f"   -> Order created (ID: {order.id})")

        # Delete cart
        cart.delete()
        print("   -> Cart deleted after checkout.")

        # Create order items
        for item in items:
            OrderItem.objects.create(
                order=order,
                variant=item,
                quantity=1,
                unit_price=item.price_override or item.product.price,
            )
            print(f"      -> OrderItem created for variant {item.id}")

if __name__ == "__main__":
    create_twelve_orders()
    create_three_orders()
