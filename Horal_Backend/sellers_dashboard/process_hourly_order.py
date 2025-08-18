import random
from datetime import timedelta
from django.utils.timezone import now
from orders.models import Order, OrderItem  # Adjust imports to match your app

def process_hourly_orders():
    print("Processing hourly orders...")

    current_time = now()

    # Step 1: Update Paid → Shipped (within 24h)
    paid_orders = Order.objects.filter(status=Order.Status.PAID)
    for order in paid_orders:
        if current_time - order.created_at >= timedelta(hours=24):
            order.status = Order.Status.SHIPPED
            order.updated_at = current_time
            order.save()
            print(f"🚚 Order {order.id} marked as SHIPPED.")

    # Step 2: Update Shipped → At_pick_up (3 days later)
    shipped_orders = Order.objects.filter(status=Order.Status.SHIPPED)
    for order in shipped_orders:
        if current_time - order.updated_at >= timedelta(days=3):
            order.status = Order.Status.AT_PICK_UP
            order.updated_at = current_time
            order.save()
            print(f"📦 Order {order.id} marked as AT_PICK_UP.")

    # Step 3: Update At_pick_up → Delivered (3 days later)
    at_pickup_orders = Order.objects.filter(status=Order.Status.AT_PICK_UP)
    for order in at_pickup_orders:
        if current_time - order.updated_at >= timedelta(days=3):
            order.status = Order.Status.DELIVERED
            order.updated_at = current_time
            order.save()

            # Mark delivered_at for its items
            OrderItem.objects.filter(order=order).update(delivered_at=current_time)
            print(f"✅ Order {order.id} marked as DELIVERED with delivered_at set.")

    # Step 4: Randomly mark some delivered orders for return_requested (within 2 days)
    delivered_orders = OrderItem.objects.filter(order__status=Order.Status.DELIVERED)
    for order in delivered_orders:
        if random.random() < 0.1:  # 10% chance to request return
            if current_time - order.delivered_at <= timedelta(days=2):
                order.is_return_requested = True
                order.save()
                print(f"🔄 Order item {order.id} return requested.")

    # Step 5: Handle return requests → Returned / Rejected (within 2 days)
    return_requested_orders = OrderItem.objects.filter(is_return_requested=True)
    for order in return_requested_orders:
        if current_time - order.delivered_at >= timedelta(days=4):
            if random.choice([True, False]):
                order.is_returned = True
                order.is_return_requested = True
                print(f"♻ Order Item {order.id} marked as RETURNED.")
            else:
                order.is_return_requested = False
                print(f"❌ Order Item {order.id} return request REJECTED.")
            order.save()

    print("Processing complete.")

if __name__ == "__main__":
    process_hourly_orders()
