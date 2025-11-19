import os, sys
import django

# Add the base directory to sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)

# Set the settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Horal_Backend.settings')

# Setup Django
django.setup()
from products.image_scan import scan_all_product_images, scan_image_model
from products.models import (
    VehicleImage, FashionImage, ElectronicsImage,
    FoodImage, HealthAndBeautyImage, AccessoryImage,
    ChildrenImage, GadgetImage
)
from django.conf import settings
bucket_name = settings.AWS_STORAGE_BUCKET_NAME

print("Starting broken image scan and cleanup...")
scan_image_model(AccessoryImage, bucket_name)
print("Completed VehicleImage scan.")