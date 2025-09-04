import os, sys
import django

# Add the base directory to sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)

# Set the settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Horal_Backend.settings')

# Setup Django
django.setup()

# os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Horal_Backend.settings')
# django.setup()

from users.models import CustomUser
from categories.models import Category
from subcategories.models import SubCategory

from django.conf import settings

from sellers_dashboard.models import (
    RawSale, WeeklySales, WeeklyShopSales, MonthlySales,
    SalesAdjustment, DailyShopSales, DailySales, MonthlyShopSales,
    YearlySales, YearlyShopSales
)
from wallet.models import SellersBankDetails, SellerTransactionHistory, Payout
from support.models import SupportTeam
from wallet.models import Bank
import requests
from station_addresses import stations
from logistics.utils import sync_stations_from_gigl, sync_station_addresses, register_gigl_webhook_on_table


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
        "gps & navigation", "e-readers", "vr/ar devices", "laptop"
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


# Create categories and subcategories
category_map = {}
subcategory_map = {}

for cat_name, subs in categories_data.items():
    category = Category.objects.create(name=cat_name)
    category_map[cat_name] = category
    for sub in subs:
        subcat = SubCategory.objects.create(category=category, name=sub, slug=sub.lower().replace(" ", "-"))
        subcategory_map[(cat_name, sub)] = subcat


admin = CustomUser.objects.create_superuser(
        email=f"horal@horal.ng",
        password="HoralTech@2025",
        full_name=f"Horal Admin",
        phone_number=f"08131534279",
        is_active=True
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
