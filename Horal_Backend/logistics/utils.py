from django.conf import settings
from .fez_api import FEZDeliveryAPI
from sellers.models import SellerKYC, SellerKYCAddress
from decimal import Decimal
from orders.models import OrderShipment
from typing import Optional
import googlemaps, math
from collections import defaultdict
from django.utils.timezone import now
from products.models import ProductIndex
from .models import GIGLShipment
from typing import Optional, Dict, Any
from django.core.exceptions import ValidationError
import base64, hashlib, json
from django.core.cache import cache
from django.db.models import Q
from Crypto.Cipher import AES
import logging, traceback

logger = logging.getLogger(__name__)

# initializing with the api key
gmaps = googlemaps.Client(key=settings.GOOGLE_API_KEY)    


def get_coordinates(address):
    # Try to get coordinates from cache
    cached = cache.get(address)
    if cached:
        return cached

    try:
        geocode_result = gmaps.geocode(address)
        if geocode_result:
            location = geocode_result[0]['geometry']['location']
            lat_lng = (location['lat'], location['lng'])

            # Cache in Redis for 3 months
            cache.set(address, lat_lng, timeout=7776000)
            return lat_lng

        return None, None
    except Exception as e:
        logger.warning(f"Error fetching coordinates: {e}")
        return None, None


def get_seller_kyc(seller):
    # Find seller's address record
    seller_kyc = SellerKYCAddress.objects.get(id=seller.address.id)
    return seller_kyc

def _safe_str(x) -> str:
    return "" if x is None else str(x)


def _buyer_full_address(order) -> str:
    """
    Get buyers address from order model
    which inherits ShippingSnapshotMixin
    """
    parts = [order.street_address, order.local_govt, order.state, order.country]
    return ", ".join([p for p in parts if p]), str(order.state)


def _seller_full_address(seller_kyc: SellerKYCAddress) -> str:
    """Get seller address from their kyc information"""
    parts = [seller_kyc.street, seller_kyc.lga, seller_kyc.state, "Nigeria"]
    return ", ".join([p for p in parts if p]), str(seller_kyc.state)


def _extract_weight_kg(item, default_kg: float=1.0) -> float:
    """
    Get the weight from product variant multiplied by the quantity
    properly handling quantity and unit conversion.
    """
    from .models import Logistics
    from django.core.exceptions import ObjectDoesNotExist

    try:
        logistics = Logistics.objects.get(product_variant=item.variant)
    except ObjectDoesNotExist as e:
        logger.warning(f"Logistics entry not found for variant {item.variant.id}: {str(e)}")
        try:
            logistics = Logistics.objects.get(object_id=item.variant.object_id)
        except ObjectDoesNotExist as e:
            logger.warning(f"Logistics entry not found for product {item.variant.object_id}: {str(e)}")
            logistics = None  # or raise a validation error
    
    quantity = getattr(item, "quantity", 1)

    if not logistics:
        return default_kg * quantity
    
    weight_value = getattr(logistics, "weight_measurement", None)
    weight_unit = getattr(logistics, "total_weight", None)

    if not weight_value or not weight_unit:
        weight = default_kg * quantity

        return weight
    
    # weight_unit = str(weight_unit).upper()

    # Conversion factors to KG
    conversion_to_kg = {
        "g": 0.001,
        "kg": 1,
    }

    # Ensure consistent lowercase
    weight_value = str(weight_value).lower()

    total_weight_kg = float(weight_unit) * quantity * conversion_to_kg[weight_value]

    return total_weight_kg



def haversine_distance(coord1, coord2):
    """
    coord1, coord2: tuples (lat, lng) in decimal degrees
    Returns distance in kilometers
    """

    R = 6371 # Earth radius in km
    lat1, lon1 = coord1
    lat2, lon2 = coord2
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(delta_lambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

    return R * c
    

def build_gigl_payload_for_item(
    *,
    recipientName: str,
    recipientPhone: str,
    recipientAddress: str,
    recipientState: str,
    recipientEmail: str,
    uniqueID: str,
    BatchID: str,
    itemDescription: str,
    additionalDetails: str,
    weight: int,
    pickUpAddress: str,
    pickUpState: str,
    valueOfItem: str,
    waybillNumber: str,
) -> Dict[str, Any]:
    """
    Build a FEZ Delivery payload for a (possibly grouped) 'single package' using the exact
    fields provided by the caller. Returns a dict suitable for:
      - POST /order
    """

    payload = {
        "PreShipmentMobileId": 0,

        # Sender / Receiver (flat fields)
        "recipientAddress": recipientAddress,
        "recipientState": recipientState,
        "recipientName": recipientName,
        "recipientPhone": recipientPhone,
        "recipientEmail": recipientEmail,
        "uniqueID": uniqueID,
        "BatchID": BatchID,
        "itemDescription": itemDescription,
        "additionalDetails": additionalDetails,
        "valueOfItem": valueOfItem,
        "weight": weight,
        "pickUpState": pickUpState,
        "pickUpAddress": pickUpAddress,
        "waybillNumber": waybillNumber,
    }

    return payload


def group_order_items_by_seller(order):
    """
    Function to group order items by seller to lessen shipping
    cost for buyers purchasing from a single seller
    """
    try:
        seller_orders = defaultdict(lambda: {"items": [], "station": None, "weight": 0.0, "seller": None})
        # item_weight = 0
        for item in order.order_items.all():
            shop = item.variant.shop
            seller = SellerKYC.objects.get(user=shop.owner.user)
            
            # Extract weight
            item_weight = _extract_weight_kg(item)
        
            # Store order info
            seller_orders[seller]["items"].append(item)
            seller_orders[seller]["weight"] += item_weight
            seller_orders[seller]["seller"] = seller
        
        return seller_orders
    except Exception as e:
        logger.error(f"Error grouping order items by seller: [{order}]\nerror: {str(e)}")
        raise ValidationError(f"Error grouping order items by seller: {str(e)}")


def create_fez_shipment_for_shipment(order_id):
    """
    Create shipments in FEZ Delivery for a single order.
    Returns True if all shipments were successfully created and updated, else False.
    """
    from orders.models import Order, OrderShipment
    api = FEZDeliveryAPI()

    # Get the order instance
    try:
        order = Order.objects.get(id=order_id)
    except Order.DoesNotExist:
        logger.warning(f"Order not found for: {order_id}")
        return False

    # Build shipment payloads
    shipment_payloads = create_shipment_payload(order)

    all_success = True  # track overall success

    for shipment, payload in shipment_payloads:
        try:
            if not shipment.fez_order_id:
                logger.info(f"Creating shipment for {shipment.id} with payload {payload}")
                result = api.create_shipment_order(payload)
                logger.info(f"FEZ Delivery response for shipment {shipment.id}: {result}")

                if result.get("status", "").lower() == "success":
                    order_nums = result.get("orderNos", {})

                    if order_nums:
                        for val in list(order_nums.values()):
                            shipment.fez_order_id = val
                            shipment.status = OrderShipment.Status.SHIPMENT_INITIATED
                            shipment.save(update_fields=["fez_order_id", "status"])
                            logger.info(f"Shipment {shipment.id} saved with fez_order_id: [{val}]")
                    else:
                        logger.warning(f"No order id returned for shipment {shipment.id}. Response: {result}")
                        all_success = False
            else:
                logger.info(f"Shipment {shipment.id} already has fez order id: [{shipment.fez_order_id}], skipping creation.")
        except Exception as e:
            logger.warning(f"Error creating shipment {shipment.id}: {e}")
            all_success = False

    return all_success



def create_shipment_payload(order):
    """
    Create shipment payloads grouped by seller (not per item).
    Returns a list of payload dicts (one per seller/shipment).
    """
    try:
        shipments = []

        for shipment in order.shipments.select_related("order__user", "seller"):
            # Build payload for seller shipment
            seller_kyc = get_seller_kyc(shipment.seller)

            if not seller_kyc:
                logger.warning(f"Seller KYC not found for seller {shipment.seller.user} to create shipment")
                raise ValueError(f"Seller KYC not found for seller {shipment.seller.user} when creating shipment payload")
            
            # Compute totals
            item_total_price = _safe_str(shipment.total_price)
            total_weight = shipment.total_weight
            unique_id = shipment.unique_id
            batch_id = shipment.batch_id
            waybill_number = shipment.waybill_number

            # Build seller address string
            seller_address, seller_state = _seller_full_address(seller_kyc)
            additional_details = (
                f"Seller / Pickup person name: {seller_kyc.first_name} {seller_kyc.last_name}\n"
                f"Seller phone number: {_safe_str(seller_kyc.mobile)}"
            )

            # Build buyer address string
            buyer_address, buyer_state = _buyer_full_address(order)

            titles = []

            for t in shipment.items.all():
                product = ProductIndex.objects.get(id=t.variant.object_id)
                titles.append(product.title)


            description = ", ".join(titles)
            title = f"Shipment for {order.user.full_name} ({len(titles)} items)"


            # Build shipment payload
            payload = build_gigl_payload_for_item(
                recipientAddress=buyer_address,
                recipientState=buyer_state,
                recipientName=order.user.full_name,
                recipientPhone=_safe_str(order.phone_number),
                recipientEmail=order.user.email,
                uniqueID=unique_id,
                BatchID=batch_id,
                itemDescription=description,
                additionalDetails=additional_details,
                valueOfItem=item_total_price,
                weight=total_weight,
                pickUpState=seller_state,
                pickUpAddress=seller_address,
                waybillNumber=waybill_number
            )
            shipments.append((shipment, payload))
        
        return shipments
    except Exception as e:
        logger.error(f"Error creating shipment payload for order: [{order}]\nerror: {str(e)}")
        raise ValidationError(f"Error creating shipment payload: {str(e)}")


def create_price_payload(order):
    """
    Create price payloads grouped by seller (not per item).
    Returns a list of payload dicts (one per seller/order_price).
    """
    try:
        order_price = []

        for shipment in order.shipments.select_related("order__user", "seller"):
            # Build payload for seller shipment
            seller_kyc = get_seller_kyc(shipment.seller)

            if not seller_kyc:
                logger.warning(f"Seller KYC not found for seller {shipment.seller.user} to fetch price")
                raise ValueError(f"Seller KYC not found for seller {shipment.seller.user} when creating price payload")
            
            # Compute totals
            total_weight = shipment.total_weight

            # Build seller address string
            _, seller_state = _seller_full_address(seller_kyc)

            # Build buyer address string
            _, buyer_state = _buyer_full_address(order)

            # Build shipment payload
            payload = {
                "state": buyer_state,
                "pickUpState": seller_state,
                "weight": total_weight
            }

            order_price.append((shipment, payload))
        
        return order_price
    except Exception as e:
        logger.error(f"Error creating pricing payload for order: [{order}]\nerror: {str(e)}")
        raise ValidationError(f"Error creating pricing payload: {str(e)}")


def calculate_shipping_for_order(order):
    """
    Calculate and update shipping cost for every item in an order.
    Returns (items_shipping_total, updated_items_list)
    """
    try:
        api = FEZDeliveryAPI()
        shipping_total = Decimal("0.00")
        updated_items = []

        # Create grouped shipment payloads
        try:
            shipment_payloads = create_price_payload(order)
        except Exception as e:
            logger.error(f"Error creating pricing payloads for order {order.id}: {str(e)}\n{str(traceback.format_exc())}")
            raise ValidationError(f"Error creating pricing payload for order: {str(e)}")

        for shipment, payload in shipment_payloads:
            result = api.get_price(payload)

            # Ensure result is valid and contains deliveryPrice
            if result.get("status", "").lower() == "success":
                cost_list = result.get("Cost", [])
                if cost_list and isinstance(cost_list, list):
                    delivery_price = cost_list[0].get("cost")
                else:
                    delivery_price = None

            if not delivery_price or Decimal(str(delivery_price)) <= 0:
                logger.error(f"No valid shipping price returned for shipment {shipment.id}. Result: {result}")
                raise ValidationError(f"Could not retrieve shipping price for shipment {shipment.id}")

            try:
                price = Decimal(str(delivery_price))
            except Exception as e:
                logger.warning(f"Error parsing price for shipment {shipment.id}: {e}")
                raise ValueError(f"Error retrieving shipment price from GIGL: {str(e)}")

            # Apply shipping price back to each shipment item
            shipment.shipping_cost = price
            shipment.save(update_fields=["shipping_cost"])

            updated_items.append({
                "shipment_id": str(shipment.id),
                "tracking_number": str(shipment.tracking_number),
                "total_weight": f"{shipment.total_weight}KG",
                "shipping_cost": str(shipment.shipping_cost),
            })

            shipping_total += price

        return shipping_total, updated_items
    except Exception as e:
        logger.error(f"Error processing shipping cost for order: [{order}]\nerror: {str(e)}")
        raise ValidationError(f"Error processing shipping cost: {str(e)}")


def get_order_details(order_id):
    """
    Function to retrieve the details of a single order
    """
    try:
        api = FEZDeliveryAPI()
        result = api.get_order_details(order_id)

        if result.get("status").lower() == "success":
            shipment_data = result.get("orderDetails")

            if shipment_data and isinstance(shipment_data, list):
                return shipment_data
            
    except Exception as e:
        logger.error(f"Error retrieving order details for fez order id: [{order_id}]\nerror: {str(e)}")
        raise ValidationError(f"Error retrieving a single shipment order details: {str(e)}")


def search_shipment_with_waybill(waybill):
    """
    Function to search if a shipment was created using waybill number
    """
    try:
        api = FEZDeliveryAPI()
        result = api.search_shipment_by_waybillnumber(waybill)

        if result.get("status", "").lower() == "success":
            order_data = result.get("data")

            if order_data and isinstance(order_data, dict):
                return order_data
            
    except Exception as e:
        logger.error(f"Error while searching shipment with waybill number: [{waybill}]\nerror: {str(e)}")
        raise ValidationError(f"Error while searching shipment with waybill number: {str(e)}")


def track_shipment_by_order_number(order_number):
    """
    Function to track a single order shipment using order number from FEZ Delivery
    """
    try:
        api = FEZDeliveryAPI()
        result = api.track_shipment(order_number)

        if result.get("status").lower() == "success":
            return result
            
    except Exception as e:
        logger.error(f"Error while retrieving tracking data for fez order id: [{order_number}]\nerror: {str(e)}")
        raise ValidationError(f"Error retriving tracking data: {str(e)}")


def create_delivery_estimate_payload(order):
    """
    Create delivery estimate payloads grouped by seller (not per item).
    Returns a list of payload dicts (one per seller/shipment).
    """
    try:
        shipments = []

        for shipment in order.shipments.select_related("order__user", "seller"):
            # Build payload for seller shipment
            seller_kyc = get_seller_kyc(shipment.seller)

            if not seller_kyc:
                logger.warning(f"Seller KYC not found for seller {shipment.seller.user} to get delivery estimate")
                raise ValueError(f"Seller KYC not found for seller {shipment.seller.user} when getting delivery estimate")

            # Build seller address string
            _, seller_state = _seller_full_address(seller_kyc)

            # Build buyer address string
            _, buyer_state = _buyer_full_address(order)

            # Build shipment payload
            payload = {
                "delivery_type": "local",
                "pick_up_state": seller_state,
                "drop_off_state": buyer_state
            }

            shipments.append((shipment, payload))
        
        return shipments
    except Exception as e:
        logger.error(f"Error creating delivery estimate payload for order: [{order}]\nerror: {str(e)}")
        raise ValidationError(f"Error creating delivery estimate payload: {str(e)}")


def estimate_shipment_delivery_time(order):
    """Function that returns the delivery estimate for orders"""
    try:
        delivery_estimates = []

        api = FEZDeliveryAPI()
        delivery_payload = create_delivery_estimate_payload(order)

        for shipment, payload in delivery_payload:
            result = api.estimate_delivery_time(payload)
            data = {}

            if result.get("status", "").lower() == "success":
                eta = result.get("data", {}).get("eta")
                data["eta"] = eta
            else:
                logger.warning(f"Failed to get ETA for shipment [{shipment.id}]: {result}")
                data["eta"] = None  # Or default value, e.g., "Unknown"
 
            # Append estimated delivery time for shipment
            delivery_estimates.append((shipment, data))

        return delivery_estimates
    
    except Exception as e:
        logger.error(f"Error getting delivery estimate for order: [{order}]\nerror: {str(e)}")
        raise ValidationError(f"Error getting delivery estimate: {str(e)}")


def register_webhook_view():
    """Function to register horal webhook on FEZ Delivery platform"""
    try:
        api = FEZDeliveryAPI()
        result = api.register_webhook()
        horal_webhook = settings.HORAL_FEZ_WEBHOOK.strip()

        registered_webhook = None
        is_active = False

        if result.get("status", "").lower() == "success":
            data = result.get("data")
            registered_webhook = data.get("webhook")
            webhook_details = data.get("webhooks", [])

            if webhook_details and isinstance(webhook_details, list):
                is_active = bool(webhook_details[0].get("is_active", 0))
            
        else:
            logger.warning(f"Failed to register webhook url: {result}")
        
        # Compare to ensure proper webhook was registered
        if (
            registered_webhook 
            and horal_webhook 
            and registered_webhook.strip() == horal_webhook
            and is_active
        ):
            return "Webhook registered successfully"
        else:
            logger.warning(f"Webhook mismatch or inactive registration")
            return "Webhook mismatch"
    
    except Exception as e:
        logger.error(f"Error registering webhook on FEZ platform: {str(e)}")
        raise ValidationError(f"Error registering webhook: {str(e)}")


def save_gigl_webhook_data(decrypted_payload: str):
    """
    Save or update shipment data from decrypted webhook payload
    """
    from orders.models import OrderShipment, GIGL_TO_ORDER_STATUS
    try:
        data = json.loads(decrypted_payload)
    except json.JSONDecodeError:
        logger.error("Invalid JSON payload")
        return
    

    # Identify the order item the data belong to
    waybill = data.get("Waybill")
    if not waybill:
        raise ValueError("Webhook payload missing Waybill")
    
    # Try to get the order item
    try:
        order_shipment= OrderShipment.objects.get(tracking_number=waybill)
    except OrderShipment.DoesNotExist:
        logger.warning(f"OrderShipment with tracking number {waybill} does not exist")
        return
    
    # Map GIGL status to OrderItem status
    gigl_status_code = data.get("StatusCode")
    order_status = GIGL_TO_ORDER_STATUS.get(gigl_status_code)

    delivery_status = ['MAHD', 'OKC', 'OKT']

    # Create or update shipment
    try:
        shipment, created = GIGLShipment.objects.update_or_create(
            waybill=data.get('Waybill'),
            defaults={
                "order_shipment": order_shipment,
                "sender_address": data.get("SenderAddress", ""),
                "receiver_address": data.get("ReceiverAddress", ""),
                "location": data.get("Location"),
                "status": data.get("Status", ""),
                "status_code": data.get("StatusCode"),
            }
        )
    except Exception as e:
        logger.error(f"Failed to update GIGLShipment for waybill {waybill}: {str(e)}")
        return

    # update order item status if mapped
    if gigl_status_code and order_shipment.status != order_status:
        order_shipment.status = order_status
        if gigl_status_code in delivery_status:
            order_shipment.delivered_at = now()
            for item in order_shipment.items.all():
                item.delivered_at = now()
                item.save(update_fields=["delivered_at"])
        order_shipment.save(update_fields=["status", "delivered_at"])
        logger.info(f"OrderItem {order_shipment.id} status updated to {order_status}")
        

    return shipment
