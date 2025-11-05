from django.conf import settings
from requests.exceptions import HTTPError
from datetime import timedelta, datetime
from django.utils import timezone
from django.core.cache import cache
import pytz
import requests
import logging

logger = logging.getLogger(__name__)

# initializing with the api key
BASE_URL = settings.FEZ_BASE_URL
USERNAME = settings.FEZ_USERNAME
PASSWORD = settings.FEZ_PASSWORD


class FEZDeliveryAPI:
    """Base class for FEZ Delivery endpoint calls"""
    def __init__(self):
        try:
            self.authtoken, self.secret_key = self.get_or_refresh_token()
        except Exception as e:
            raise RuntimeError(f"Failed to initialize FEZDeliveryAPI: {e}")


    def get_or_refresh_token(self):
        token = cache.get("fez_token")
        secret = cache.get("fez_secret")
        expiry = cache.get("fez_expiry")  # stored as datetime

        now = timezone.now()
        # valid token?
        if token and expiry:
            # convert both to UTC-aware datetimes and timestamps
            expiry_utc = expiry.astimezone(pytz.UTC)
            now_utc = now.astimezone(pytz.UTC)
            
            if now_utc < expiry_utc:
                return token, secret

        # get new token
        token, secret, expiry = self.authenticate()

        # ensure expiry is aware and in UTC
        if expiry.tzinfo is None:
            expiry = timezone.make_aware(expiry, pytz.UTC)
        expiry_utc = expiry.astimezone(pytz.UTC)
        now_utc = timezone.now().astimezone(pytz.UTC)

        # compute grace time (expiry minus 10 minutes)
        grace_utc = expiry_utc - timedelta(minutes=10)
       
        # compute TTL in seconds: (grace_time - now)
        ttl_seconds = int((grace_utc - now_utc).total_seconds())

        # safety: prevent negative or tiny TTL
        ttl_seconds = max(ttl_seconds, 60)
        print(f"[FEZ] expiry_utc={expiry_utc}, grace_utc={grace_utc}, now_utc={now_utc}")
        print(f"[FEZ] TTL seconds calculated: {ttl_seconds}")

        # DEBUG log to verify
        logger.info(f"[FEZ] expiry_utc={expiry_utc}, grace_utc={grace_utc}, now_utc={now_utc}")
        logger.info(f"[FEZ] TTL seconds calculated: {ttl_seconds}")

        cache.set("fez_token", token, timeout=ttl_seconds)
        cache.set("fez_secret", secret, timeout=ttl_seconds)
        cache.set("fez_expiry", expiry, timeout=ttl_seconds)

        return token, secret


    def authenticate(self):
        """Fetch and return JWT token for api call authorization"""
        url = f"{BASE_URL}/user/authenticate"
        data = {
            "user_id": f"{USERNAME}",
            "password": f"{PASSWORD}"
        }
        try:
            res = requests.post(url, json=data)
           
            res.raise_for_status()
            authtoken = res.json()["authDetails"]["authToken"]
            secret_key = res.json()["orgDetails"]["secret-key"]

            # Parse token expiration
            expiry_str = res.json()["authDetails"]["expireToken"]
            expiry_dt = datetime.strptime(expiry_str, "%Y-%m-%d %H:%M:%S")

            # Convert to aware datetime (UTC)
            expiry_dt = timezone.make_aware(expiry_dt, timezone=pytz.UTC)

            return authtoken, secret_key, expiry_dt
        
        except HTTPError as e:
            logger.error(f"Error while authenticating on FEZ: {str(e)}")
            raise RuntimeError(f"Auth failed: {e}, response: {res.text}")
    
    
    def _headers(self):
        """header"""
        return {
            "Authorization": f"Bearer {self.authtoken}",
            "secret-key": f"{self.secret_key}",
            "Content-Type": "application/json"
        }
    

    def get_price(self, payload):
        """Get delivery price for shipments order"""
        try:
            url = f"{BASE_URL}/order/cost"
            res = requests.post(
                url, json=payload, headers=self._headers(), timeout=15
            )
            res.raise_for_status()
            return res.json()
        
        except requests.exceptions.Timeout:
            logger.error("FEZ delivery price request timed out")
            return {"error": True, "details": "Shipping provider timed out"}
        except requests.exceptions.RequestException as e:
            logger.error(f"FEZ delivery price retrieval request error: {e}")
            return {"error": True, "details": str(e)}
        except HTTPError as e:
            return {"error": str(e), "details": res.text}
    

    def create_shipment_order(self, payload):
        """Create shipment order and get order id"""
        try:
            url = f"{BASE_URL}/order"
            res = requests.post(url, json=payload, headers=self._headers(), timeout=15)
            res.raise_for_status()
            return res.json()
        
        except requests.exceptions.Timeout:
            logger.error("FEZ delivery order creation request timed out")
            return {"error": True, "details": "Shipping provider timed out"}
        except requests.exceptions.RequestException as e:
            logger.error(f"FEZ Delivery shipment order creation request error: {e}")
            return {"error": True, "details": str(e)}
        except HTTPError as e:
            return {"error": str(e), "details": res.text}
        

    def get_order_details(self, order_id):
        """Get a single order details based on order id"""
        try:
            url = f"{BASE_URL}/orders/{order_id}"
            res = requests.get(url, headers=self._headers(), timeout=15)
            res.raise_for_status()
            return res.json()
        
        except requests.exceptions.Timeout:
            logger.error("FEZ delivery order details request timed out")
            return {"error": True, "details": "Shipping provider order details timed out"}
        except requests.exceptions.RequestException as e:
            logger.error(f"FEZ Delivery order details request error: {e}")
            return {"error": True, "details": str(e)}
        except HTTPError as e:
            return {"error": str(e), "details": res.text}
        

    def search_shipment_by_waybillnumber(self, waybillNumber):
        """Search shipment using waybill number"""
        try:
            url = f"{BASE_URL}/orders/search/{waybillNumber}"
            res = requests.get(url, headers=self._headers(), timeout=15)
            res.raise_for_status()
            
            return res.json()
        
        except requests.exceptions.Timeout:
            logger.error("FEZ Delivery order search request timed out")
            return {"error": True, "details": "Shipping provider timed out"}
        except requests.exceptions.RequestException as e:
            logger.error(f"FEZ Delivery order search request error: {e}")
            return {"error": True, "details": str(e)}
        except HTTPError as e:
            return {"error": str(e), "details": res.text}
        

    def track_shipment(self, orderNumber):
        """Track shipment using FEZ Delivery worder number"""
        try:
            url = f"{BASE_URL}/order/track/{orderNumber}"
            res = requests.get(url, headers=self._headers(), timeout=15)
            res.raise_for_status()
            
            return res.json()
        
        except requests.exceptions.Timeout:
            logger.error("FEZ Delivery track order request timed out")
            return {"error": True, "details": "Shipping provider timed out"}
        except requests.exceptions.RequestException as e:
            logger.error(f"FEZ Delivery track order request error: {e}")
            return {"error": True, "details": str(e)}
        except HTTPError as e:
            return {"error": str(e), "details": res.text}
        

    def track_entire_order(self, payload):
        """Post method to track an entire order for a single user"""
        try:
            url = f"{BASE_URL}/orders/search"
            res = requests.post(
                url, json=payload, headers=self._headers(), timeout=15
            )
            res.raise_for_status()
            return res.json()
        
        except requests.exceptions.Timeout:
            logger.error("FEZ delivery order status search request timed out")
            return {"error": True, "details": "Shipping provider timed out"}
        except requests.exceptions.RequestException as e:
            logger.error(f"FEZ delivery order delivery statuses request error: {e}")
            return {"error": True, "details": str(e)}
        except HTTPError as e:
            return {"error": str(e), "details": res.text}
        

    def estimate_delivery_time(self, payload):
        """Return estimated delivery time for an order"""
        try:
            url = f"{BASE_URL}/delivery-time-estimate"
            res = requests.post(url, json=payload, headers=self._headers(), timeout=15)
            res.raise_for_status()
            
            return res.json()
        
        except requests.exceptions.Timeout:
            logger.error("FEZ Delivery delivery estimation request timed out")
            return {"error": True, "details": "Shipping provider timed out"}
        except requests.exceptions.RequestException as e:
            logger.error(f"FEZ Delivery delivery estimation request error: {e}")
            return {"error": True, "details": str(e)}
        except HTTPError as e:
            return {"error": str(e), "details": res.text}    
    
    
    def register_webhook(self):
        """Register webhook for the FEZ Delivery event status update"""
        payload = {"webhook": settings.HORAL_FEZ_WEBHOOK.strip()}
        try:
            url = f"{BASE_URL}/webhooks/store"
            res = requests.post(url, json=payload, headers=self._headers(), timeout=15)
            res.raise_for_status()
            return res.json()
        
        except requests.exceptions.Timeout:
            logger.error("FEZ Delivery webhook registration request timed out")
            return {"error": True, "details": "Shipping provider timed out"}
        except requests.exceptions.RequestException as e:
            logger.error(f"FEZ Delivery webhook reg request error: {e}")
            return {"error": True, "details": str(e)}
        except HTTPError as e:
            return {"error": str(e), "details": res.text}
                  
