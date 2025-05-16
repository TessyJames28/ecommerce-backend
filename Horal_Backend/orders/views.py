from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from rest_framework.response import Response
from django.db import transaction
from rest_framework.exceptions import ValidationError

from .models import Order, OrderItem
from .serializer import OrderItemSerializer, OrderSerializer
from carts.models import Cart, CartItem
from products.utility import BaseResponseMixin, update_quantity

# Create your views here.

class CheckoutView(GenericAPIView, BaseResponseMixin):
    """Checkout cart and place order (status: pending)"""
    permission_classes = [IsAuthenticated]
    serializer_class = OrderSerializer


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

                # Calculate total
                total = cart.total_price
                order = Order.objects.create(user=user, total_amount=total)

            
                for item in cart.cart_item.all():
                    variant = item.variant

                    # Check if requested quantity can be reserved
                    if item.quantity > variant.available_stock:
                        raise ValidationError(
                            f"Only {variant.available_stock} items available for {variant}"
                        )
                    # Reserve the stock
                    variant.reserved_quantity += item.quantity
                    variant.save()
                    update_quantity(variant.product)

                    OrderItem.objects.create(
                        order=order,
                        variant=item.variant,
                        quantity=item.quantity,
                        unit_price=item.variant.price_override or item.variant.product.price
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
            return self.get_response(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                "An unexpected error occurred while processing your order."
            )
        

class PaymentCallbackView(GenericAPIView, BaseResponseMixin):
    """Update order status after payment"""
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        """Handles order creation after payment"""
        order_id = request.data.get('order_id')
        status_input = request.data.get('status') # e.g paid, failed, cancelled

        if not order_id or not status_input:
            return self.get_response(
                status.HTTP_400_BAD_REQUEST,
                "order_id and status are required"
            )

        try:
            order = Order.objects.get(id=order_id, user=request.user)
        except Order.DoesNotExist:
            return self.get_response(
                status.HTTP_404_NOT_FOUND,
                "Order not found"
            )
        
        if status_input not in Order.Status.values:
            return self.get_response(
                status.HTTP_400_BAD_REQUEST,
                "Invalid status value"
            )
        
        try:
            with transaction.atomic():
                # If status is 'paid', deduct stock and clear cart
                if status_input == Order.Status.PAID:
                    for item in order.order_items.all():
                        variant = item.variant
                        
                        # Deduct from total stock after successful payment
                        variant.reserved_quantity -= item.quantity
                        variant.stock_quantity -= item.quantity
                        variant.save()
                        update_quantity(variant.product)

                    # Clear cart
                    CartItem.objects.filter(cart__user=request.user).delete()

                    # if failed or cancelled, leave stock as is but update status
                elif status_input in [Order.Status.FAILED, Order.Status.CANCELLED]:
                    for item in order.order_items.all():
                        variant = item.variant
                        variant.reserved_quantity -= item.quantity
                        variant.save()
                        update_quantity(variant.product)

                # Update the order status
                order.status = status_input
                order.save()
        except ValidationError as e:
            return self.get_response(
                status.HTTP_400_BAD_REQUEST,
                str(e)
            )
        
        except Exception:
            return self.get_response(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                "Something went wrong while updating your order"
            )

        serializer = OrderSerializer(order)
        return self.get_response(
            status.HTTP_200_OK,
            f"Order updated to {status_input}",
            serializer.data
        )
        