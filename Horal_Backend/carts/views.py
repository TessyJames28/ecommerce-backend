from django.shortcuts import render, get_object_or_404
from rest_framework.generics import GenericAPIView
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from .models import Cart, CartItem
from .serializers import CartItemSerializer, CartSerializer, CartItemCreateSerializer
from products.utils import BaseResponseMixin
from .authentication import SessionOrAnonymousAuthentication

# Create your views here.
class CartView(GenericAPIView, BaseResponseMixin):
    """Handle the cart view endpoint for both authenticated and anonymous users"""
    serializer_class = CartSerializer
    permission_classes = [AllowAny]
    authentication_classes = [SessionOrAnonymousAuthentication]

    def get_cart(self, request):
        """Get or create a cart based on user authentication status"""
        try:
            if request.user.is_authenticated:
                cart, _ = Cart.objects.get_or_create(user=request.user)

                # Check if there is an orphaned session cart and merge if needed
                session_key = request.session.session_key
                if session_key:
                    session_cart = Cart.objects.filter(session_key=session_key).first()
                    if session_cart and session_cart.id != cart.id: # Don't merge is it's the same cart
                        self._merge_carts(session_cart, cart)
                        session_cart.delete() # Remove the session cart after merging

                        # Clear the session key reference to avoid stale references
                        request.session['cart_merged'] = True
                    
                return cart
            else:
                # Create cart for anonymous users using session key
                session_key = request.session.session_key
                if not session_key:
                    request.session.save() # Create a session if one doesn't exist
                    session_key = request.session.session_key

                cart, _ = Cart.objects.get_or_create(session_key=session_key)

                return cart
        except Exception as e:
            # Log the error for debugging
            print(f"Error in get_cart: {str(e)}")
            # Create a new cart as fallback
            if request.user.is_authenticated:
                return Cart.objects.create(user=request.user)
            else:
                request.session.save()
                return Cart.objects.create(session_key=request.session.session_key)
    

    def get(self, request, *args, **kwargs):
        """Get or create a cart for a user or anonymous visitor"""
        cart = self.get_cart(request)
        serializer = self.get_serializer(cart)
        return self.get_response(
            status.HTTP_200_OK,
            "Cart retrieved successfully",
            serializer.data
        )
    

class CartDeleteView(GenericAPIView, BaseResponseMixin):
        """
        Handle cart deletion by users
        """
        serializer_class = CartSerializer
        permission_classes = [AllowAny]
        authentication_classes = [SessionOrAnonymousAuthentication]


        def get_cart(self, request):
            """Get or create a cart based on user authentication status"""
            cart_view = CartView()
            return cart_view.get_cart(request)

        def delete(self, request, cart_id):
            """
            Method to delete a cart
            """
            # cart = self.get_cart(request)
            user_cart = get_object_or_404(Cart, id=cart_id)

            if not user_cart:
                return self.get_response(
                    status.HTTP_404_NOT_FOUND,
                    "User cart not found"
                )
            
            user_cart.delete()
            return Response({
                "status": "success",
                "status_code": status.HTTP_204_NO_CONTENT,
                "message": "Cart deleted successfully"
            })



class CartItemCreateView(GenericAPIView, BaseResponseMixin):
    """Handle item creation on cart by resolving variant_id"""
    serializer_class = CartItemCreateSerializer
    permission_classes = [AllowAny]
    authentication_classes = [SessionOrAnonymousAuthentication]

    def get_cart(self, request):
        """Get or create a cart based on user authentication status"""
        cart_view = CartView()
        return cart_view.get_cart(request)
    

    def post(self, request, *args, **kwargs):
        """
        Post method to handle product addition inside the cart
        """
        # Make sure we are using the correct cart
        cart = self.get_cart(request)

        # Add cart to the context so serializer can use it
        serializer = self.get_serializer(data=request.data, context={
            'request': request,
            'cart': cart
        })
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
    permission_classes = [AllowAny]
    authentication_classes = [SessionOrAnonymousAuthentication]


    def get_cart(self, request):
        """Get current cart"""
        cart_view = CartView()
        return cart_view.get_cart(request)
    

    def get_cart_item(self, request, item_id):
        """Get cart item based on autehntication status"""
        try:
            cart = self.get_cart(request)
            return get_object_or_404(CartItem, id=item_id, cart=cart)
        except Exception as e:
            print(f"Error getting cart item: {str(e)}")
            return None
        

    def put(self, request, item_id, *args, **kwargs):
        """Update quantity of an item in the cart"""
        cart_item = self.get_cart_item(request, item_id)

        if not cart_item:
            return self.get_response(
                status.HTTP_404_NOT_FOUND,
                "Cart item not found",
            )
        
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
        cart_item = self.get_cart_item(request, item_id)
        if not cart_item:
            return self.get_response(
                status.HTTP_400_BAD_REQUEST,
                "Cart item not found",
            )
        cart_item.delete()
        return Response({
            "status": status.HTTP_204_NO_CONTENT,
            "message": "Cart item removed"
        })
    