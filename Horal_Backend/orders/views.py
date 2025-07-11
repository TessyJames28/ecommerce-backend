from django.shortcuts import get_object_or_404
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db import transaction
from rest_framework.exceptions import ValidationError
from products.utility import IsSuperAdminPermission
from payment.views import trigger_refund
from payment.models import PaystackTransaction
from payment.utility import update_order_status
from notification.utility import (
    store_order_otp, verify_order_otp, generate_otp,
    send_otp_email
)

from .utility import approve_return
from .models import Order, OrderItem
from .serializer import OrderReturnRequest, OrderSerializer, OrderReturnRequestSerializer
from carts.models import Cart
from products.utility import BaseResponseMixin, update_quantity

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
                order = Order.objects.create(user=user, total_amount=total)
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
                    print(f"Variant: {variant}")
                    print(variant.product)
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
        order_id = request.data.get('order_id')
        reason = request.data.get('reason')

        if not order_id or not reason:
            return self.get_response(
                status.HTTP_400_BAD_REQUEST,
                "order_id and reason required"
            )
        
        try:
            order = Order.objects.get(id=order_id, user=request.user)
        except Order.DoesNotExist:
            return self.get_response(
                status.HTTP_404_NOT_FOUND,
                "Order not found"
            )
        
        # Check if the order has been paid for
        if order.status != Order.Status.PAID:
            return self.get_response(
                status.HTTP_400_BAD_REQUEST,
                "Only paid orders can be returned"
            )
        
        # Check to prevent duplicate request
        if OrderReturnRequest.objects.filter(order=order).exists():
            return self.get_response(
                status.HTTP_400_BAD_REQUEST,
                "Order cancellation and return request already initiated"
            )
        
        # Create request
        order_return = OrderReturnRequest.objects.create(order=order, reason=reason)

        update_order_status(order, Order.Status.RETURN_REQUESTED, request.user)

        serializer = self.get_serializer(order_return)

        return self.get_response(
            status.HTTP_201_CREATED,
            "Order cancellation and return request submitted",
            serializer.data
        )
    

class ApproveReturnView(APIView, BaseResponseMixin):
    """
    Class to allow admin or superuser to approve return request
    """
    permission_classes = [IsSuperAdminPermission]


    def post(self, request):
        """Allows admin to approve cancellation request"""
        return_id = request.data.get('return_id')

        if not return_id:
            return self.get_response(
                status.HTTP_400_BAD_REQUEST,
                "return_id is required"
            )
        
        try:
            req = OrderReturnRequest.objects.select_related('order').get(id=return_id)
        except OrderReturnRequest.DoesNotExist:
            return self.get_response(
                status.HTTP_404_NOT_FOUND,
                "Return or cancellation request not found"
            )
        
        # Check if the request is already approved
        if req.approved:
            return self.get_response(
                status.HTTP_400_BAD_REQUEST,
                "Cancellation request already approved"
            )
        
        # Approve and restock
        approve_return(req, request.user)

        # Find the transaction for this order
        try:
            tx = PaystackTransaction.objects.get(order=req.order)
        except PaystackTransaction.DoesNotExist:
            return self.get_response(
                status.HTTP_404_NOT_FOUND,
                "Associated payment transaction not found"
            )
        
        # Trigger refund
        refund_result = trigger_refund(tx.reference)

        if not refund_result.get("status"):
            return self.get_response(
                status.HTTP_400_BAD_REQUEST,
                "Return approved but refund failed",
                refund_result
            )
    
        return self.get_response(
            status.HTTP_200_OK,
            "Return approved and refund initiated",
            refund_result
        )
    