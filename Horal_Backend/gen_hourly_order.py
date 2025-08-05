import os, django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Horal_Backend.settings")  # Replace this
django.setup()

import random
from django.utils.timezone import now
from users.models import CustomUser
from products.models import ProductVariant
from orders.models import Order, OrderItem


def generate_hourly_orders():
    print("Simulating hourly orders...")
    """
    Simulate hourly orders purchased by buyers from sellers.
    This function randomly selects sellers and buyers, creates orders,
    and saves them to the database.
    """
    # Fetch active sellers and buyers
    sellers = CustomUser.objects.filter(is_seller=True)
    buyers = CustomUser.objects.filter(is_seller=False)
    all_variants = ProductVariant.objects.select_related('content_type', 'shop')

    selected_sellers = random.sample(list(sellers), k=random.randint(1, 4))

    for seller in selected_sellers:
        seller_variants = all_variants.filter(shop__owner__user=seller)
        if not seller_variants.exists():
            continue
        print(f"Selected seller: {seller.email} with {seller_variants.count()} variants")

        buyer = random.choice(buyers)
        location = getattr(buyer, "location", None)
        if not location:
            continue

        selected_items = random.sample(list(seller_variants), k=min(3, seller_variants.count()))

        order = Order.objects.create(
            user=buyer,
            total_amount=0,
            status=random.choice([
                Order.Status.PAID, Order.Status.SHIPPED,
                Order.Status.DELIVERED
            ]),
            street_address="123 Test St",
            local_govt=location.local_govt,
            landmark="Near Market",
            state=location.state,
            country=location.country,
            phone_number=buyer.phone_number,
            created_at=now()  # Set the order creation time to now
        )

        total = 0
        for variant in selected_items:
            quantity = random.randint(1, 3)
            unit_price = variant.price_override or variant.product.price
            OrderItem.objects.create(
                order=order,
                variant=variant,
                quantity=quantity,
                unit_price=unit_price
            )
            total += unit_price * quantity

        order.total_amount = total
        order.save()
        print(f"✅ Order placed by {buyer.email} with {len(selected_items)} items. Total: ₦{total:.2f}")


if __name__ == "__main__":
    generate_hourly_orders()
    print("Hourly orders simulation completed.")