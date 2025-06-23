# your_app/management/commands/seed_db.py

from django.core.management.base import BaseCommand
import os, random, uuid
from datetime import timedelta
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType

from users.models import CustomUser, Location
from sellers.models import SellerKYC, SellerSocials
from shops.models import Shop
from categories.models import Category
from subcategories.models import SubCategory
from products.models import (
    ChildrenProduct, FashionProduct, GadgetProduct, ElectronicsProduct,
    VehicleProduct, AccessoryProduct, HealthAndBeautyProduct, FoodProduct,
    ProductVariant, ImageLink, Occasion, ProductIndex, Color
)
from carts.models import Cart, CartItem
from orders.models import Order, OrderItem
from ratings.models import UserRating
from favorites.models import Favorites, FavoriteItem

class Command(BaseCommand):
    help = 'Seed the database with sample users, products, categories, orders, etc.'

    def handle(self, *args, **kwargs):
        states_and_lgas = {
            "Lagos": ["Ikeja", "Surulere", "Yaba"],
            "Port Harcourt": ["Obio-Akpor", "Port Harcourt City", "Eleme"],
            "Abuja": ["Garki", "Wuse", "Maitama"],
            "Imo": ["Owerri", "Mbaitoli", "Orlu"],
            "Kaduna": ["Kaduna North", "Kaduna South", "Zaria"]
        }

        categories_data = {
            "fashion": [
                "clothing (men and women)", "shoes (men and women)", "bags", "jewelries",
                "watches", "eyewear", "underwear & sleepwear", "jerseys", "hats & caps", "swimwear"
            ],
            "health and beauty": ["skincare", "makeup", "hair care", "fragrances", "wellness & supplements", "oral hygiene"],
            "foods": ["fresh produce", "meat, poultry & seafood", "dairy & eggs", "beverages (non-alcoholic)", "baked goods", "frozen foods"],
            "vehicles": ["cars", "motorcycles", "buses & vans", "vehicle parts & accessories", "bicycles & scooters", "boats & watercraft", "trucks"],
            "gadget": ["smartphones", "tablets", "smartwatches & wearables", "drones", "cameras & photography gadgets", "portable audio", "gaming", "gps & navigation", "e-readers", "vr/ar devices"],
            "accessories": ["phone accessories", "laptop accessories", "camera accessories", "travel accessories", "wallets & cardholders", "umbrellas", "gloves", "belts"],
            "children": ["Baby clothing (0-24 months)", "diapers & wipes", "feeding & nursing", "gear & travel", "toys & gifts (0-3 years)", "children clothing", "maternity wear", "baby food", "safety & health"],
            "electronics": ["televisions & home theater", "audio & hi-fi systems", "computers & laptops", "printers & scanners", "networking devices", "home appliances", "gaming PCs & components", "generators"]
        }

        colors = [c[0] for c in Color.choices]

        # === Data Wipe ===
        CustomUser.objects.all().delete()
        Category.objects.all().delete()
        SubCategory.objects.all().delete()
        ImageLink.objects.all().delete()

        category_map = {}
        subcategory_map = {}

        for cat_name, subs in categories_data.items():
            category = Category.objects.create(name=cat_name)
            category_map[cat_name] = category
            for sub in subs:
                subcat = SubCategory.objects.create(category=category, name=sub, slug=sub.lower().replace(" ", "-"))
                subcategory_map[(cat_name, sub)] = subcat

        sellers = []
        buyers = []

        for i in range(30):
            user = CustomUser.objects.create_user(
                email=f"user{i}@mail.com",
                password="TestPass123!",
                full_name=f"User {i}",
                phone_number=f"080{i:08d}",
                is_active=True,
                is_seller=i < 10
            )
            state = random.choice(list(states_and_lgas.keys()))
            lga = random.choice(states_and_lgas[state])
            Location.objects.create(user=user, street_address="123 Test St", local_govt=lga, landmark="Near Market", state=state)
            if i < 10:
                kyc = SellerKYC.objects.create(user=user, nin="NIN.jpg", utility_bill="bill.jpg", is_verified=True)
                SellerSocials.objects.create(user=user, instagram="https://instagram.com/demo")
                shop = Shop.objects.create(owner=kyc, owner_type="seller", name=f"Shop {i}", location=f"{lga}, {state}")
                sellers.append((user, shop))
            else:
                buyers.append(user)

        image_urls = [f"https://img.com/{uuid.uuid4()}.jpg" for _ in range(1000)]
        image_index = 0

        def create_images(count):
            nonlocal image_index
            imgs = []
            for _ in range(count):
                url = image_urls[image_index]
                image_index += 1
                imgs.append(ImageLink.objects.create(url=url, alt_text="Seeded image"))
            return imgs

        def create_variants(product, count=2):
            variants = []
            for _ in range(count):
                variant = ProductVariant.objects.create(
                    content_type=ContentType.objects.get_for_model(product),
                    object_id=product.id,
                    standard_size=random.choice(["S", "M", "L"]),
                    color=random.choice(colors),
                    stock_quantity=random.randint(10, 50),
                    price_override=product.price + random.uniform(1.0, 10.0)
                )
                variants.append(variant)
            return variants

        product_index_list = []

        for user, shop in sellers:
            for cat_key in categories_data:
                cat = category_map[cat_key]
                subs = [subcategory_map[(cat_key, sub)] for sub in categories_data[cat_key]]
                for _ in range(2):
                    sub = random.choice(subs)
                    state, lga = random.choice(list(states_and_lgas.items()))
                    lga = random.choice(lga)
                    price = round(random.uniform(10, 200), 2)
                    title = f"{cat_key.title()} Product {uuid.uuid4().hex[:5]}"
                    desc = "Seeded description"
                    common_kwargs = dict(
                        title=title,
                        description=desc,
                        price=price,
                        quantity=20,
                        shop=shop,
                        category=cat,
                        sub_category=sub,
                        state=state,
                        local_govt=lga
                    )
                    model_class = {
                        "fashion": FashionProduct,
                        "vehicles": VehicleProduct,
                        "gadget": GadgetProduct,
                        "electronics": ElectronicsProduct,
                        "accessories": AccessoryProduct,
                        "children": ChildrenProduct,
                        "health and beauty": HealthAndBeautyProduct,
                        "foods": FoodProduct
                    }[cat_key]

                    p = model_class.objects.create(**common_kwargs)
                    imgs = create_images(3)
                    p.images.set(imgs)
                    p.save()
                    variants = create_variants(p, count=3)
                    content_type = ContentType.objects.get_for_model(p)
                    pi = ProductIndex.objects.get(object_id=p.id, content_type=content_type)
                    product_index_list.append(pi)

        print("✅ Sellers, products, and images created.")

        remaining_users = buyers
        all_variants = ProductVariant.objects.all()
        delivered_variants = []

        for buyer in remaining_users:
            cart = Cart.objects.create(user=buyer)
            for _ in range(random.randint(6, 7)):
                items = random.sample(list(all_variants), k=3)
                for item in items:
                    if not CartItem.objects.filter(cart=cart, variant=item).exists():
                        CartItem.objects.create(cart=cart, variant=item, quantity=1)

                total = sum(
                    item.price_override or item.product.price for item in items
                )
                status = random.choices([
                    Order.Status.DELIVERED, Order.Status.CANCELLED,
                    Order.Status.SHIPPED, Order.Status.PAID
                ], weights=[6, 1, 1, 1])[0]

                order = Order.objects.create(
                    user=buyer,
                    total_amount=total,
                    status=status
                )
                for item in items:
                    OrderItem.objects.create(
                        order=order,
                        variant=item,
                        quantity=1,
                        unit_price=item.price_override or item.product.price
                    )
                if status == Order.Status.DELIVERED:
                    delivered_variants.extend((buyer, item) for item in items)

        for (buyer, item) in random.sample(delivered_variants, min(120, len(delivered_variants))):
            product = item.product
            if not product:
                continue
            content_type = ContentType.objects.get_for_model(product.__class__)
            product_index = ProductIndex.objects.filter(content_type=content_type, object_id=product.id).first()
            if not product_index:
                continue
            UserRating.objects.create(
                user=buyer,
                order_item=OrderItem.objects.filter(variant=item, order__user=buyer).first(),
                product=product_index,
                rating=random.randint(3, 5),
                comment="Great product!"
            )

        for user in remaining_users:
            fav = Favorites.objects.create(user=user)
            fav_items = ProductIndex.objects.order_by('?')[:3]
            for p in fav_items:
                FavoriteItem.objects.create(favorites=fav, product_index=p)

        print("✅ Database seeding complete.")
