# logistics/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .gigl_api import GIGLogisticsAPI
from .models import GIGLWebhookCredentials
from orders.models import OrderItem
from users.authentication import CookieTokenAuthentication
from rest_framework.permissions import IsAuthenticated
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from .utils import decrypt_webhook_data, save_gigl_webhook_data
import json


class TrackShipmentView(APIView):
    """Track shipment status by waybill"""
    permission_classes = [IsAuthenticated]
    authentication_classes = [CookieTokenAuthentication]

    def get(self, request, waybill):
        api = GIGLogisticsAPI()
        result = api.track_shipment(waybill)
        if "error" in result:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
        return Response(result, status=status.HTTP_200_OK)


@csrf_exempt
def gigl_webhook(request):
    if request.method != "POST":
        return JsonResponse({
            "error": "Invalid method"
        }, status=405)

    try:
        # The encrypted payload is sent as raw POST body
        encrypted_data = request.body.decode('utf8')

        # Get secret
        webhook_s = GIGLWebhookCredentials.objects.first()

        if not webhook_s:
            return JsonResponse({"error": "Webhook secret not found"}, status=500)

        # Decrypt
        decrypted_json_str = decrypt_webhook_data(encrypted_data, webhook_s.secret)

        # Check the authenticity of the payload
        data = json.loads(decrypted_json_str)

        # Normalize values for comparison
        db_user_id = str(webhook_s.user_id)  # Convert UUID object to string
        payload_user_id = str(data.get("UserId")).strip()  # Strip whitespace
        db_channel_code = str(webhook_s.channel_code).strip()
        payload_channel_code = str(data.get("ChannelCode")).strip()

        if payload_user_id != db_user_id or payload_channel_code != db_channel_code:
            return JsonResponse({
                "error": "Invalid request payload"
            }, status=405)
        
        # Save GIGL webhook data
        save_gigl_webhook_data(decrypted_json_str)

        return JsonResponse({
            "status": "received",
            "message": "Webhook received successfully"
        }, status=200)
    except Exception as e:
        return JsonResponse({
            "error": str(e)
        }, status=400)
