from django.conf import settings
from .gigl_api import GIGLogisticsAPI
from sellers.models import SellerKYC, SellerKYCAddress
from decimal import Decimal
from typing import Optional
import googlemaps, math
from collections import defaultdict
from django.utils.timezone import now
from products.models import ProductIndex
from .models import Station, GIGLWebhookCredentials, GIGLShipment, GIGLExperienceCentre
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
    # Find seller's KYC record
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
        print(f"Logistics product variant: {logistics}")
    except ObjectDoesNotExist as e:
        logger.warning(f"Logistics entry not found for variant {item.variant.id}: {str(e)}")
        try:
            logistics = Logistics.objects.get(object_id=item.variant.object_id)
            print(f"Logistics product id: {logistics}")
        except ObjectDoesNotExist as e:
            logger.warning(f"Logistics entry not found for product {item.variant.object_id}: {str(e)}")
            logistics = None  # or raise a validation error
    
    quantity = getattr(item, "quantity", 1)

    print(f"Logistics: {logistics}")
    if not logistics:
        return default_kg * quantity
    
    weight_value = getattr(logistics, "weight_measurement", None)
    weight_unit = getattr(logistics, "total_weight", None)
    print(f"weight measurement: {weight_value}\ntotal weight: {weight_unit}")

    if not weight_value or not weight_unit:
        weight = default_kg * quantity

        print(f"Weight after calculation: {weight}")
        return weight
    
    weight_unit = str(weight_unit).upper()

    # Conversion factors to KG
    conversion_to_kg = {
        "G": 0.001,
    }

    if weight_unit != "KG":
        factor = conversion_to_kg.get(weight_unit)
        total_weight_kg = float(weight_value) * quantity * factor
    else:
        # Multiply by quantity first, then convert to kg
        total_weight_kg = float(weight_value) * quantity
    print(f"Total weight after conversion: {total_weight_kg}")

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


def get_nearest_station_id(state_name: str) -> Optional[int]:
    """
    Return the first station_id for a given state.
    If not found, use predefined fallback states.
    Raises ValidationError if no station is found.
    """
    
    fallback_states = {
        "kebbi": "sokoto",
        "yobe": "bauchi"
    }
    
    state_lookup = state_name.lower()

    # Special handling for Abuja / Federal Capital Territory
    if state_lookup in ["abuja", "fct", "federal capital territory"]:
        station = Station.objects.filter(
            Q(state_name__iexact="abuja") | Q(state_name__iexact="federal capital territory")
        ).first()
    else:
        station = Station.objects.filter(state_name__iexact=state_lookup).first()
        if not station and state_lookup in fallback_states:
            station = Station.objects.filter(state_name__iexact=fallback_states[state_lookup]).first()
    
    if not station:
        raise ValueError(f"No station found for state '{state_name}' and so cannot generate shipping cost")
    
    return station.station_id
    

def build_gigl_payload_for_item(
    *,
    sender_name: str,
    sender_phone_num: str,
    sender_station_id: int,
    inputted_sender_address: str,
    sender_locality: str,
    receiver_station_id: int,
    sender_address: str,
    receiver_name: str,
    receiver_phone_num: str,
    receiver_address: str,
    inputted_receiver_address: str,
    s_lat: str,
    s_lng: str,
    r_lat: str,
    r_lng: str,
    description: str,
    weight_kg: float,
    item_name: str,
    value: Decimal,
    quantity: int,
    vehicle_type: str = "BIKE",
    include_cod: bool = False,
    cod_amount: Optional[Decimal] = None,
) -> Dict[str, Any]:
    """
    Build a GIGL payload for a (possibly grouped) 'single package' using the exact
    fields provided by the caller. Returns a dict suitable for:
      - POST api/ThirdParty/price
      - POST api/ThirdParty/captureshipment
    """

    payload = {
        "PreShipmentMobileId": 0,

        # Sender / Receiver (flat fields)
        "SenderName": sender_name,
        "SenderPhoneNumber": sender_phone_num,
        "SenderStationId": sender_station_id,
        "InputtedSenderAddress": inputted_sender_address,
        "SenderLocality": sender_locality,
        "ReceiverStationId": receiver_station_id,
        "SenderAddress": sender_address,

        "ReceiverName": receiver_name,
        "ReceiverPhoneNumber": receiver_phone_num,
        "ReceiverAddress": receiver_address,
        "InputtedReceiverAddress": inputted_receiver_address,

        # Locations
        "SenderLocation": {
            "Latitude": s_lat,
            "Longitude": s_lng,
            "FormattedAddress": "",
            "Name": "",
            "LGA": sender_locality,
        },
        "ReceiverLocation": {
            "Latitude": r_lat,
            "Longitude": r_lng,
            "FormattedAddress": "",
            "Name": "",
            "LGA": "",  
        },

        # Single line describing the whole package (can be a grouped package)
        "PreShipmentItems": [
            {
                "PreShipmentItemMobileId": 0,
                "Description": description,
                "Weight": weight_kg,
                "Weight2": 0,
                "ItemType": "Normal",
                "ShipmentType": 1,
                "ItemName": item_name,
                "EstimatedPrice": 0,
                "Value": str(value),        # matches your previous usage (_safe_str)
                "ImageUrl": "",
                "Quantity": quantity,
                "SerialNumber": 0,
                "IsVolumetric": False,
                "Length": None,
                "Width": None,
                "Height": None,
                "PreShipmentMobileId": 0,
                "CalculatedPrice": None,
                "SpecialPackageId": None,
                "IsCancelled": False,
                "PictureName": "",
                "PictureDate": None,
                "WeightRange": "0",
            }
        ],

        "VehicleType": vehicle_type,
        "IsBatchPickUp": False,
        "WaybillImage": "",
        "WaybillImageFormat": "",
        "DestinationServiceCenterId": 0,
        "DestinationServiceCentreId": 0,

        # COD
        "IsCashOnDelivery": bool(include_cod),
        "CashOnDeliveryAmount": float(cod_amount or 0),
    }

    return payload


def group_order_items_by_seller(order):
    """
    Function to group order items by seller to lessen shipping
    cost for buyers purchasing from a single seller
    """
    seller_orders = defaultdict(lambda: {"items": [], "station": None})

    for item in order.order_items.all():
        shop = item.variant.shop
        seller = SellerKYC.objects.get(user=shop.owner.user)
        seller_kyc = SellerKYCAddress.objects.get(id=seller.address.id)
        
        # Extract weight
        item_weight = _extract_weight_kg(item)
        print(f"Weight returned: {item_weight}")

        # Get seller address and nearest station
        # seller_address, seller_state = _seller_full_address(seller_kyc)
        # seller_lat, seller_lng = get_coordinates(seller_address)
        # seller_station_id = get_nearest_station_id(seller_state)
        # station = Station.objects.get(station_id=seller_station_id)
        
        # Store order info
        seller_orders[seller]["items"].append(item)
        # seller_orders[seller]["station"] = station.address
        seller_orders[seller]["weight"] += item_weight
        print(f"Weight saved for seller: {seller_orders[seller]["weight"]}")
    
    
    return seller_orders


def create_gigl_shipment_for_shipment(order_id):
    """
    Create shipments in GIGL for a single order.
    Returns True if all shipments were successfully created and updated, else False.
    """
    from orders.models import Order, OrderShipment
    api = GIGLogisticsAPI()

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
            # Skip if shipment already has a tracking number
            if not shipment.tracking_number:
                result = api.create_shipment(payload)
                waybill = result.get("waybill")

                if waybill:
                    shipment.tracking_number = waybill
                    shipment.status = OrderShipment.Status.SHIPMENT_INITIATED
                    shipment.save(update_fields=["tracking_number", "status"])
                else:
                    all_success = False
            else:
                logger.info(f"Shipment {shipment.id} already has tracking number {shipment.tracking_number}, skipping creation.")   
        except Exception as e:
            logger.warning(f"Error creating shipment {shipment.id}: {e}")
            all_success = False

    return all_success



def create_shipment_payload(order):
    """
    Create shipment payloads grouped by seller (not per item).
    Returns a list of payload dicts (one per seller/shipment).
    """
    shipments = []

    for shipment in order.shipments.select_related("order__user", "seller"):
        # Build payload for seller shipment
        seller_kyc = get_seller_kyc(shipment.seller)

        if not seller_kyc:
            raise ValueError(f"Seller KYC not found for seller {shipment.seller.user}")
        
        # Compute totals
        item_total_price = shipment.total_price
        total_weight = shipment.total_weight
        total_quantity = shipment.quantity

        # Build seller address string
        seller_address, seller_state = _seller_full_address(seller_kyc)
        seller_lat, seller_lng = get_coordinates(seller_address)
        seller_station_id = get_nearest_station_id(seller_state)

        # Build buyer address string
        buyer_address, buyer_state = _buyer_full_address(order)
        buyer_lat, buyer_lng = get_coordinates(buyer_address)
        buyer_station_id = get_nearest_station_id(buyer_state)

        # # Save seller and buyer station id
        # shipment.seller_station = seller_station_id
        # shipment.buyer_station = buyer_station_id
        # shipment.save(update_fields=["seller_station", "buyer_station"])

        titles = []

        for t in shipment.items.all():
            product = ProductIndex.objects.get(id=t.variant.object_id)
            titles.append(product.title)


        description = ", ".join(titles)
        title = f"Shipment for {order.user.full_name} ({len(titles)} items)"


        # Build shipment payload
        payload = build_gigl_payload_for_item(
            sender_name=f"{seller_kyc.first_name} {seller_kyc.last_name}",
            sender_phone_num=_safe_str(seller_kyc.mobile),
            sender_station_id=seller_station_id,
            inputted_sender_address=seller_address,
            sender_locality=_safe_str(seller_kyc.lga),
            receiver_station_id=buyer_station_id,
            sender_address=seller_address,
            receiver_name=order.user.full_name,
            receiver_phone_num=_safe_str(order.phone_number),
            receiver_address=buyer_address,
            inputted_receiver_address=buyer_address,
            s_lat=_safe_str(seller_lat),
            s_lng=_safe_str(seller_lng),
            r_lat=_safe_str(buyer_lat),
            r_lng=_safe_str(buyer_lng),
            description=description,
            weight_kg=_safe_str(total_weight),
            item_name=title,
            value=item_total_price,
            quantity=total_quantity,
        )
        shipments.append((shipment, payload))
    
    return shipments


def get_experience_centers(state: str) -> str:
    """
    Function that accepts a sellers states
    Returns all experience centers associated to the state
    """
    centers = GIGLExperienceCentre.objects.filter(state=state)
    return [center.address for center in centers]    


def calculate_shipping_for_order(order):
    """
    Calculate and update shipping cost for every item in an order.
    Returns (items_shipping_total, updated_items_list)
    """
    api = GIGLogisticsAPI()
    shipping_total = Decimal("0.00")
    updated_items = []

    # Create grouped shipment payloads
    try:
        shipment_payloads = create_shipment_payload(order)
    except Exception as e:
        logger.error(f"Error creating shipment payloads for order {order.id}: {str(e)}\n{str(traceback.format_exc())}")
        raise ValidationError(f"Error creating shipment payload for order: {str(e)}")

    for shipment, payload in shipment_payloads:
        result = api.get_price(payload)

        try:
            price = Decimal(str(result.get("object", {}).get("deliveryPrice", 0)))
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


def sync_stations_from_gigl():
    """
    Fetch stations from GIGL API and save/update
    them in the Station table.
    """
    api = GIGLogisticsAPI()
    response = api.get_stations()

    if not response or "object" not in response:
        return
    
    for station_data in response["object"]:
        # Parse station info
        station_id = station_data.get("stationId")
        station_name = station_data.get("stationName")
        station_code = station_data.get("stationCode")
        state_id = station_data.get("stateId")
        state_name = station_data.get("stateName")

        # Update or create station in DB
        Station.objects.update_or_create(
            station_id=station_id,
            defaults={
                "station_name": state_name,
                "station_code": station_code,
                "state_id": state_id,
                "state_name": state_name
            }
        )


def sync_station_addresses(station_addresses: list):
    """
    station_addresses: list of dicts, e.g.,
    [{"station_name": "ABA", "state_name": "ABIA", "address": "Some address here"}, ...]
    """

    for data in station_addresses:
        station_name = data.get("station_name")
        state_name = data.get("state_name")
        address = data.get("address")

        if not state_name or not state_name or not address:
            continue

        GIGLExperienceCentre.objects.create(
            address=address,
            state=state_name,
            centre_name=station_name
        )
    logger.info(f"Done populating {GIGLExperienceCentre.objects.all().count()} Experience centers")


def decrypt_webhook_data(encrypted_data: str, secret: str) -> bytes:
    """
    Decrypt AES-256-CBC encrypted webhook payload.
    Returns raw bytes (not UTF-8 decoded).
    """
    try:
        encrypted_bytes = base64.b64decode(encrypted_data)
    except Exception as e:
        raise ValueError(f"Base64 decode error: {e}")

    if len(encrypted_bytes) < 32:
        raise ValueError("Payload too short to contain salt + IV.")

    salt = encrypted_bytes[:16]
    iv = encrypted_bytes[16:32]
    ciphertext = encrypted_bytes[32:]

    if len(ciphertext) % 16 != 0:
        raise ValueError(f"Ciphertext length {len(ciphertext)} is not a multiple of 16. Payload likely corrupted.")

    # Derive key
    key = hashlib.pbkdf2_hmac('sha1', secret.encode(), salt, 10000, dklen=32)

    # Decrypt
    cipher = AES.new(key, AES.MODE_CBC, iv)
    decrypted = cipher.decrypt(ciphertext)

    # Remove PKCS7 padding
    pad_len = decrypted[-1]
    if pad_len < 1 or pad_len > 16:
        raise ValueError("Invalid padding. Wrong key/secret or corrupted payload.")
    decrypted = decrypted[:-pad_len]

    return decrypted.decode('utf8')



def register_gigl_webhook_on_table():
    """
    Function to register GIGL webhook
    And save the returned secret on table for future decoding
    of webhook payload
    """
    api = GIGLogisticsAPI()
    response = api.register_webhook()

    if "userId" in response and "secret" in response:
        GIGLWebhookCredentials.objects.update_or_create(
            user_id=response["userId"],
            defaults={
                "channel_code": response["channelCode"],
                "secret": response["secret"],
                "webhook_url": response["url"]
            }
        )
        return True
    return False


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
