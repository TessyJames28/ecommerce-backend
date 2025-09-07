from django.conf import settings 
import requests, hmac, hashlib, json
from django.db import transaction
from rest_framework.permissions import IsAuthenticated
from django.http import JsonResponse
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from .models import PaystackTransaction
from orders.models import Order, OrderItem
from rest_framework.views import APIView
from django.utils.timezone import now
from carts.models import CartItem
from .utils import trigger_refund, update_order_status
from orders.serializers import OrderSerializer
from products.utils import update_quantity, IsAdminOrSuperuser
from django.utils.decorators import method_decorator
from rest_framework.exceptions import ValidationError
from users.authentication import CookieTokenAuthentication
import uuid, os
from wallet.models import Payout


# Create your views here.
@method_decorator(csrf_exempt, name='dispatch')
class InitializeTransaction(APIView):
    """
    class to initialize order payment on paystack
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [CookieTokenAuthentication]

    def post(self, request):
        """Function to handle payment initialization on paystack"""
        email = request.data.get("email")
        order_id = request.data.get('order_id') # passed from frontend
        platform = request.data.get('platform')

        if platform not in ['web', 'mobile']:
            return JsonResponse({
                "status": "error",
                "status_code": status.HTTP_400_BAD_REQUEST,
                "message": "Invalid platform specified"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if platform == 'mobile':
            redirect_url = settings.MOBILE_REDIRECT_URL
        elif platform == 'web':
            redirect_url = settings.WEB_REDIRECT_URL

        try:
            order = Order.objects.get(id=order_id, user__email=email)
        except Order.DoesNotExist:
            return JsonResponse({
                "status": "error",
                "status_code": status.HTTP_404_NOT_FOUND,
                "message": "Order not found"
            }, status=status.HTTP_404_NOT_FOUND)
                
        # Check for complete location fields
        required_fields = ['country', 'state', 'local_govt', 'phone_number', 'street_address', 'landmark']
        missing_fields = [field for field in required_fields if not getattr(order, field, None)]

        if missing_fields:
            raise ValidationError(
                f"Please complete your shipping address information. Missing fields: {', '.join(missing_fields)}"
            )
        
        
        amount = int(order.total_amount * 100) # convert amount to kobo

        # --- Check if a transaction already exists for this order ---
        existing_txn = PaystackTransaction.objects.filter(order=order).first()
        if existing_txn:
            if existing_txn.status == PaystackTransaction.StatusChoices.PENDING:
                # Return existing pending transaction
                return Response({
                    "status": "success",
                    "message": "Transaction already initialized",
                    "data": {
                        "authorization_url": existing_txn.authorization_url,
                        "access_code": existing_txn.access_code,
                        "reference": existing_txn.reference,
                    }
                })
            else:
                # If already completed or failed, optionally raise an error
                return JsonResponse({
                    "status": "error",
                    "status_code": status.HTTP_400_BAD_REQUEST,
                    "message": f"Transaction already {existing_txn.status.lower()} for this order"
                }, status=status.HTTP_400_BAD_REQUEST)
        else:
            # Generate new reference
            reference = str(uuid.uuid4())
            
        # Step 1: Initialize payment with Paystack
        url = "https://api.paystack.co/transaction/initialize"
        headers = {
            "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
            "Content-Type": "application/json"
        }

        data = {
            "email": email,
            "amount": amount,
            "reference": reference,
            "callback_url": redirect_url,
            "metadata": {
                "order_id": str(order.id)
            }
        }

        response = requests.post(url, headers=headers, json=data)
        res_data = response.json()

        if not res_data.get("status"):
            return JsonResponse({
                "status": "error",
                "status_code": status.HTTP_400_BAD_REQUEST,
                "message": "Paystack error"
            })
        
        # Save new transaction
        existing_txn = PaystackTransaction.objects.create(
            reference=reference,
            user=request.user,
            email=email,
            amount=amount,
            order=order,
            status=PaystackTransaction.StatusChoices.PENDING,
            access_code=res_data["data"]["access_code"],
            authorization_url=res_data["data"]["authorization_url"]
        )

        return Response(res_data)
    

@method_decorator(csrf_exempt, name='dispatch')
class VerifyTransaction(APIView):
    """
    Class to verify paystack transaction if successful
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [CookieTokenAuthentication]

    def get(self, request, reference):
        """Method to verify user payment by admin"""
        url = f"{settings.PAYSTACK_VERIFY_URL}/{reference}"
        headers = {
            "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"
        }

        response = requests.get(url, headers=headers)
        res_data = response.json()

        try:
            tx = PaystackTransaction.objects.get(reference=reference)
        except PaystackTransaction.DoesNotExist:
            return JsonResponse({
                "status": "error",
                "status_code": status.HTTP_404_NOT_FOUND,
                "message": "Transaction not found"
            }, status=status.HTTP_404_NOT_FOUND)
        
        if res_data['data']['status'] == "success":
            # If already marked successful, skip update
            if tx.status != PaystackTransaction.StatusChoices.SUCCESS:
                tx.status = PaystackTransaction.StatusChoices.SUCCESS
                tx.paid_at = res_data['data']['paid_at']
                tx.gateway_response = res_data['data'].get('gateway_response')
                tx.save()

                # Check and update order if necessary
                if tx.order and tx.order.status != Order.Status.PAID:
                    update_order_status(tx.order, Order.Status.PAID, request.user)

            model_data = Order.objects.get(id=tx.order.id)
            serializer = OrderSerializer(model_data)

            return JsonResponse({
                "status": "success",
                "message": "Payment successful",
                "order_data": serializer.data,
                "payment_data": res_data['data']
            })
        else:
            tx.status = PaystackTransaction.StatusChoices.FAILED
            tx.save()
            return JsonResponse({
                "status": "failed",
                "message": "Payment verification failed",
                "data": res_data['data']
            })
    

@csrf_exempt
def transaction_webhook(request):
    """
    Setup a webhook to listen to transaction events
    """
    secret = settings.PAYSTACK_SECRET_KEY.encode()
    signature = request.headers.get('x-paystack-signature')
    body = request.body
    expected_signature = hmac.new(secret, body, hashlib.sha512).hexdigest()

    if signature != expected_signature:
        return JsonResponse({
            "status": "error",
            "status_code": status.HTTP_400_BAD_REQUEST,
            "message": "Invalid signature"
        })
    
    event = json.loads(body)
    data = event.get('data', {})
    event_type = event['event']

    if not "transfer" in event_type:
        reference = data.get('reference') or data.get("transaction_reference")
        if not reference:
            print(f"[Webhook] Missing reference in payload: {json.dumps(event, indent=2)}")
            return JsonResponse({
                "status": "error",
                "status_code": 400,
                "message": "Missing transaction reference"
            }, status=400)

        try:
            tx = PaystackTransaction.objects.get(reference=reference)
            order = tx.order
        except PaystackTransaction.DoesNotExist:
            return JsonResponse({
                "status": "error",
                "status_code": status.HTTP_404_NOT_FOUND,
                "message": "Transaction not found"
            })
    else:
        reference = data.get('reference')

    if event_type == 'charge.success':
        tx.status = PaystackTransaction.StatusChoices.SUCCESS
        tx.paid_at = data.get('paid_at')
        tx.gateway_response = data.get('gateway_response')
        tx.save()

        if order and order.status != Order.Status.PAID:
            try:
                with transaction.atomic():
                    for item in order.order_items.all():
                        variant = item.variant
                        variant.reserved_quantity -= item.quantity
                        variant.save()
                        update_quantity(variant.product)
                    CartItem.objects.filter(cart__user=order.user).delete()
                    update_order_status(order, Order.Status.PAID)
            except Exception as e:
                raise
                # pass
    elif event_type == "charge.failed":
        tx.status = PaystackTransaction.StatusChoices.FAILED
        tx.save()

        if order:
            try:
                with transaction.atomic():
                    for item in order.order_items.all():
                        variant = item.variant
                        variant.reserved_squantity -= item.quantity
                        variant.stock_quantity += item.quantity
                        variant.save()
                        update_quantity(variant.product)
                    update_order_status(order, Order.Status.FAILED)
            except Exception:
                pass

    elif event_type in ["transfer.success", "transfer.failed"]:
        payout = Payout.objects.filter(reference_id=reference).first()

        if payout:
            if event_type == "transfer.success":
                print(f"Event type: {event_type}")
                payout.status = Payout.StatusChoices.SUCCESS
                payout.save(update_fields=["status"])
            elif event_type == "transfer.failed":
                from .tasks import retry_payout_transfer
                retry_payout_transfer.apply_async(args=[payout.id], countdown=600)
                   
    return JsonResponse({
        "status": "success",
        "status_code": status.HTTP_200_OK
    })


class RetryRefundView(APIView):
    """
    class to handle refund retry for failed refund cases
    """
    permission_classes = [IsAdminOrSuperuser]
    authentication_classes = [CookieTokenAuthentication]

    def post(self, request):
        """
        Post method for admin and staff to retry refund
        When refund failed from paystack end
        """
        reference = request.data.get("reference")
        order_item = request.data.get("order_item")

        if not reference:
            return Response({
                "status": "error",
                "status_code": status.HTTP_400_BAD_REQUEST,
                "message": "reference is required"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not order_item:
            return Response({
                "status": "error",
                "status_code": status.HTTP_400_BAD_REQUEST,
                "message": "order item is required to process partial refund"
            }, status=status.HTTP_400_BAD_REQUEST)

        
        try:
            tx = PaystackTransaction.objects.get(reference=reference)
        except PaystackTransaction.DoesNotExist:
            return Response({
                "status": "error",
                "status_code": status.HTTP_404_NOT_FOUND,
                "message": "Transaction not found"
            }, status=status.HTTP_404_NOT_FOUND)
        
        if tx.refund_successful:
            return Response({
                "status": "success",
                "status_code": status.HTTP_200_OK,
                "message": "Refund already successful"
            }, status=status.HTTP_200_OK)
        
        # Get order item for amount
        try:
            order_item = OrderItem.objects.get(id=order_item, order=tx.order.id)
        except OrderItem.DoesNotExist:
            return Response({
                "status": "error",
                "status_code": status.HTTP_400_BAD_REQUEST,
                "message": "Order with this item not found"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get amount
        amount = order_item.total_price
        
        result = trigger_refund(reference, amount=amount, retry=True)
        # Add just before or after calling trigger_refund

        if result.get("status"):
            return Response({
                "status": "success",
                "status_code": status.HTTP_200_OK,
                "message": "Refund retried and successful"
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                "status": "error",
                "status_code": status.HTTP_400_BAD_REQUEST,
                "message": result.get("message", "Refund retry failed")  # extract Paystack error if present
            }, status=status.HTTP_400_BAD_REQUEST)
        
