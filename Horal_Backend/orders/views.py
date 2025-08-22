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
from users.models import CustomUser
from .utils import approve_return
from .models import Order, OrderItem
from .serializers import OrderReturnRequest, OrderSerializer, OrderReturnRequestSerializer
from carts.models import Cart
from products.utils import BaseResponseMixin, update_quantity
from django.utils.timezone import now
from support.serializers import MessageSerializer
from support.utils import handle_mailgun_attachments, create_message_for_instance
from support.models import Message, SupportAttachment, Tickets
from django.contrib.contenttypes.models import ContentType
from notifications.models import Notification
import re

# Create your views here.

class CheckoutView(GenericAPIView, BaseResponseMixin):
    """Checkout cart and place order (status: pending)"""
    permission_classes = [IsAuthenticated]
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
                existing_order = Order.objects.filter(user=user, status=Order.Status.PENDING).first()
                if existing_order:
                    serializer = self.get_serializer(existing_order)
                    return self.get_response(
                        status.HTTP_200_OK,
                        "You already have a pending order",
                        serializer.data
                    )

                # If no existing order, continue creating one and calculate total
                total = cart.total_price
                address = None
                if hasattr(user, 'shipping_address'):
                    address = user.shipping_address

                order, created = Order.objects.update_or_create(
                    user=user,
                    total_amount=total,
                    street_address=address.street_address if address else None,
                    local_govt=address.local_govt if address else None,
                    landmark=address.landmark if address else None,
                    country=address.country if address else None,
                    state=address.state if address else None,
                    phone_number=address.phone_number if address else None,
                    created_at=now()  # Ensure created_at is set
                )
                update_order_status(order, Order.Status.PENDING, user, force=True)
            
                for item in cart.cart_item.all():
                    variant = item.variant

                    # Check if requested quantity can be reserved
                    if item.quantity > variant.stock_quantity:
                        raise ValidationError(
                            f"Only {variant.available_stock} items available for {variant}"
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

                serializer = self.get_serializer(order)

                return self.get_response(
                    status.HTTP_201_CREATED,
                    "Order placed, Awaiting payment",
                    serializer.data
                )
        except ValidationError as e:
            return self.get_response(
                status.HTTP_400_BAD_REQUEST,
                str(e)
            )
        
        except Exception as e:
            print(e)
            return self.get_response(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                str(e)
            )
        
    def put(self, request, *args, **kwargs):
        """Partial updates for user address during checkout"""
        order = self.get_queryset().first()

        if not order:
            return self.get_response(
                status.HTTP_404_NOT_FOUND,
                "No pending order found for address update"
            )
        
        serializer = self.get_serializer(order, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return self.get_response(
            status.HTTP_200_OK,
            "Shipping address updated successfully",
            serializer.data
        )


class OrderDeleteView(GenericAPIView):
    """
    class to handle the delete view for order
    and reset reserved quantities
    """

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
    serializer_class = OrderSerializer

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
        print(f"Attachment order view: {attachments}")

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
        
        # Check if the order has been paid for
        if order_item.order.status != Order.Status.DELIVERED:
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
        except PaystackTransaction.DoesNotExist:
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
        except CustomUser.DoesNotExist:
            return self.get_response(
                status.HTTP_404_NOT_FOUND,
                "Customer not found"
            )

        match = re.search(r"\[(SUP|RET)-[A-Z0-9]{8}\]", subject)
        print(f"Match: {match}")
        print(f"Subject: {subject}")
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
        except Tickets.DoesNotExist:
            pass

        return Response({
            "status": "ok",
            "message_id": msg.id,
        }, status=status.HTTP_201_CREATED)

