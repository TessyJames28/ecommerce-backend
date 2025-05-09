from django.shortcuts import render, get_object_or_404
from rest_framework.generics import GenericAPIView
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from .models import Cart, CartItem
from .serializers import CartItemSerializer, CartSerializer, CartItemCreateSerializer
from products.models import ProductVariant
from products.utility import BaseResponseMixin

# Create your views here.
class CartView(GenericAPIView, BaseResponseMixin):
    """Handle the cart view endpoint"""
    serializer_class = CartSerializer
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, *args, **kwargs):
        """Get or create a cart for a user"""
        cart, _ = Cart.objects.get_or_create(user=request.user)
        serializer = self.get_serializer(cart)
        return self.get_response(
            status.HTTP_200_OK,
            "Cart retrieved successfully",
            serializer.data
        )
    


class CartItemCreateView(GenericAPIView, BaseResponseMixin):
    """Handle item creation on cart by resolving variant_id"""
    serializer_class = CartItemCreateSerializer


    def post(self, request, *args, **kwargs):
        """
        Post method to handle product addition inside the cart
        lookup and resolve variant id, increase or decrease quantity
        """
        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        cart_item = serializer.save()

        response_serializer = CartItemSerializer(cart_item)

        return self.get_response(
            status.HTTP_201_CREATED,
            "Item added to cart successfully",
            response_serializer.data
        )


class CartItemUpdateDeleteView(GenericAPIView, BaseResponseMixin):
    """Class to handle cart update and delete feature"""
    serializer_class = CartItemSerializer


    def put(self, request, item_id, *args, **kwargs):
        """Update quantity of an item in the cart"""
        cart_item = get_object_or_404(CartItem,id=item_id, cart__user=request.user)
        quantity = int(request.data.get("quantity", 0))

        if quantity < 1:
            return self.get_response(
                status.HTTP_400_BAD_REQUEST,
                "Quantity must be greater than 0",
            )
        
        if quantity > cart_item.variant.stock_quantity:
            return self.get_response(
                status.HTTP_400_BAD_REQUEST,
                "Insufficient Stock",
            )
        
        cart_item.quantity = quantity
        cart_item.save()
        serializer = self.get_serializer(cart_item)
        return self.get_response(
            status.HTTP_200_OK,
            "Cart item updated",
            serializer.data
        )
    

    def delete(self, request, item_id, *args, **kwargs):
        """Remove item from the cart"""
        cart_item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
        cart_item.delete()
        return Response({
            "status": status.HTTP_204_NO_CONTENT,
            "message": "Cart item removed"
        })
