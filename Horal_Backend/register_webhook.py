import os, sys
import django

# Add the base directory to sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)

# Set the settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Horal_Backend.settings')

# Setup Django
django.setup()

from logistics.utils import register_webhook_view
from orders.tasks import create_fez_shipment_on_each_shipment

result = create_fez_shipment_on_each_shipment.delay("08069fbd754b4c4cac0f1abd2b89824b")
print(f"result: {result}")

def register_webhook():
    print("Syncing FEZ Delivery Data to Register Webhook")

    print("About to register webhook")
    result = register_webhook_view()
    print(f"Registered webhook result: {result}")


# if __name__ == "__main__":
    # register_webhook()