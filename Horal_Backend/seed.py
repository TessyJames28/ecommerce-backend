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
from datetime import date, timedelta
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType

# os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Horal_Backend.settings')
# django.setup()

from users.models import CustomUser, Location
from sellers.models import SellerKYC, SellerSocials, SellerKYCAddress, SellerKYCCAC, SellerKYCNIN
from shops.models import Shop
from categories.models import Category
from subcategories.models import SubCategory
from products.models import (
    ChildrenProduct, FashionProduct, GadgetProduct, ElectronicsProduct,
    VehicleProduct, AccessoryProduct, HealthAndBeautyProduct, FoodProduct,
    ProductVariant, ProductIndex, Color,
    VehicleImage, FashionImage, ElectronicsImage, FoodImage,
    HealthAndBeautyImage, AccessoryImage, ChildrenImage, GadgetImage
)
from logistics.models import Logistics
from django.conf import settings

from products.utils import image_model_map
from carts.models import Cart, CartItem
from orders.models import Order, OrderItem, OrderReturnRequest
from ratings.models import UserRating
from favorites.models import Favorites, FavoriteItem
from images import image_urls
from sellers_dashboard.models import (
    RawSale, WeeklySales, WeeklyShopSales, MonthlySales,
    SalesAdjustment, DailyShopSales, DailySales, MonthlyShopSales,
    YearlySales, YearlyShopSales
)
from wallet.models import SellersBankDetails, SellerTransactionHistory, Payout
from support.models import SupportTeam


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


colors = [c[0] for c in Color.choices]


# Clear data first (optional in dev)
SupportTeam.objects.all().delete()
CustomUser.objects.all().delete()
Category.objects.all().delete()
SubCategory.objects.all().delete()
RawSale.objects.all().delete()
SalesAdjustment.objects.all().delete()
DailySales.objects.all().delete()
DailyShopSales.objects.all().delete()
WeeklySales.objects.all().delete()
WeeklyShopSales.objects.all().delete()
MonthlySales.objects.all().delete()
MonthlyShopSales.objects.all().delete()
YearlySales.objects.all().delete()
YearlyShopSales.objects.all().delete()
SellersBankDetails.objects.all().delete()
SellerTransactionHistory.objects.all().delete()
Payout.objects.all().delete()

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

for i in range(5):
    staff = CustomUser.objects.create_user(
        email=f"staff{i}@mail.com",
        password="TestPass123!",
        full_name=f"Staff {i}",
        phone_number=f"070{i:08d}",
        is_active=True,
        is_staff=True,
    )

# Create bot staff
support = CustomUser.objects.create_user(
    email=settings.SUPPORT_EMAIL,
    password=settings.SUPPORT_PASSWORD,
    full_name="support-bot",
    is_staff=True,
    is_active=True
)

returns = CustomUser.objects.create_user(
    email=settings.RETURNS_EMAIL,
    password=settings.RETURNS_PASSWORD,
    full_name="returns-bot",
    is_staff=True,
    is_active=True
)
print(f"Support and returns bot create:\n\tSupport: {support}\n\tReturns: {returns}")

# Create Support Team
s_team = SupportTeam.objects.create(
    team=support,
    name=support.full_name,
    email=support.email
)

r_team = SupportTeam.objects.create(
    team=returns,
    name=returns.full_name,
    email=returns.email
)

print(f"Support and returns team member created:\n\tSupport: {s_team}\n\tReturns: {r_team}")

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
    
    used_nins = set()
    used_rc_numbers = set()
    used_mobiles = set()
    used_social_links = set()

    if i < 10:
        # Unique safe dummy values
        nin_val = f"{10000000000 + i}"
        rc_number_val = f"RC{100000 + i}"
        mobile_val = f"081{1000000 + i}"
        fb_link = f"https://facebook.com/seller{i}"
        ig_link = f"https://instagram.com/seller{i}"

        # Ensure uniqueness across runs
        if nin_val in used_nins or rc_number_val in used_rc_numbers or mobile_val in used_mobiles:
            continue

        used_nins.add(nin_val)
        used_rc_numbers.add(rc_number_val)
        used_mobiles.add(mobile_val)
        used_social_links.update([fb_link, ig_link])

        # Create KYC submodels
        nin_obj = SellerKYCNIN.objects.create(
            nin=nin_val,
            selfie=f"https://example.com/selfie-{i}.jpg",
            status="verified",
            nin_verified=True
        )

        cac_obj = SellerKYCCAC.objects.create(
            rc_number=rc_number_val,
            company_type="Limited Liability",
            company_name=f"Demo Company {i}",
            status="verified",
            cac_verified=True
        )

        address_obj = SellerKYCAddress.objects.create(
            first_name=f"User{i}",
            last_name="Seller",
            middle_name="A.",
            dob=date.today() - timedelta(days=30 * 365),
            gender="male" if i % 2 == 0 else "female",
            mobile=mobile_val,
            street="123 Market Rd",
            landmark="Beside Mall",
            lga=lga,
            state=state,
            business_name=f"Biz {i}"
        )

        socials_obj = SellerSocials.objects.create(
            facebook=fb_link,
            instagram=ig_link
        )

        kyc = SellerKYC.objects.create(
            user=user,
            nin=nin_obj,
            cac=cac_obj,
            address=address_obj,
            socials=socials_obj,
            is_verified=True,
            status="verified"
        )

        shop = Shop.objects.create(
            owner=kyc,
            owner_type="seller",
            name=f"Shop {i}"
        )

        sellers.append((user, shop))
    else:
        buyers.append(user)


def create_images(product, count=3):
    """Create images dynamically for the correct product image model."""
    model_name = product.__class__.__name__
    image_model_class = image_model_map.get(model_name)

    if not image_model_class:
        return []

    imgs = []
    for _ in range(count):
        url = random.choice(image_urls)
        img = image_model_class.objects.create(
            product=product,
            url=url,
            alt_text="Seeded image"
        )
        imgs.append(img)
    return imgs


def create_variants(product, count=2):
    """Create variants tied to a product via ContentType."""
    variants = []
    for _ in range(count):
        variant = ProductVariant.objects.create(
            content_type=ContentType.objects.get_for_model(product),
            object_id=product.id,
            standard_size=random.choice(["S", "M", "L"]),
            custom_size_unit=random.choice(["KG", "G", "L", "ML", "M"]),
            custom_size_value=random.randint(1, 5),
            color=random.choice([c[0] for c in Color.choices]),
            stock_quantity=random.randint(10, 50),
            price_override=product.price + random.uniform(1.0, 10.0),
            shop=product.shop
        )
        variants.append(variant)
    return variants


def create_logistics(product):
    """Create variants tied to a product via ContentType."""
    
    logistics = Logistics.objects.create(
        content_type=ContentType.objects.get_for_model(product),
        object_id=product.id,
        weight_measurement=random.choice(["KG", "G", "L", "ML", "M"]),
        total_weight=random.randint(1, 5),
    )
    return logistics

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
                p = FashionProduct.objects.create(**common_kwargs,
                                                  material="Cotton", style="Casual",
                                                  sleeve_length="short", neckline="round")
            elif cat_key == "vehicles":
                p = VehicleProduct.objects.create(**common_kwargs,
                                                  make="Toyota", model="Camry", year=2021,
                                                  mileage=15000, engine_type="petrol",
                                                  engine_size="medium", fuel_type="petrol",
                                                  transmission="automatic", num_doors=4,
                                                  num_seats=5, vin=str(uuid.uuid4())[:17],
                                                  color_exterior="black", color_interior="gray",
                                                  seating_capacity=5)
            elif cat_key == "gadget":
                p = GadgetProduct.objects.create(**common_kwargs,
                                                 model="XPhone 12", processor="A14",
                                                 ram="6GB", storage="128GB",
                                                 screen_size="6.1", operating_system="android",
                                                 connectivity="WiFi/Bluetooth")
            elif cat_key == "electronics":
                p = ElectronicsProduct.objects.create(**common_kwargs,
                                                      model="ElecX", power_output="medium",
                                                      features="Smart TV", connectivity="WiFi",
                                                      voltage="220V", power_source="electric")
            elif cat_key == "accessories":
                p = AccessoryProduct.objects.create(**common_kwargs,
                                                    material="Leather",
                                                    compatibility="Universal",
                                                    dimensions="10x5", type="case")
            elif cat_key == "children":
                p = ChildrenProduct.objects.create(**common_kwargs,
                                                   material="Plastic", weight_capacity="20kg",
                                                   safety_certifications="CE")
            elif cat_key == "health and beauty":
                p = HealthAndBeautyProduct.objects.create(**common_kwargs,
                                                          ingredients="Aloe Vera",
                                                          skin_type="dry",
                                                          fragrance="Lavender",
                                                          usage_instructions="Apply daily",
                                                          spf="15", shade="Natural",
                                                          volume="200ml",
                                                          benefits="Moisturizes skin")
            elif cat_key == "foods":
                p = FoodProduct.objects.create(**common_kwargs,
                                               ingredients="Organic Fruits",
                                               dietary_info="Vegan",
                                               origin="Local Farm", weight="2kg",
                                               condition="fresh", shelf_life="7 days",
                                               size="Medium")

            # ✅ attach images via new model
            create_images(p, count=3)

            # ✅ attach variants
            create_logistics(p)

            # ✅ attach variants
            create_variants(p, count=3)

            # Add to ProductIndex
            content_type = ContentType.objects.get_for_model(p)
            pi = ProductIndex.objects.get(object_id=p.id, content_type=content_type)
            product_index_list.append(pi)

print("✅ Seeded users, shops, categories, subcategories, products, images, variants, and product index successfully.")

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

        status = random.choices(
            [Order.Status.CANCELLED, Order.Status.PAID],
            weights=[1, 6]
        )[0]

        order = Order.objects.create(
            user=buyer,
            product_total=total,
            total_amount=total + total,
            shipping_total=total,
            status=status,
            street_address="123 Test St",
            local_govt=random.choice(states_and_lgas[buyer.location.state]),
            landmark="Near Market",
            state=buyer.location.state,
            country=buyer.location.country,
            phone_number=buyer.phone_number,
            created_at=timezone.now()
        )

        # order_item_status = random.choices(
        #     [
        #         OrderItem.Status.SHIPMENT_INITIATED,
        #         OrderItem.Status.SHIPMENT_CREATED,
        #         OrderItem.Status.SHIPMENT_CREATED_BY_CUSTOMER,
        #         OrderItem.Status.AVAILABLE_FOR_PICKUP,
        #         OrderItem.Status.SHIPMENT_PICKED_UP,
        #         OrderItem.Status.OUT_FOR_DELIVERY,
        #         OrderItem.Status.DELIVERED_TO_CUSTOMER_ADDRESS,
        #         OrderItem.Status.DELIVERED_TO_PICKUP_POINT,
        #         OrderItem.Status.DELIVERED_TO_TERMINAL,
        #         OrderItem.Status.DELAYED_DELIVERY,
        #         OrderItem.Status.DELAYED_PICKUP,
        #         OrderItem.Status.DELAYED_PICKUP_BY_CUSTOMER
        #     ], 
        #     weights=[1, 1, 1, 1, 1, 1, 3, 3, 3, 1, 1, 1]
        # )[0]

        for item in items:
            delivered_at = None
            is_completed = False

            order_item = OrderItem.objects.create(
                order=order,
                variant=item,
                quantity=1,
                unit_price=item.price_override or item.product.price,
            )

            # if status in [
            #     OrderItem.Status.DELIVERED_TO_CUSTOMER_ADDRESS,
            #     OrderItem.Status.DELIVERED_TO_PICKUP_POINT,
            #     OrderItem.Status.DELIVERED_TO_TERMINAL
            # ]:
            #     # Randomly choose a delivery date: today or a few days ago
            #     days_ago = random.choice([0, 1, 2, 3, 4, 5])
            #     delivered_at = timezone.now() - timezone.timedelta(days=days_ago)

            #     # Mark as completed if more than 3 days ago or simulate review
            #     if days_ago > 3 or random.choice([True, False]):
            #         is_completed = True

            #     order_item.delivered_at=delivered_at
            #     order_item.is_completed=is_completed
            #     order_item.save(update_fields=["delivered_at", "is_completed"])

            # # Simulate return request only for delivered orders
            # if status in [
            #     OrderItem.Status.DELIVERED_TO_CUSTOMER_ADDRESS,
            #     OrderItem.Status.DELIVERED_TO_PICKUP_POINT,
            #     OrderItem.Status.DELIVERED_TO_TERMINAL
            # ] and random.choice([True, False]):
            #     # return_status = random.choice([
            #     #     OrderReturnRequest.Status.REQUESTED,
            #     #     # OrderReturnRequest.Status.REJECTED,
            #     #     # OrderReturnRequest.Status.COMPLETED
            #     # ])
            #     OrderReturnRequest.objects.create(
            #         order_item=order_item,
            #         reason="Item defective or not as described",
            #         status=OrderReturnRequest.Status.REQUESTED
            #     )

            if status == "paid":
                delivered_variants.append((buyer, item))

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

    # ❌ Skip returned or return-requested items
    if order_item.is_return_requested or order_item.is_returned:
        continue

    # ✅ Skip if this user already rated this order_item for this product
    if UserRating.objects.filter(user=buyer, order_item=order_item, product=product_index).exists():
        continue

    UserRating.objects.create(
        user=buyer,
        order_item=order_item,
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


import requests
from logistics.models import Bank
from station_addresses import stations
from logistics.utils import sync_stations_from_gigl, sync_station_addresses, register_gigl_webhook_on_table


def fetch_and_store_bank():
    """
    Function to fetch bank details from paystack
    Store in the Bank DB for use
    """
    print("Entered")
    url = f"{settings.PAYSTACK_BASE_URL}/bank?country=nigeria"
    headers = {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"
    }

    try:
        response = requests.get(url, headers=headers)
        data = response.json()
    except Exception as e:
        raise Exception(f"Paystack bank fetch issue: {e}")

    if data.get("status") is True:
        for bank in data.get("data", []):
            Bank.objects.update_or_create(
                name=bank["name"].strip(),
                defaults={
                    "code": bank["code"],
                    "slug": bank.get("slug"),
                    "active": bank.get("active", True)
                }
            )

        return F"Fetched and store {len(data.get("data", []))} banks."
    else:
        raise Exception(f"Failed to fetch banks: {data}")
    

def sync_gigl_data(station_address):
    print("Syncing GIGL data")

    print("Starting to sync stations from gigl")
    sync_stations_from_gigl()
    print("Done syncing stations from gigl")

    print("Stating to sync experience centre addresses")
    sync_station_addresses(station_address)
    print("Done syncing experience center addresses")

    print("About to register webhook for secret")
    register_gigl_webhook_on_table()
    print("Registered webhook on table")
    
if __name__ == "__main__":
    fetch_and_store_bank()
    print(f"Bank data fetched successfully")
    sync_gigl_data(stations)
    print("Done syncing gigl data")
