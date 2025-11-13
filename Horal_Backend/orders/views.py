from django.shortcuts import get_object_or_404
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db import transaction
from rest_framework.exceptions import ValidationError
from products.utils import IsSuperAdminPermission
from payment.views import trigger_refund
from payment.models import PaystackTransaction, OrderStatusLog
from payment.utils import update_order_status
from decimal import Decimal
from users.models import CustomUser
from .discounts import apply_coupon_discount
from .utils import approve_return, create_shipments_for_order, get_consistent_checkout_payload
from .models import Order, OrderItem, OrderShipment
from .serializers import (
    OrderReturnRequest, OrderSerializer,
    OrderReturnRequestSerializer, OrderShipmentSerializer,
    OrderWithShipmentSerializer
)
from carts.models import Cart
from users.authentication import CookieTokenAuthentication
from logistics.utils import calculate_shipping_for_order
from products.utils import BaseResponseMixin, update_quantity
from products.models import ProductVariant
from django.utils.timezone import now
from support.serializers import MessageSerializer
from support.utils import handle_mailgun_attachments, create_message_for_instance
from support.models import Message, SupportAttachment, Tickets
from django.contrib.contenttypes.models import ContentType
from notifications.models import Notification
import re, logging
import traceback

logger = logging.getLogger(__name__)

# Create your views here.

class CheckoutView(GenericAPIView, BaseResponseMixin):
    """Checkout cart and place order (status: pending)"""
    permission_classes = [IsAuthenticated]
    authentication_classes = [CookieTokenAuthentication]
    serializer_class = OrderSerializer

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user, status=Order.Status.PENDING)


    def post(self, request, *args, **kwargs):
        """
        Post method to create an order based on user's cart
        """
        user = request.user
        cart = Cart.objects.filter(user=user).first()

        if not cart or not cart.cart_item.exists():
            return self.get_response(
                status.HTTP_400_BAD_REQUEST,
                "Your cart is empty"
            )
        
        try:
            with transaction.atomic():
                # Instead of getting existing order, recreate the order to allow
                # users to remove item from cart if them choose maybe because of shipping cost
                # WIthout them abandoning the order
                order = Order.objects.filter(user=user, status=Order.Status.PENDING).first()
                if not order:       
                    # If no existing order, continue creating one and calculate total
                    total = cart.total_price
                    address = None
                    if hasattr(user, 'shipping_address'):
                        address = user.shipping_address
                    order, created = Order.objects.update_or_create(
                        user=user,
                        status="pending",
                        defaults={
                            "product_total": total,
                            "total_amount": total,
                            "street_address": address.street_address if address else None,
                            "local_govt": address.local_govt if address else None,
                            "landmark": address.landmark if address else None,
                            "country": address.country if address else None,
                            "state": address.state if address else None,
                            "phone_number": address.phone_number if address else None,
                            "created_at": now()
                        }
                    )
                    update_order_status(order, Order.Status.PENDING, user, force=True)

                # Release stock for existing order items
                for order_item in order.order_items.select_related("variant").all():
                    variant = (
                        ProductVariant.objects.select_for_update()
                        .get(pk=order_item.variant.pk)
                    )
                    variant.reserved_quantity -= order_item.quantity
                    variant.stock_quantity += order_item.quantity
                    variant.save()
                    update_quantity(variant.product)

                # Clear existing order items to resync with cart
                order.order_items.all().delete()

                # Add order items
                for item in cart.cart_item.all():
                    variant = (
                        ProductVariant.objects.select_for_update()
                        .get(pk=item.variant.pk)
                    )

                    # Check if requested quantity can be reserved
                    if item.quantity > variant.stock_quantity:
                        raise ValidationError(
                            f"Only {variant.stock_quantity} items available for {variant}"
                        )
                    # Reserve the stock
                    variant.reserved_quantity += item.quantity
                    variant.stock_quantity -= item.quantity  # Deduct immediately upon reservation
                    variant.save()
                    update_quantity(variant.product)

                    OrderItem.objects.create(
                        order=order,
                        variant=item.variant,
                        quantity=item.quantity,
                        unit_price=item.variant.price_override or item.variant.product.price,
                    )

                #--------------------
                # Create shipment first
                #--------------------
                # Clear old shipments if this a re-checkout
                order.shipments.all().delete()
                shipments = create_shipments_for_order(order)

                #--------------------
                # Calculate shipping
                #--------------------
                has_address = all([order.street_address, order.state, order.local_govt])
                shipping_total, items = (0, [])

                # Only calculate shipping if we have a full address
                if has_address:
                    shipping_total, items = calculate_shipping_for_order(order)
                product_total = sum(
                    i.unit_price * i.quantity for i in order.order_items.all()
                )

                # Calculate Insurance fee
                insurance_fee = 0
                if product_total >= 200000:
                    insurance_fee = product_total * Decimal('0.01')  # 1% of the grand total

                shipping_total += insurance_fee
                grand_total = product_total + shipping_total

                # Save them to DB
                order.product_total = product_total
                order.shipping_total = shipping_total
                order.total_amount = grand_total
                order.save(update_fields=[
                    "product_total", "shipping_total", "total_amount",
                    "discount_applied"
                ])
                if order.discount_applied:
                    apply_coupon_discount(order)

                # Get consistent order payload              
                shipments = get_consistent_checkout_payload(order)

                return self.get_response(
                    status.HTTP_201_CREATED,
                    "Order placed and shipping cost calculated",
                    {
                        "order_id": str(order.id),
                        "user_email": order.user.email,
                        "shipments": shipments,
                        "product_total": str(order.product_total),
                        "shipping_total": str(order.shipping_total),
                        "total_amount": str(order.total_amount),
                        "address": {
                            "street": order.street_address,
                            "local_govt": order.local_govt,
                            "state": order.state,
                            "landmark": order.landmark,
                            "country": order.country,
                            "phone_number": order.phone_number,
                        },
                    },
                )
                
        except ValidationError as e:
            logger.warning(f"Validation error during checkout for user {user.id}: {str(e)}")
            return self.get_response(
                status.HTTP_400_BAD_REQUEST,
                str(e)
            )
        except ValueError as e:
            import traceback
            logger.error(f"Error during checkout for user {user.id}: {str(e)} {traceback.format_exc()}")
            return self.get_response(
                status.HTTP_400_BAD_REQUEST,
                {str(e)}
            )
        
        except Exception as e:
            import traceback
            logger.error(f"Error during checkout for user {user.id}: {str(e)} {traceback.format_exc()}")
            return self.get_response(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                {str(e)}
            )
        

    def put(self, request, *args, **kwargs):
        """Partial updates for user address during checkout"""
        try:
            order = self.get_queryset().first()

            if not order:
                return self.get_response(
                    status.HTTP_404_NOT_FOUND,
                    "No pending order found for address update"
                )
            
            serializer = self.get_serializer(order, data=request.data)
            serializer.is_valid(raise_exception=True)
            serializer.save()

            try:
                shipping_total, items = calculate_shipping_for_order(order)
            except ValueError as e:
                logger.error(f"Error calculating shipping for order {order.id}: {str(e)}\n{traceback.format_exc()}")
                return self.get_response(
                    status.HTTP_500_INTERNAL_SERVER_ERROR,
                    f"Error calculating shipping: {e}"
                )
            except Exception as e:
                logger.error(f"Unexpected error calculating shipping for order {order.id}: {str(e)}\n{traceback.format_exc()}")
                return self.get_response(
                    status.HTTP_400_BAD_REQUEST,
                    "Unexpected error calculating shipping"
                )

            product_total = sum(i.unit_price * i.quantity for i in order.order_items.all())

            # Calculate Insurance fee
            insurance_fee = 0
            if product_total >= 200000:
                insurance_fee = product_total * Decimal('0.01')  # 1% of the grand total

            shipping_total += insurance_fee

            grand_total = product_total + shipping_total
            
            # Save them to DB
            order.product_total = product_total
            order.shipping_total = shipping_total
            order.total_amount = grand_total
            order.save(update_fields=["product_total", "shipping_total", "total_amount"])
            
            if order.discount_applied:
                apply_coupon_discount(order)

            # Get consistent order payload                
            shipments = get_consistent_checkout_payload(order)

            return self.get_response(
                status.HTTP_201_CREATED,
                "Shipping address updated successfully and shipping cost recalculated",
                {
                    "order_id": str(order.id),
                    "user_email": order.user.email,
                    "shipments": shipments,
                    "product_total": str(order.product_total),
                    "shipping_total": str(order.shipping_total),
                    "total_amount": str(order.total_amount),
                    "address": {
                        "street": order.street_address,
                        "local_govt": order.local_govt,
                        "landmark": order.landmark,
                        "state": order.state,
                        "country": order.country,
                        "phone_number": order.phone_number,
                    },
                },
            )
        except ValidationError as e:
            logger.warning(f"Validation error updating address for order {order.id}: {str(e)}")    
            return self.get_response(
                status.HTTP_400_BAD_REQUEST,
                str(e)
            )
        except Exception as e:
            logger.error(f"Error updating address for order {order.id}: {str(e)}")
            return self.get_response(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                str(e)
            )


    def patch(self, request, *args, **kwargs):
        """
        Apply a coupon or discount to the order total (product cost only).
        Example: Deduct 3000 from the product total.
        """
        user = request.user
        order = self.get_queryset().first()
        if not order:
            return self.get_response(
                status.HTTP_404_NOT_FOUND,
                "No pending order found for coupon application"
            )
        
        # Check is the user already has a paid order
        has_previous_order = Order.objects.filter(
            user=user, status='paid'
        ).exists()

        if has_previous_order:
            return self.get_response(
                status.HTTP_400_BAD_REQUEST,
                "Discount only applies to first-time buyers"
            ) 
        
        if order.discount_applied:
            return self.get_response(
                status.HTTP_400_BAD_REQUEST,
                "Discount already applied for this order"
            )
        
        discount_amount = 3000

        try:
            order = apply_coupon_discount(order, discount_amount)
            
            # Get consistent order payload                
            shipments = get_consistent_checkout_payload(order)

            return self.get_response(
                status.HTTP_201_CREATED,
                "Coupon applied successfully to total product amount",
                {
                    "order_id": str(order.id),
                    "user_email": order.user.email,
                    "shipments": shipments,
                    "product_total": str(order.product_total),
                    "purcharse_insurance": str(order.purcharse_insurance),
                    "shipping_total": str(order.shipping_total),
                    "total_amount": str(order.total_amount),
                    "address": {
                        "street": order.street_address,
                        "local_govt": order.local_govt,
                        "state": order.state,
                        "landmark": order.landmark,
                        "country": order.country,
                        "phone_number": order.phone_number,
                    },
                },
            )
        except ValueError as e:
            logger.warning(f"Validation error applying coupon for user {user.id}: {str(e)}")    
            return self.get_response(
                status.HTTP_400_BAD_REQUEST,
                str(e)
            )
        except Exception as e:
            logger.error(f"Error applying coupon for user {user.id}: {str(e)}")
            return self.get_response(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                str(e)
            )


class OrderDeleteView(GenericAPIView):
    """
    class to handle the delete view for order
    and reset reserved quantities
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [CookieTokenAuthentication]

    def delete(self, request, *args, **kwargs):
        order_id = self.kwargs.get('pk')
        order = get_object_or_404(Order, pk=order_id, user=request.user)

        if order.status != Order.Status.PENDING:
            return Response({
                "status": "error",
                "status code": status.HTTP_400_BAD_REQUEST,
                "message": "Only pending orders can be deleted"
            }, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            for item in order.order_items.all():
                variant = item.variant

                # reset the reserved quantity
                variant.reserved_quantity = max(0, variant.reserved_quantity - item.quantity)
                variant.stock_quantity += item.quantity
                variant.save()

                # Recalculate total quantity for the product
                update_quantity(variant.product)

            order.delete()

        return Response({
            "status": "success",
            "status code": status.HTTP_204_NO_CONTENT,
            "message": "Order deleted and reserved stock released"
        })



class AdminAllOrderView(GenericAPIView, BaseResponseMixin):
    """Class to handle the retrieval of all orders"""
    permission_classes = [IsSuperAdminPermission]
    authentication_classes = [CookieTokenAuthentication]
    serializer_class = OrderSerializer

    def get(self, request):
        """Retrieve all orders and their items"""
        queryset = Order.objects.all().select_related('user').prefetch_related('order_items')
        serializer = self.serializer_class(queryset, many=True)

        return self.get_response(
            status.HTTP_200_OK,
            "All orders retrieved successfully.",
            serializer.data
        )
    

class UserOrderListView(GenericAPIView, BaseResponseMixin):
    """List all order from a single user"""
    permission_classes = [IsAuthenticated]
    authentication_classes = [CookieTokenAuthentication]
    serializer_class = OrderSerializer

    def get(self, request):
        """Retrieve all order for a single seller"""
        queryset = Order.objects.filter(user=request.user).prefetch_related('order_items')
        serializer = self.serializer_class(queryset, many=True)
        return self.get_response(
            status.HTTP_200_OK,
            "User orders retrieved successfully",
            serializer.data
        )
    

class OrderDetailView(GenericAPIView, BaseResponseMixin):
    """Class to view order details"""
    permission_classes = [IsAuthenticated]
    authentication_classes = [CookieTokenAuthentication]
    serializer_class = OrderWithShipmentSerializer

    def get(self, request, order_id):
        if request.user.is_staff or request.user.is_superuser:
            order = get_object_or_404(Order, id=order_id)
        else:
            order = get_object_or_404(Order, id=order_id, user=request.user)

        serializer = self.serializer_class(order)
        return self.get_response(
            status.HTTP_200_OK,
            "Order details retrieved successfully",
            serializer.data
        )


class OrderReturnRequestView(GenericAPIView, BaseResponseMixin):
    """
    Class to handle order return request
    For order cancellation and request for a refund
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [CookieTokenAuthentication]
    serializer_class = OrderReturnRequestSerializer

    def post(self, request, *args, **kwargs):
        """
        Allow users with real and paid purchases to cancel
        Paid orders and request a refund
        """
        from payment.models import OrderStatusLog

        order_item_id = request.data.get('order_item_id')
        reason = request.data.get('reason')
        attachments = request.data.get("attachments")

        if not order_item_id or not reason:
            return self.get_response(
                status.HTTP_400_BAD_REQUEST,
                "order_id and reason required"
            )
        
        try:
            order_item = OrderItem.objects.get(id=order_item_id, order__user=request.user)
        except OrderItem.DoesNotExist:
            return self.get_response(
                status.HTTP_404_NOT_FOUND,
                "Order item not found"
            )
       #=============================Commented out for testing========================== 
        # Check if the order has been paid for
        if order_item.shipment.status not in [
            OrderShipment.Status.DELIVERED_TO_CUSTOMER_ADDRESS,
            OrderShipment.Status.DELIVERED_TO_TERMINAL,
            OrderShipment.Status.DELIVERED_TO_PICKUP_POINT
        ]:
            return self.get_response(
                status.HTTP_400_BAD_REQUEST,
                "Only delivered orders can be returned"
            )
        
        # Check to prevent duplicate request
        if OrderReturnRequest.objects.filter(order_item=order_item).exists():
            return self.get_response(
                status.HTTP_400_BAD_REQUEST,
                "Order cancellation and return request already initiated"
            )
        
        # Create request
        order_return = OrderReturnRequest.objects.create(
            order_item=order_item, reason=reason,
            status=OrderReturnRequest.Status.REQUESTED
        )        

        update_order_status(
            order_return, OrderReturnRequest.Status.REQUESTED,
            request.user, OrderStatusLog.OrderType.ORDERRETURNREQUEST,
            force=True
        )

        serializer = self.get_serializer(order_return)

        #Pass attachments to signal via context
        order_return._attachments_data = attachments
        transaction.on_commit(lambda: create_message_for_instance(order_return))

        return self.get_response(
            status.HTTP_201_CREATED,
            "Order cancellation and return request submitted",
            serializer.data
        )
    

class ApproveReturnView(APIView, BaseResponseMixin):
    """
    Class to allow admin or superuser to approve return request
    """
    permission_classes = [IsAdminUser]
    authentication_classes = [CookieTokenAuthentication]


    def patch(self, request):
        """Allows admin to approve cancellation request"""
        return_id = request.data.get('return_id')

        if not return_id:
            return self.get_response(
                status.HTTP_400_BAD_REQUEST,
                "return_id is required"
            )
        
        try:
            req = OrderReturnRequest.objects.select_related('order_item').get(id=return_id)
        except OrderReturnRequest.DoesNotExist as e:
            logger.error(f"Return request not found for approval: {str(e)}")
            return self.get_response(
                status.HTTP_404_NOT_FOUND,
                "Return request not found"
            )
        
        # Check if the request is already approved
        if req.status == OrderReturnRequest.Status.APPROVED:
            return self.get_response(
                status.HTTP_400_BAD_REQUEST,
                "Order return request already approved"
            )

        # Find the transaction for this order
        try:
            tx = PaystackTransaction.objects.get(order=req.order_item.order, status="success")
        except PaystackTransaction.DoesNotExist as e:
            logger.error(f"PaystackTransaction not found for return approval: {str(e)}")
            return self.get_response(
                status.HTTP_404_NOT_FOUND,
                "Associated payment transaction not found"
            )
        
        # Approve and restock
        approve_return(req, request.user)

        # Get the order item amount for refund
        order_item = req.order_item
        amount = order_item.total_price

        # Trigger refund
        refund_result = trigger_refund(tx.reference, amount=amount)

        if not refund_result.get("status"):
            return self.get_response(
                status.HTTP_400_BAD_REQUEST,
                "Return approved but refund failed",
                refund_result
            )
        elif refund_result.get("status"):
            req.status = OrderReturnRequest.Status.COMPLETED
            req.processed_at = now()
            req.save(update_fields=["status", "processed_at"])

        update_order_status(
            req, OrderReturnRequest.Status.COMPLETED,
            request.user, OrderStatusLog.OrderType.ORDERRETURNREQUEST
        )        
    
        return self.get_response(
            status.HTTP_200_OK,
            "Return approved and refund initiated",
            refund_result
        )
    

class RejectReturnView(APIView, BaseResponseMixin):
    """
    Class to allow admin or superuser to reject return request
    """
    permission_classes = [IsAdminUser]
    authentication_classes = [CookieTokenAuthentication]


    def patch(self, request):
        """Allows admin to approve cancellation request"""
        return_id = request.data.get('return_id')

        if not return_id:
            return self.get_response(
                status.HTTP_400_BAD_REQUEST,
                "return_id is required"
            )
        
        try:
            req = OrderReturnRequest.objects.select_related('order_item').get(id=return_id)
        except OrderReturnRequest.DoesNotExist:
            return self.get_response(
                status.HTTP_404_NOT_FOUND,
                "Return or cancellation request not found"
            )
        
        # Check if the request is already approved or rejected
        if req.status == OrderReturnRequest.Status.APPROVED:
            return self.get_response(
                status.HTTP_400_BAD_REQUEST,
                "Cancellation request already approved"
            )
        
        if req.status == OrderReturnRequest.Status.REJECTED:
            return self.get_response(
                status.HTTP_400_BAD_REQUEST,
                "Cancellation request already rejected"
            )
        
        # Reject return request
        req.status = OrderReturnRequest.Status.REJECTED
        req.processed_at = now()
        req.save(update_fields=["status", "processed_at"])

        update_order_status(
            req, OrderReturnRequest.Status.REJECTED,
            request.user, OrderStatusLog.OrderType.ORDERRETURNREQUEST
        )

        return self.get_response(
            status.HTTP_200_OK,
            "Return rejected"
        )
    

class ReturnsEmailWebhookView(APIView, BaseResponseMixin):
    """Webhook to retrieve and ingest customers messages"""
    authentication_classes = []
    permission_classes = []

    def post(self, request, *args, **kwargs):
        """
        Mailgun webhook to handle the extraction and saving
        of customers return messages/emails
        """
        from support.utils import extract_reply_body

        sender = request.data.get("sender") # customer's email
        recipient = request.data.get("recipient") # support email
        subject = request.data.get("subject", "")
        body_plain = request.data.get("body-plain")
        clean_body = extract_reply_body(body_plain)
        attachments = request.FILES 

        # Find the return request by email
        # get user by email
        try:
            user = CustomUser.objects.get(email=sender)
        except CustomUser.DoesNotExist as e:
            logger.error(f"Customer not found for return email webhook: {str(e)}")
            return self.get_response(
                status.HTTP_404_NOT_FOUND,
                "Customer not found"
            )

        match = re.search(r"\[(SUP|RET)-[A-Z0-9]{8}\]", subject)
        if not match:
            return self.get_response(
                status.HTTP_400_BAD_REQUEST,
                "Reference code not found in subject"
            )
        reference = match.group(0).strip("[]")
        returns = OrderReturnRequest.objects.filter(
            order_item__order__user=user,
            reference=reference
        ).first()

        if not returns:
            return self.get_response(
                status.HTTP_404_NOT_FOUND,
                "Return request not found"
            )

        # Create message
        msg = Message.objects.create(
            # content_type=ContentType.objects.get_for_model(OrderReturnRequest),
            # object_id=returns.id,
            parent=returns,
            sender=user,
            subject=subject,
            team_email=recipient,
            body=clean_body,
            sent_at=now()
        )

        # Handle attachments
        if attachments:
            handle_mailgun_attachments(attachments, msg, type="returns")


        try:
            ticket = Tickets.objects.get(
                content_type=ContentType.objects.get_for_model(OrderReturnRequest),
                object_id=returns.id,
            )
            # Notifications only if ticket already exists and is assigned
            if ticket.ticket_state == Tickets.State.ASSIGNED:
                if ticket.re_assigned:
                    Notification.objects.create(
                        user=ticket.re_assigned_to.team,
                        type=Notification.Type.ORDER_RETURN,
                        channel=Notification.ChannelChoices.INAPP,
                        subject=subject,
                        message=body_plain,
                        content_type=ContentType.objects.get_for_model(Message),
                        parent=msg,
                        object_id=msg.id,
                    )
                else:
                    Notification.objects.create(
                        user=ticket.assigned_to.team,
                        type=Notification.Type.ORDER_RETURN,
                        channel=Notification.ChannelChoices.INAPP,
                        subject=subject,
                        message=body_plain,
                        content_type=ContentType.objects.get_for_model(Message),
                        object_id=msg.id,
                    )
        except Tickets.DoesNotExist as e:
            logger.info(f"No ticket found for return email webhook: {str(e)}")
            pass

        return Response({
            "status": "ok",
            "message_id": msg.id,
        }, status=status.HTTP_201_CREATED)


class ShipmentListView(GenericAPIView, BaseResponseMixin):
    """
    Class to display order shipment details
    Used by both buyers and sellers
    """
    serializer_class = OrderShipmentSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [CookieTokenAuthentication]

    def get_queryset(self, request, *args, **kwargs):
        return get_object_or_404(
            OrderShipment, order=kwargs["order_id"],
            order__user=request.user
        )
    
    def get(self, request, order_id, *args, **kwargs):
        """Retrieve buyers shipment details"""
        if not order_id:
            return self.get_response(
                status.HTTP_400_BAD_REQUEST,
                "Please provide the order_id"
            )
        queryset = self.get_queryset(request, *args, **kwargs)

        serializer = self.get_serializer(queryset)

        return self.get_response(
            status.HTTP_200_OK,
            "Shipment data returned successfully",
            serializer.data
        )

