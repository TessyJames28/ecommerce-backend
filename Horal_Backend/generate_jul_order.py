import os
import django
import random
from datetime import datetime, timedelta, date
from django.utils import timezone
from django.db import connection

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Horal_Backend.settings")  # Replace this
django.setup()

from products.models import ProductVariant
from orders.models import Order, OrderItem, OrderReturnRequest
from users.models import CustomUser, Location

# Helper to return random datetime within a given day
def random_time_on_day(day: date):
    naive = datetime.combine(day, datetime.min.time()) + timedelta(
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
        seconds=random.randint(0, 59)
    )
    return timezone.make_aware(naive)


def create_july_orders():
    sellers = list(CustomUser.objects.filter(is_seller=True, is_active=True))
    buyers = list(CustomUser.objects.filter(is_seller=False, is_active=True))
    all_variants = ProductVariant.objects.select_related('content_type', 'shop').all()

    start_date = date(2025, 6, 1)
    end_date = date(2025, 8, 22)

    for single_date in (start_date + timedelta(days=n) for n in range((end_date - start_date).days + 1)):
        print(f"📅 Creating orders for {single_date.strftime('%Y-%m-%d')}...")
        orders_today = random.randint(20, 30)

        for _ in range(orders_today):
            buyer = random.choice(buyers)
            seller = random.choice(sellers)
            location = getattr(buyer, "location", None)
            if not location:
                continue

            seller_variants = all_variants.filter(shop__owner__user=seller)
            if not seller_variants.exists():
                continue

            selected_variants = random.sample(list(seller_variants), k=min(3, seller_variants.count()))
            order_time = random_time_on_day(single_date)

            status = random.choice([
                Order.Status.PAID, Order.Status.SHIPPED, Order.Status.AT_PICK_UP,
                Order.Status.DELIVERED, Order.Status.CANCELLED
            ])

            order = Order.objects.create(
                user=buyer,
                total_amount=0,
                status=status,
                street_address="123 Test St",
                local_govt=location.local_govt,
                landmark="Near Market",
                state=location.state,
                country=location.country,
                phone_number=buyer.phone_number,
                created_at=order_time,
            )

            total = 0
            for variant in selected_variants:
                qty = random.randint(1, 3)
                unit_price = variant.price_override or variant.product.price

                delivered_at = None
                is_completed = False

                if status == Order.Status.DELIVERED:
                    # Set delivery date same day as order or a few days later
                    days_after_order = random.randint(0, 5)
                    delivered_at = order_time + timedelta(days=days_after_order)

                    # Mark as completed if > 3 days since delivery or simulate review
                    if (timezone.now() - delivered_at).days > 3 or random.choice([True, False]):
                        is_completed = True

                order_item = OrderItem.objects.create(
                    order=order,
                    variant=variant,
                    quantity=qty,
                    unit_price=unit_price,
                    delivered_at=delivered_at,
                    is_completed=is_completed
                )

                total += qty * unit_price

                # Randomly simulate return requests for some delivered items (small %)
                if status == Order.Status.DELIVERED and random.random() < 0.1:  # 10% chance
                    return_status = random.choice([
                        OrderReturnRequest.Status.REQUESTED,
                        OrderReturnRequest.Status.REJECTED,
                        OrderReturnRequest.Status.COMPLETED
                    ])
                    OrderReturnRequest.objects.create(
                        order_item=order_item,
                        reason="Item defective or not as described",
                        status=return_status,
                        approved=(return_status == OrderReturnRequest.Status.COMPLETED)
                    )
                    # Ensure returned/requested items are not marked completed
                    order_item.is_completed = False
                    order_item.save(update_fields=["is_completed"])

            order.total_amount = total
            order.save()

        print(f"✅ {orders_today} orders created for {single_date.strftime('%Y-%m-%d')}.")


if __name__ == "__main__":
    create_july_orders()
