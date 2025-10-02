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


food_sub = [
    "fruits", "vegetables", "grains or cereals", "legumes or pulses",
        "nuts and seeds", "meat and poultry", "fish and seafood", "dairy", "eggs", "fats and oils", "herbs and spices",
        "confectionery and snacks", "others"
]

categories = Category.objects.all()
food_cat = Category.objects.get(name="foods")

for sub in food_sub:
    subcat = SubCategory.objects.get_or_create(category=food_cat, name=sub, slug=sub.lower().replace(" ", "-"))
    print(subcat)

for cat in categories:
    if cat.name != "foods":
        subcat = SubCategory.objects.get_or_create(category=cat, name="others", slug="others")
        print(subcat)
