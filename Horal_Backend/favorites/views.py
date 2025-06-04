from django.shortcuts import get_object_or_404
from rest_framework.generics import GenericAPIView
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from products.utility import BaseResponseMixin
from carts.authentication import SessionOrAnonymousAuthentication
from django.contrib.contenttypes.models import ContentType

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
    A class that handles item removal from favorites
    """
    serializer_class = FavoriteItemSerializer
    permission_classes = [AllowAny]
    authentication_classes = [SessionOrAnonymousAuthentication]


    def get_favorite_item(self, request, item_id):
        """
        Get favorite item based on authentication status
        """
        if request.user.is_authenticated:
            return get_object_or_404(
                FavoriteItem, id=item_id,
                favorites__user=request.user
            )
        else:
            session_key = request.session.session_key
            if not session_key:
                return None
            return get_object_or_404(
                FavoriteItem,
                id=item_id,
                favorites__session_key=session_key
            )
        
    
    def delete(self, request, item_id, *args, **kwargs):
        """
        Remove item from favorites
        """
        favorite_item = self.get_favorite_item(request, item_id)

        if not favorite_item:
            return self.get_response(
                status.HTTP_400_BAD_REQUEST,
                "Favorite item not found",
            )
        
        favorite_item.delete()
        return Response({
                "status": "success",
                "status code": status.HTTP_200_OK,
                "message": "Product removed from favorites"
        })
    

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
        product_type = request.query_params.get('product_type')

        if not product_id or not product_type:
            return self.get_response(
                status.HTTP_400_BAD_REQUEST,
                "Product ID and product type are required"
            )
        
        # Find the correct model and content type
        model_class = CATEGORY_MODELS.get(product_type)

        if not model_class:
            return self.get_response(
                status.HTTP_400_BAD_REQUEST,
                f"Invalid product type: {product_type}"
            )
        
        content_type = ContentType.objects.get_for_model(model_class)

        # Check if product is in favorites
        if request.user.is_authenticated:
            favorites = Favorites.objects.filter(user=request.user).first()
        else:
            session_key = request.session.session_key
            if not session_key:
                return self.get_response(
                    status.HTTP_200_OK,
                    "Product is not in favorites",
                    {"is_favorite": False}
                )
            favorites = Favorites.objects.filter(session_key=session_key).first()

        if not favorites:
            return self.get_response(
                status.HTTP_200_OK,
                "Product is not in favorites",
                {"is_favorite": False}
            )
        
        is_favorite = FavoriteItem.objects.filter(
            favorites=favorites,
            content_type=content_type,
            object_id=product_id
        ).exists()

        message = "Product is in favorites" if is_favorite else "Product is not in favorite"
        return self.get_response(
            status.HTTP_200_OK,
            message,
            {"is_favorite": is_favorite}
        )
    

class MergeFavoritesView(GenericAPIView, BaseResponseMixin):
    """
    Merge anonymous favorites with user favorites after login
    """
    serializer_class = FavoritesSerializer
    authentication_classes = [SessionOrAnonymousAuthentication]

    def post(self, request, *args, **kwargs):
        """
        Merge anonymous favorites into authenticated user favorites
        """
        if not request.user.is_authenticated:
            return self.get_response(
                status.HTTP_401_UNAUTHORIZED,
                "User must be authenticated to merge favorites"
            )
        
        session_key = request.session.session_key
        if not session_key:
            return self.get_response(
                status.HTTP_200_OK,
                "No anonymous favorites to merge",
            )
        
        try:
            anonymous_favorites = Favorites.objects.get(session_key=session_key)
            user_favorites, _ = Favorites.objects.get_or_create(user=request.user)

            # Move items from anonymous favorites to user favorites
            for item in anonymous_favorites.items.all():
                # Check if the item already exists in user favorites
                exists = FavoriteItem.objects.filter(
                    favorites=user_favorites,
                    content_type=item.content_type,
                    object_id=item.object_id
                ).exists()

                if not exists:
                    # Create a new favorite item for the user
                    FavoriteItem.objects.create(
                        favorites=user_favorites,
                        content_type=item.content_type,
                        object_id=item.object_id
                    )

            # Delete the anonymous favorites
            anonymous_favorites.delete()

            # Return the merged favorites
            serializer = self.get_serializer(user_favorites)
            return self.get_response(
                status.HTTP_200_OK,
                "Favorites merged successfully",
                serializer.data
            )
        
        except Favorites.DoesNotExist:
            return self.get_response(
                status.HTTP_200_OK,
                "No anonymous favorites to merge"
            )