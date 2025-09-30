from django.conf import settings
from requests.exceptions import HTTPError
import requests
import logging

logger = logging.getLogger(__name__)

# initializing with the api key
BASE_URL = settings.GIGL_BASE_URL
USERNAME = settings.GIGL_USERNAME
PASSWORD = settings.GIGL_PASSWORD


class GIGLogisticsAPI:
    """Base class for GIGL endpoint calls"""
    def __init__(self):
        self.token = self.authenticate()

    def authenticate(self):
        """Fetch and return JWT token for api call authorization"""
        url = f"{BASE_URL}/login"
        data = {
            "username": f"{USERNAME}",
            "password": f"{PASSWORD}",
            "sessionObj": ""
        }
        try:
            res = requests.post(url, json=data)
            res.raise_for_status()
            token = res.json()["data"]["token"]

            return token
        except HTTPError as e:
            return {"error": str(e), "details": res.text}
    
    
    def _headers(self):
        """header"""
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
    

    def get_price(self, payload):
        """Get delivery price for shipments"""
        try:
            url = f"{BASE_URL}/price"
            res = requests.post(
                url, json=payload, headers=self._headers(), 
                timeout=(5, 10)  # 5s connect, 10s read
            )
            res.raise_for_status()
            return res.json()
        
        except requests.exceptions.Timeout:
            logger.error("GIGL price request timed out")
            return {"error": True, "details": "Shipping provider timed out"}
        except requests.exceptions.RequestException as e:
            logger.error(f"GIGL request error: {e}")
            return {"error": True, "details": str(e)}
        except HTTPError as e:
            return {"error": str(e), "details": res.text}
    

    def create_shipment(self, payload):
        """Create shipment and get waybill"""
        try:
            url = f"{BASE_URL}/captureshipment"
            res = requests.post(url, json=payload, headers=self._headers(), timeout=15)
            res.raise_for_status()
            return res.json()
        
        except requests.exceptions.Timeout:
            logger.error("GIGL price request timed out")
            return {"error": True, "details": "Shipping provider timed out"}
        except requests.exceptions.RequestException as e:
            logger.error(f"GIGL request error: {e}")
            return {"error": True, "details": str(e)}
        except HTTPError as e:
            return {"error": str(e), "details": res.text}
        

    def track_shipment(self, waybill):
        """Track shipment using waybill"""
        try:
            url = f"{BASE_URL}/TrackAllMobileShipment/{waybill}"
            res = requests.get(url, headers=self._headers(), timeout=15)
            res.raise_for_status()
            
            return res.json()
        
        except requests.exceptions.Timeout:
            logger.error("GIGL price request timed out")
            return {"error": True, "details": "Shipping provider timed out"}
        except requests.exceptions.RequestException as e:
            logger.error(f"GIGL request error: {e}")
            return {"error": True, "details": str(e)}
        except HTTPError as e:
            return {"error": str(e), "details": res.text}
        
    
    def get_stations(self):
        """Get List of GIGL stations"""
        try:
            url = f"{BASE_URL}/localStations"
            res = requests.get(url, headers=self._headers(), timeout=15)
            res.raise_for_status()

            return res.json()
        
        except requests.exceptions.Timeout:
            logger.error("GIGL price request timed out")
            return {"error": True, "details": "Shipping provider timed out"}
        except requests.exceptions.RequestException as e:
            logger.error(f"GIGL request error: {e}")
            return {"error": True, "details": str(e)}
        except HTTPError as e:
            return {"error": str(e), "details": res.text}
    
    
    def register_webhook(self):
        """Register webhook for the gigl event status update"""
        payload = {"url": settings.HORAL_GIGL_WEBHOOK}
        try:
            url = settings.GIGL_WEBHOOK
            res = requests.post(url, json=payload, headers=self._headers(), timeout=15)
            res.raise_for_status()
            return res.json()
        
        except requests.exceptions.Timeout:
            logger.error("GIGL price request timed out")
            return {"error": True, "details": "Shipping provider timed out"}
        except requests.exceptions.RequestException as e:
            logger.error(f"GIGL request error: {e}")
            return {"error": True, "details": str(e)}
        except HTTPError as e:
            return {"error": str(e), "details": res.text}
         
