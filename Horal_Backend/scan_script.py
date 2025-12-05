import os, sys
import django

# Add the base directory to sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)

# Set the settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Horal_Backend.settings')

# Setup Django
django.setup()
from products.tasks import task_scan_and_clean_images

print("Starting broken image scan and cleanup...")
task_scan_and_clean_images()
print("Completed Image scan.")