import os
import django
import random
from datetime import datetime, timedelta, date
from django.utils import timezone
from django.db import connection

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Horal_Backend.settings")  # Replace this
django.setup()

from products.models import ProductVariant
from orders.models import Order, OrderItem
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
    end_date = date(2025, 8, 5)

    for single_date in (start_date + timedelta(days=n) for n in range((end_date - start_date).days + 1)):
        # if single_date.day == 28:
        #     continue  # Skip July 28

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

            order = Order.objects.create(
                user=buyer,
                total_amount=0,
                status=random.choice([
                    Order.Status.PAID, Order.Status.SHIPPED,
                    Order.Status.DELIVERED, Order.Status.CANCELLED
                ]),
                street_address="123 Test St",
                local_govt=location.local_govt,
                landmark="Near Market",
                state=location.state,
                country=location.country,
                phone_number=buyer.phone_number,
                created_at=order_time,  # This will now work
            )




            total = 0
            for variant in selected_variants:
                qty = random.randint(1, 3)
                unit_price = variant.price_override or variant.product.price
                OrderItem.objects.create(
                    order=order,
                    variant=variant,
                    quantity=qty,
                    unit_price=unit_price,
                )
                total += qty * unit_price

            order.total_amount = total
            order.save()

        print(f"✅ {orders_today} orders created for {single_date.strftime('%Y-%m-%d')}.")

if __name__ == "__main__":
    create_july_orders()
