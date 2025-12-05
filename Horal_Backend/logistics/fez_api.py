from django.conf import settings
from requests.exceptions import HTTPError
from datetime import timedelta, datetime
from django.utils import timezone
from django.core.cache import cache
import requests
import logging

logger = logging.getLogger(__name__)

# initializing with the api key
BASE_URL = settings.FEZ_BASE_URL
USERNAME = settings.FEZ_USERNAME
PASSWORD = settings.FEZ_PASSWORD

STRICT_TTL_SECONDS = 150 * 60   # 2hrs 30mins = 9000 seconds


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

        # Return token and secret if still valid
        if token and secret:
            return token, secret

        # get new token
        token, secret = self.authenticate()

        # Ignore: expiry from fez and use strict fixed TTL of 2hrs 30mins
        ttl_seconds = STRICT_TTL_SECONDS

        logger.info(f"fixed [FEZ] TTL seconds calculated: {ttl_seconds}")

        cache.set("fez_token", token, timeout=ttl_seconds)
        cache.set("fez_secret", secret, timeout=ttl_seconds)

        # Store expiry just for debugging, not used for validation
        forced_expiry = timezone.now() + timedelta(seconds=ttl_seconds)
        cache.set("fez_expiry", forced_expiry, timeout=ttl_seconds)

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

            return authtoken, secret_key
        
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
    

    def invalidate_fez_cache(self):
        """Delete all FEZ token cache items so next request forces fresh authentication."""
        cache.delete("fez_token")
        cache.delete("fez_secret")
        cache.delete("fez_expiry")
        logger.warning("FEZ cache invalidated — token will be refreshed on next request.")

    
    def fex_request(self, method, url, retry=False, **kwargs):
        """
        Method to handle sending request to FEZ delivery. 
        If FEZ returns 5xx (or network error):
            - Invalidate cached token and secret
            - Refresh token and retry once
        """
        try:
            res = requests.request(
                method, url, headers=self._headers(), timeout=15, **kwargs
            )
        except requests.exceptions.RequestException as e:
            # Network level error: invalidate and retry once
            logger.error(f"FEZ network error: {e}")
            if not retry:
                self.invalidate_fez_cache()
                # Force refresh
                self.authtoken, self.secret_key = self.get_or_refresh_token()
                return self.fex_request(method, url, retry=True, **kwargs)

            # Already retried => propagate to None and allow method caller to handle it
            return None
        
        # If success => return response
        if res.status_code < 400:
            return res
        
        # For 5xx and 401 response, invalidate and retry once
        if (res.status_code == 401 or 500 <= res.status_code < 600) and not retry:
            logger.warning(f"FEZ returned {res.status_code}. Invalidate token and retrying once")
            self.invalidate_fez_cache()
            self.authtoken, self.secret_key = self.get_or_refresh_token()
            return self.fex_request(method, url, retry=True, **kwargs)
        
        # Else return the response for calling method to parse
        return res


    def get_price(self, payload):
        """Get delivery price for shipments order"""
        try:
            url = f"{BASE_URL}/order/cost"
            # res = requests.post(
            #     url, json=payload, headers=self._headers(), timeout=15
            # )
            res = self.fex_request("POST", url, json=payload)
            
            if res is None:
                # Network error and retry exhausted
                return {
                    "error": True,
                    "details": "Network or provider failure"
                }
            
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
            # res = requests.post(url, json=payload, headers=self._headers(), timeout=15)
            res = self.fex_request("POST", url, json=payload)
            
            if res is None:
                # Network error and retry exhausted
                return {
                    "error": True,
                    "details": "Network or provider failure"
                }
            
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
            # res = requests.get(url, headers=self._headers(), timeout=15)
            
            res = self.fex_request("GET", url)
            
            if res is None:
                # Network error and retry exhausted
                return {
                    "error": True,
                    "details": "Network or provider failure"
                }
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
            # res = requests.get(url, headers=self._headers(), timeout=15)
            
            res = self.fex_request("GET", url)
            
            if res is None:
                # Network error and retry exhausted
                return {
                    "error": True,
                    "details": "Network or provider failure"
                }
            
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
            # res = requests.get(url, headers=self._headers(), timeout=15)
            
            res = self.fex_request("GET", url)
            
            if res is None:
                # Network error and retry exhausted
                return {
                    "error": True,
                    "details": "Network or provider failure"
                }
            
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
            # res = requests.post(
            #     url, json=payload, headers=self._headers(), timeout=15
            # )

            res = self.fex_request("POST", url, json=payload)
            
            if res is None:
                # Network error and retry exhausted
                return {
                    "error": True,
                    "details": "Network or provider failure"
                }
            
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
            # res = requests.post(url, json=payload, headers=self._headers(), timeout=15)
            
            res = self.fex_request("POST", url, json=payload)
            
            if res is None:
                # Network error and retry exhausted
                return {
                    "error": True,
                    "details": "Network or provider failure"
                }
            
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
            # res = requests.post(url, json=payload, headers=self._headers(), timeout=15)
            
            res = self.fex_request("POST", url, json=payload)
            
            if res is None:
                # Network error and retry exhausted
                return {
                    "error": True,
                    "details": "Network or provider failure"
                }
            
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
                  
