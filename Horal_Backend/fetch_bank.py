import os, django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Horal_Backend.settings")  # Replace this
django.setup()

from django.conf import settings
from wallet.models import Bank
import requests


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
    
if __name__ == "__main__":
    fetch_and_store_bank()
    print(f"Bank data fetched successfully")