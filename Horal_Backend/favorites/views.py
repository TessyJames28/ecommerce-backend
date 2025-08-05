from django.shortcuts import get_object_or_404
from rest_framework.generics import GenericAPIView
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from products.utils import BaseResponseMixin
from carts.authentication import SessionOrAnonymousAuthentication
from products.models import ProductIndex

from .models import FavoriteItem, Favorites
from .serializers import (
    FavoriteItemSerializer,
    FavoritesSerializer,
    AddToFavoritesSerializer,
    CATEGORY_MODELS
)

# Create your views here.

class FavoritesView(GenericAPIView, BaseResponseMixin):
    """
    Handle the favorites view endpoint for both
    authenticated and anonymous users
    """
    serializer_class = FavoritesSerializer
    permission_classes = [AllowAny]
    authentication_classes = [SessionOrAnonymousAuthentication]

    def get_favorites(self, request):
        """
        Get or create favorites based on user authentication status
        """

        if request.user.is_authenticated:
            favorites, _ = Favorites.objects.get_or_create(user=request.user)
        else:
            # For anonymous users, use session key
            session_key = request.session.session_key
            if not session_key:
                request.session.create()
                session_key = request.session.session_key

            favorites, _ = Favorites.objects.get_or_create(session_key=session_key)

        return favorites
    

    def get(self, request, *args, **kwargs):
        """
        Get or create favorites for authenticated and anonymous users
        """
        favorites = self.get_favorites(request)
        serializer = self.get_serializer(favorites)
        return self.get_response(
            status.HTTP_200_OK,
            "Favorites retrieved successfully",
            serializer.data
        )
    

class AddToFavoritesView(GenericAPIView, BaseResponseMixin):
    """
    Handles adding items to favorites
    """
    serializer_class = AddToFavoritesSerializer
    permission_classes = [AllowAny]
    authentication_classes = [SessionOrAnonymousAuthentication]

    def post(self, request, *args, **kwargs):
        """
        Post method to add products to favorites
        """
        serializer = self.get_serializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        favorite_item = serializer.save()

        response_serializer = FavoriteItemSerializer(favorite_item)
        return self.get_response(
            status.HTTP_201_CREATED,
            "Product added to favorites successfully",
            response_serializer.data
        )


class RemoveFromFavoritesView(GenericAPIView, BaseResponseMixin):
    """
    A class that handles item removal from favorites.
    Supports authenticated and anonymous users.
    """
    serializer_class = FavoriteItemSerializer
    permission_classes = [AllowAny]
    authentication_classes = [SessionOrAnonymousAuthentication]


    def delete(self, request, item_id, *args, **kwargs):
        """
        Delete a favorite item.
        """
        favorite_item = get_object_or_404(FavoriteItem, id=item_id)

        if not favorite_item:
            return self.get_response(
                status.HTTP_400_BAD_REQUEST,
                "Favorite item not found"
            )

        favorite_item.delete()
        return Response({
            "status": "success",
            "status_code": status.HTTP_200_OK,
            "message": "Product removed from favorites"
        }, status=status.HTTP_200_OK)

    

class CheckFavoriteStatusView(GenericAPIView, BaseResponseMixin):
    """
    Check if a product is in user's favorites
    """
    permission_classes = [AllowAny]
    authentication_classes = [SessionOrAnonymousAuthentication]


    def get(self, request, *args, **kwargs):
        """
        Check if a specific product is in favorites
        """
        product_id = request.query_params.get('product_id')

        if not product_id:
            return self.get_response(
                status.HTTP_400_BAD_REQUEST,
                "Product ID is required"
            )
        
        try:
            print("start to check ProductIndex")
            product_index = ProductIndex.objects.get(id=product_id)
            print(product_index)
        except ProductIndex.DoesNotExist:
            print("Enter exception")
            return self.get_response(
                status.HTTP_200_OK,
                "Product is not in favorites",
                {"is_favorite": False}
            )
        print("in favorite filter")
        is_favorite = FavoriteItem.objects.filter(
            product_index=product_index
        ).exists()

        message = "Product is in favorites" if is_favorite else "Product is not in favorite"
        return self.get_response(
            status.HTTP_200_OK,
            message,
            {"is_favorite": is_favorite}
        )
