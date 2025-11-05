# logistics/views.py
from rest_framework.views import APIView
from rest_framework import status
from orders.models import FEZ_STATUS_MAP, OrderShipment, Order
from products.utils import BaseResponseMixin
from users.authentication import CookieTokenAuthentication
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from .utils  import (
    get_single_order_details, search_shipment_with_waybill,
    track_shipment_by_order_number, track_a_single_order_statuses
)
import json, logging

logger = logging.getLogger(__name__)


class TrackSingleShipmentView(APIView, BaseResponseMixin):
    """Class to allow user to track a single shipment using fez order id"""
    permission_classes = [IsAuthenticated]
    authentication_classes = [CookieTokenAuthentication]

    def get(self, request, fez_order_id):
        """Get method to track a single order"""
        try:
            if not fez_order_id:
                return self.get_response(
                    status.HTTP_400_BAD_REQUEST,
                    "You must provide fez order id to track the shipment status"
                )
            try:
                shipment = OrderShipment.objects.get(fez_order_id=fez_order_id)
            except OrderShipment.DoesNotExist:
                logger.error(f"Shipment with the provider fez order id: [{fez_order_id}] not found")
                return self.get_response(
                    status.HTTP_404_NOT_FOUND,
                    "Shipment with the provided fez order id not found"
                )
            
            result = track_shipment_by_order_number(fez_order_id)

            if not result:
                logger.error(f"FEZ API returned no data for order id [{fez_order_id}]")
                return self.get_response(
                    status.HTTP_502_BAD_GATEWAY,
                    "Unable to fetch shipment status from provider. Try again later."
                )

            return self.get_response(
                status.HTTP_200_OK,
                result
            )
        except Exception as e:
            logger.error(f"Error tracking a single shipment [{fez_order_id}]: {str(e)}")
            import traceback
            return self.get_response(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                f"Error while tracking the shipment status: {str(e)} {traceback.format_exc()}"
            )


class TrackOrderShipmentsView(APIView, BaseResponseMixin):
    """Class to allow user to track all shipment related to a single order"""
    permission_classes = [IsAuthenticated]
    authentication_classes = [CookieTokenAuthentication]

    def post(self, request, order_id):
        """Post method to track a single order shipment statuses"""
        try:
            if not order_id:
                return self.get_response(
                    status.HTTP_400_BAD_REQUEST,
                    "You must provide order id to track the shipment status"
                )
            try:
                order = Order.objects.get(id=order_id)
            except Order.DoesNotExist:
                logger.error(f"Order with the provided order id: [{order_id}] not found")
                return self.get_response(
                    status.HTTP_404_NOT_FOUND,
                    "Order with the provided order id not found"
                )
            
            result = track_a_single_order_statuses(order)

            if not result:
                logger.error(f"FEZ API returned no data for order id [{order_id}]")
                return self.get_response(
                    status.HTTP_502_BAD_GATEWAY,
                    "Unable to fetch shipment status from provider. Try again later."
                )

            return self.get_response(
                status.HTTP_200_OK,
                result
            )
        except Exception as e:
            logger.error(f"Error retrieving shipment statuses for a single order [{order_id}]: {str(e)}")
            return self.get_response(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                f"Error while retrieving the shipment status: {str(e)}"
            )


class SingleShipmentView(APIView, BaseResponseMixin):
    """Class to allow Admin to view single order (shipment) details"""
    permission_classes = [IsAdminUser]
    authentication_classes = [CookieTokenAuthentication]

    def get(self, request, fez_order_id):
        """Get method to retrieve a single shipment details"""
        try:
            if not fez_order_id:
                return self.get_response(
                    status.HTTP_400_BAD_REQUEST,
                    "You must provide fez order id to view the shipment details"
                )
            try:
                shipment = OrderShipment.objects.get(fez_order_id=fez_order_id)
            except OrderShipment.DoesNotExist:
                logger.error(f"Shipment with the provider fez order id: [{fez_order_id}] not found")
                return self.get_response(
                    status.HTTP_404_NOT_FOUND,
                    "Shipment with the provided fez order id not found"
                )
            
            result = get_single_order_details(fez_order_id)

            if not result:
                logger.error(f"FEZ API returned no data for order id [{fez_order_id}]")
                return self.get_response(
                    status.HTTP_502_BAD_GATEWAY,
                    "Unable to fetch shipment details from provider. Try again later."
                )

            return self.get_response(
                status.HTTP_200_OK,
                result
            )
        except Exception as e:
            logger.error(f"Error retrieving a single shipment [{fez_order_id}]: {str(e)}")
            return self.get_response(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                f"Error while retrieving the shipment details: {str(e)}"
            )
        

class SearchShipmentView(APIView, BaseResponseMixin):
    """Class to allow admin to search shipment by waybill number"""
    permission_classes = [IsAdminUser]
    authentication_classes = [CookieTokenAuthentication]

    def get(self, request, waybill_number):
        """Get method to retrieve a single shipment status using waybill number"""
        try:
            if not waybill_number:
                return self.get_response(
                    status.HTTP_400_BAD_REQUEST,
                    "You must provide waybill number to view the shipment status"
                )
            try:
                shipment = OrderShipment.objects.get(waybill_number=waybill_number)
            except OrderShipment.DoesNotExist:
                logger.error(f"Shipment with this waybill number: [{waybill_number}] not found")
                return self.get_response(
                    status.HTTP_404_NOT_FOUND,
                    "Shipment with the provided waybill number not found"
                )
            
            result = search_shipment_with_waybill(waybill_number)

            if not result:
                logger.error(f"FEZ API returned no shipment data for waybill number [{waybill_number}]")
                return self.get_response(
                    status.HTTP_502_BAD_GATEWAY,
                    "Unable to fetch shipment status from provider. Try again later."
                )

            return self.get_response(
                status.HTTP_200_OK,
                result
            )
        except Exception as e:
            logger.error(f"Error retrieving a single shipment status for waybill [{waybill_number}]: {str(e)}")
            return self.get_response(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                f"Error while retrieving the shipment status: {str(e)}"
            )


@csrf_exempt
def fez_webhook(request):
    """FEZ Delivery webhook for updating shipment status"""
    try:
        if request.method != "POST":
            return JsonResponse({"error": "Invalid method"}, status=405)

        # Parse JSON body
        try:
            payload = json.loads(request.body.decode("utf-8"))
        except Exception:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        order_num = str(payload.get("orderNumber", "")).strip()
        delivery_status = str(payload.get("status", "")).strip()

        # Validate order number
        if not order_num:
            return JsonResponse({"error": "Missing order number"}, status=400)

        # Map logistics status to internal status
        internal_status = FEZ_STATUS_MAP.get(delivery_status)

        if internal_status:
            try:
                shipment = OrderShipment.objects.get(fez_order_id=order_num)
            except OrderShipment.DoesNotExist:
                logger.warning(f"Webhook received unknown orderNumber: [{order_num}]")
                return JsonResponse({"error": "Invalid order number"}, status=400)

            # Update status
            shipment.status = internal_status
            shipment.save(update_fields=["status"])
            logger.info(f"Shipment {shipment.id} updated to '{internal_status}' via webhook.")
        else:
            # Unknown logistic status — log and ignore, still return 200 so FEZ doesn't retry forever
            logger.warning(f"Unknown FEZ status received: '{delivery_status}' for {order_num}")

        return JsonResponse({"status": "OK"}, status=200)

    except Exception as e:
        logger.error(f"Error processing FEZ Delivery Webhook: {str(e)}")
        return JsonResponse({"error": "Server error"}, status=500)
