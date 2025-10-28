from django.conf import settings
from requests.exceptions import HTTPError
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
            self.authtoken, self.secret_key = self.authenticate()
        except Exception as e:
            raise RuntimeError(f"Failed to initialize FEZDeliveryAPI: {e}")

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
            return {"error": str(e), "details": res.text}
    
    
    def _headers(self):
        """header"""
        return {
            "Authorization": f"{self.authtoken}",
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
                  
