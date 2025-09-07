import os, django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Horal_Backend.settings")  # Replace this
django.setup()

from django.conf import settings
from wallet.models import Bank
from logistics.utils import (
    sync_station_addresses,
    sync_stations_from_gigl,
    register_gigl_webhook_on_table,
    save_gigl_webhook_data,
    decrypt_webhook_data
)
from logistics.models import GIGLWebhookCredentials
from station_addresses import stations
import requests, json
from django.http import JsonResponse


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
    print("Started sync")
    sync_stations_from_gigl()
    print("Stations synced")
    sync_station_addresses(station_address)
    print("Station addresses synced")
    register_gigl_webhook_on_table()
    print("Webhook registered")


def gigl_webhook(encrypted_data):
    try:

        # Get secret
        webhook_s = GIGLWebhookCredentials.objects.first()
        print(f"Webhook secret from DB: {webhook_s.secret if webhook_s else 'None'}")

        # if not webhook_s:
        #     return JsonResponse({"error": "Webhook secret not found"}, status=500)
        
        secret = "vgWA4WiL1pqtfFCvu3vb"

        # Decrypt
        decrypted_json_str = decrypt_webhook_data(encrypted_data, secret)

        # Check the authenticity of the payload
        data = json.loads(decrypted_json_str)
        print(data)

        # Normalize values for comparison
        db_user_id = str("949c9c99-5dd7-4db1-8980-1cbb3fa8fc99")  # Convert UUID object to string
        payload_user_id = str(data.get("UserId")).strip()  # Strip whitespace
        db_channel_code = str("IND298636").strip()
        payload_channel_code = str(data.get("ChannelCode")).strip()
        print(f"Payload UserId: {payload_user_id}, DB UserId: {db_user_id} | Payload ChannelCode: {payload_channel_code}, DB ChannelCode: {db_channel_code}")

        if payload_user_id != db_user_id or payload_channel_code != db_channel_code:
            print(f"Payload UserId: {payload_user_id}, DB UserId: {db_user_id} | Payload ChannelCode: {payload_channel_code}, DB ChannelCode: {db_channel_code}")
        
        decrypted = {'Waybill': '1349105650', 'SenderAddress': '2d1 Emmanuel Olorunfemi St, Ifako Agege, Lagos, Nigeria', 'ReceiverAddress': '39 Dominos Pizza Gbagada,1A Idowu Olaitan St, Gbagada, Lagos, Nigeria', 'Location': None, 'Status': 'DELIVERED_TO_CUSTOMER_ADDRESS', 'UserId': '949c9c99-5dd7-4db1-8980-1cbb3fa8fc99', 'ChannelCode': 'IND298636', 'StatusCode': 'MAHD'}

        decrypted_json = json.dumps(decrypted)
        print(f"Decrypted JSON: {decrypted_json}")
        
        # Save GIGL webhook data
        save_gigl_webhook_data(decrypted_json)

        return JsonResponse({
            "status": "received",
            "message": "Webhook received successfully"
        }, status=200)
    except Exception as e:
        return JsonResponse({
            "error": str(e)
        }, status=400)
    
if __name__ == "__main__":
    # fetch_and_store_bank()
    # print(f"Bank data fetched successfully")
    # sync_gigl_data(stations)
    # print("GIGL data sync completed successfully")

    encrypted_data = "v2s/XHqwrg7jlNmn1+QVJmMVTN1XUVCfAeqUPtMuIwXjyO8239tJmHScQoGNs4RAPopNcwAvIxLsb802xIAosF4yWQc6nLh4vwT9yC/0+DzRXQYPCO/C/bc7vsYn2tUcjW5pZYKeAogitHgYh6kZEMQrD4YvXIxpOdwDkPKmDufuhPXkvjnatCg46rpDsTP9Zd5O460NVBsMahhs8/bGbD2/3DahuzZ1nmHmtxgZxWcmTVUFB8T/JLPNO3EIYdF/lp7NWPHXjbXv5zprNxdHvraje/7cpAZQW2MNazjVH7DBpT5MMk6lQocwwJ4gvtfrvSPJc5ui6UN+j/Q5xHk+p1dDj6LXnRowVPy7+E4M4NVrb7rKtfN8A1HLgC5SAdfSllV0EikxkqRaYdIrcjG5SDjXUgNP2+zWQcHSORHXiLdqR4jVAgAQcGLz8h+vsWF1iny2rTQNA4EiXNaNj7FtBP0H1lVWq5DTaMSlI6BJ9kjpWOphVYrK4AsQDYKJFJ4D"
    gigl_webhook(encrypted_data)  # Replace with actual encrypted data for testing



# GIGL_TO_ORDER_STATUS = {
#     'CRT': OrderShipment.Status.SHIPMENT_CREATED,
#     'MCRT': OrderShipment.Status.SHIPMENT_CREATED_BY_CUSTOMER,
#     'AD': OrderShipment.Status.AVAILABLE_FOR_PICKUP,
#     'MPIK': OrderShipment.Status.SHIPMENT_PICKED_UP,
#     'OFDU': OrderShipment.Status.OUT_FOR_DELIVERY,
#     'MAFD': OrderShipment.Status.SHIPMENT_ARRIVED_FINAL_DESTINATION,
#     'MAHD': OrderShipment.Status.DELIVERED_TO_CUSTOMER_ADDRESS,
#     'OKC': OrderShipment.Status.DELIVERED_TO_PICKUP_POINT,
#     'OKT': OrderShipment.Status.DELIVERED_TO_TERMINAL,
#     'DLD': OrderShipment.Status.DELAYED_DELIVERY,
#     'DLP': OrderShipment.Status.DELAYED_PICKUP,
#     'DUBC': OrderShipment.Status.DELAYED_PICKUP_BY_CUSTOMER
# }
