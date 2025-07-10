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
from datetime import datetime, timedelta
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType

# os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Horal_Backend.settings')
# django.setup()

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
from images import image_urls

# Sample data
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
    "health and beauty": [
        "skincare", "makeup", "hair care", "fragrances", "wellness & supplements", "oral hygiene"
    ],
    "foods": [
        "fresh produce", "meat, poultry & seafood", "dairy & eggs", "beverages (non-alcoholic)",
        "baked goods", "frozen foods"
    ],
    "vehicles": [
        "cars", "motorcycles", "buses & vans", "vehicle parts & accessories",
        "bicycles & scooters", "boats & watercraft", "trucks"
    ],
    "gadget": [
        "smartphones", "tablets", "smartwatches & wearables", "drones",
        "cameras & photography gadgets", "portable audio", "gaming",
        "gps & navigation", "e-readers", "vr/ar devices"
    ],
    "accessories": [
        "phone accessories", "laptop accessories", "camera accessories",
        "travel accessories", "wallets & cardholders", "umbrellas", "gloves", "belts"
    ],
    "children": [
        "Baby clothing (0-24 months)", "diapers & wipes", "feeding & nursing", "gear & travel",
        "toys & gifts (0-3 years)", "children clothing", "maternity wear", "baby food", "safety & health"
    ],
    "electronics": [
        "televisions & home theater", "audio & hi-fi systems", "computers & laptops",
        "printers & scanners", "networking devices", "home appliances",
        "gaming PCs & components", "generators"
    ]
}


colors = [c[0] for c in ImageLink._meta.get_field("url").choices or Color.choices]

# Clear data first (optional in dev)
CustomUser.objects.all().delete()
Category.objects.all().delete()
SubCategory.objects.all().delete()
ImageLink.objects.all().delete()

# Create categories and subcategories
category_map = {}
subcategory_map = {}

for cat_name, subs in categories_data.items():
    category = Category.objects.create(name=cat_name)
    category_map[cat_name] = category
    for sub in subs:
        subcat = SubCategory.objects.create(category=category, name=sub, slug=sub.lower().replace(" ", "-"))
        subcategory_map[(cat_name, sub)] = subcat

# Create 30 users (10 sellers, 20 buyers)
sellers = []
buyers = []

admin = CustomUser.objects.create_superuser(
        email=f"adminuser@mail.com",
        password="TestPass123!",
        full_name=f"Admin User",
        phone_number=f"08033556677",
        is_active=True
    )

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
        kyc = SellerKYC.objects.create(user=user, nin=f"https://example.com/nin-{i}.jpg", utility_bill=f"https://example.com/bill-{i}.jpg", is_verified=True)
        SellerSocials.objects.create(user=user, instagram="https://instagram.com/demo")
        shop = Shop.objects.create(owner=kyc, owner_type="seller", name=f"Shop {i}", location=f"{lga}, {state}")
        sellers.append((user, shop))
    else:
        buyers.append(user)

def create_images(count):
    global image_index
    imgs = []
    for _ in range(count):
        url = random.choice(image_urls)
        imgs.append(ImageLink.objects.create(url=url, alt_text="Seeded image"))
    return imgs

def create_variants(product, count=2):
    variants = []
    for _ in range(count):
        variant = ProductVariant.objects.create(
            content_type=ContentType.objects.get_for_model(product),
            object_id=product.id,
            standard_size=random.choice(["S", "M", "L"]),
            color=random.choice([c[0] for c in Color.choices]),
            stock_quantity=random.randint(10, 50),
            price_override=product.price + random.uniform(1.0, 10.0)
        )
        variants.append(variant)
    return variants

# Create products for each seller (16 total = 2 per category)
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
                is_published=1,
                category=cat,
                sub_category=sub,
                state=state,
                local_govt=lga
            )

            if cat_key == "fashion":
                p = FashionProduct.objects.create(**common_kwargs)
                p.material = "Cotton"
                p.style = "Casual"
                p.sleeve_length = "short"
                p.neckline = "round"
                p.save()
            elif cat_key == "vehicles":
                p = VehicleProduct.objects.create(
                    **common_kwargs,
                    make="Toyota", model="Camry", year=2021, mileage=15000,
                    engine_type="petrol", engine_size="medium", fule_type="petrol",
                    transmission="automatic", num_doors=4, num_seats=5,
                    vin=str(uuid.uuid4())[:17], color_exterior="black", color_interior="gray",
                    seating_capacity=5
                )
            elif cat_key == "gadget":
                p = GadgetProduct.objects.create(
                    **common_kwargs,
                    model="XPhone 12", processor="A14", ram="6GB", storage="128GB",
                    screen_size="6.1", operating_system="android", connectivity="WiFi/Bluetooth"
                )
            elif cat_key == "electronics":
                p = ElectronicsProduct.objects.create(
                    **common_kwargs,
                    model="ElecX", power_output="medium", features="Smart TV",
                    connectivity="WiFi", voltage="220V", power_source="electric"
                )
            elif cat_key == "accessories":
                p = AccessoryProduct.objects.create(
                    **common_kwargs,
                    material="Leather", compatibility="Universal", dimensions="10x5", type="case"
                )
            elif cat_key == "children":
                p = ChildrenProduct.objects.create(
                    **common_kwargs,
                    material="Plastic", weight_capacity="20kg", safety_certifications="CE"
                )
            elif cat_key == "health and beauty":
                p = HealthAndBeautyProduct.objects.create(
                    **common_kwargs,
                    ingredients="Aloe Vera", skin_type="dry", fragrance="Lavender",
                    usage_instructions="Apply daily", spf="15", shade="Natural",
                    volume="200ml", benefits="Moisturizes skin"
                )
            elif cat_key == "foods":
                p = FoodProduct.objects.create(
                    **common_kwargs,
                    ingredients="Organic Fruits", dietary_info="Vegan",
                    origin="Local Farm", weight="2kg", condition="fresh",
                    shelf_life="7 days", size="Medium"
                )
            imgs = create_images(3)
            p.images.set(imgs)
            p.save()
            variants = create_variants(p, count=3)
            content_type = ContentType.objects.get_for_model(p)
            pi = ProductIndex.objects.get(object_id=p.id, content_type=content_type)
            product_index_list.append(pi)

print("✅ User, Seller, Shop, Category, Subcategory, Product, Image, Variant, and ProductIndex created successfully.")

# === REMAINING USERS ORDERING ===
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
            item.price_override or getattr(item.product, 'price', 0)
            for item in items
            if item.product is not None
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
    cart.delete()


# === RATINGS ===
for (buyer, item) in random.sample(delivered_variants, min(120, len(delivered_variants))):
    product = item.product
    if not product:
        continue

    content_type = ContentType.objects.get_for_model(product.__class__)
    product_index = ProductIndex.objects.filter(content_type=content_type, object_id=product.id).first()

    if not product_index:
        continue

    order_item = OrderItem.objects.filter(variant=item, order__user=buyer).first()
    if not order_item:
        continue

    # ✅ Skip if this user already rated this order_item for this product
    if UserRating.objects.filter(user=buyer, order_item=order_item, product=product_index).exists():
        continue

    UserRating.objects.create(
        user=buyer,
        order_item=OrderItem.objects.filter(variant=item, order__user=buyer).first(),
        product=product_index,
        rating=random.randint(3, 5),
        comment="Great product!"
    )


# === FAVORITES ===
for user in remaining_users:
    fav = Favorites.objects.create(user=user)
    fav_items = ProductIndex.objects.order_by('?')[:3]
    for p in fav_items:
        FavoriteItem.objects.create(favorites=fav, product_index=p)

print("Database seeding complete.")
