from django.conf import settings
from .bulk_sms_error import BSNG_ERROR_MAP
import requests, json
import logging

logger = logging.getLogger(__name__)


base_url = settings.BULK_SMS_BASE_URL
# api_token = settings.BULK_SMS_API
api_token = settings.BULK_SMS_LEGACY_API
sender_id = settings.BULK_SMS_SENDER_ID


class BulkSMSAPI():
    """Class to handle API integration for Bulk SMS Nigeria Service"""

    def __init__(self):
        self.base_url = base_url
        self.api_token = api_token
        self.sender_id = sender_id


    def _headers(self):
        """Generate headers for API requests"""
        return {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
    

    def send_sms(self, to_number, message, gateway=None):
        """Send SMS to a given number with the specified message"""
        url_endpoint = f"{self.base_url}/v2/sms"

        # Build the payload
        payload = {
            "from": f"{self.sender_id}",
            "to": to_number,
            "body": message
        }

        # Include gateway in payload if provided
        if gateway:
            payload["gateway"] = gateway
        
        response = requests.post(url_endpoint, json=payload, headers=self._headers(), timeout=30)

        result = response.json()

        if result.get("status") == "error":
            status_code = result.get("code")
            error_info = BSNG_ERROR_MAP.get(status_code, {"http": 500, "message": "Unknown error"})
            logger.error(f"Bulk SMS API Error {status_code}: {error_info['message']}")
            raise Exception(f"Bulk SMS API Error {status_code}: {error_info['message']}")
        elif result.get("status") == "success":
            logger.info(f"SMS sent successfully to {to_number}\nData: {result.get("data")}")
