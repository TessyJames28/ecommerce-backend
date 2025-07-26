from django.shortcuts import get_object_or_404
from rest_framework.generics import GenericAPIView
from products.utility import BaseResponseMixin
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from products.models import ProductVariant
from .models import ProductRatingSummary
from .serializers import (
    SellerProductRatingsSerializer,
    SellerProductOrdersSerializer,
    SellerProfileSerializer,
)
from user_profile.models import Profile
from shops.models import Shop
from django.db.models import Q
from orders.models import OrderItem
from django.utils.timezone import timezone
import calendar


# Create your views here.
class SellerProductRatingView(GenericAPIView, BaseResponseMixin):
    """
    Class to handle the aggregation logic for sellers
    products ratings
    """
    serializer_class = SellerProductRatingsSerializer
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        """
        Get all products and the ratings for a specific seller
        Get all ProductIndex entries that point to linked
        products under the seller shops
        """
        sort = request.query_params.get("sort", "recent")
        search = request.query_params.get("search", "").strip()

        # Get seller's shops
        shops = Shop.objects.filter(owner__user_id=request.user)

        # Instead of product__in (inefficient for large datasets)
        ratings = ProductRatingSummary.objects.filter(
            shop__in=shops
        ).select_related("product", "shop")

        ratings = list(ratings)  # Get the related ProductIndex objects as a python list

        # Apply serach only within sellers rated products
        if search:

            # Filter in Python based on linked_product fields
            ratings = [
                rating for rating in ratings
                if hasattr(rating.product, 'linked_product') and rating.product.linked_product and (
                    search.lower() in getattr(rating.product.linked_product, 'title', '').lower()
                    or search.lower() in getattr(rating.product.linked_product, 'description', '').lower()
                )
            ]

        # Apply sorting
        if sort == "oldest":
            ratings.sort(key=lambda r: r.product.created_at or timezone.datetime.min)
        else:
            ratings.sort(key=lambda r: r.product.created_at or timezone.datetime.min, reverse=True)


        # serializer response
        serializer = self.get_serializer({
            "shop": shops.first(),
            "reviews": ratings
        })

        return self.get_response(
            status.HTTP_200_OK,
            "Sellers products ratings retrieved successfully",
            serializer.data
        )


class SellerOrderListView(GenericAPIView, BaseResponseMixin):
    """
    Class that handles the retrieval of all a sellers order
    """
    serializer_class = SellerProductOrdersSerializer
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        """
        Get all orders beloging to a seller
        """
        user = request.user
        search = request.query_params.get("search")
        filter_status = request.query_params.get("status")
        year = request.query_params.get("year")
        month_input = request.query_params.get("month")
        
        # Convert month value like "january" into numeric value
        month = None
        if month_input:
            try:
                month = list(calendar.month_name).index(month_input.capitalize())
            except ValueError:
                return self.get_response(
                    status.HTTP_400_BAD_REQUEST,
                    "Invalid month name"
                )
            
        # get seller's shop
        try:
            shop = Shop.objects.get(owner__user=user)
        except Shop.DoesNotExist:
            return self.get_response(
                status.HTTP_404_NOT_FOUND,
                "Shop not found"
            )
        
        # Filter order where the product belongs to the seller's shop
        order_items = OrderItem.objects.select_related("variant", "order", "order__user").filter(
            variant__shop=shop
        )


        # Apply search option
        if search:
            # First: get variant IDs where product title matches
            matching_variant_ids = []

            for variant in ProductVariant.objects.select_related("shop"):
                product = variant.product  # GFK object
                if hasattr(product, "title") and search.lower() in product.title.lower():
                    matching_variant_ids.append(variant.id)

            # Then use the IDs to filter the main query
            order_items = order_items.filter(
                Q(order__id__icontains=search) |
                Q(variant__id__in=matching_variant_ids) |
                Q(order__user__full_name__icontains=search)
            )

        # Apply filtering
        if filter_status:
            order_items = order_items.filter(order__status__icontains=filter_status)

        if year:
            order_items = order_items.filter(order__created_at__year=year)

        if month:
            order_items = order_items.filter(order__created_at__month=month)

        serializer = self.get_serializer({
            "shop": shop,
            "orders": order_items
        })

        return self.get_response(
            status.HTTP_200_OK,
            "Sellers order retrieved successfully",
            serializer.data
        )
    

class SellerProfileView(GenericAPIView):
    """
    View to retrieve the complete seller profile
    """
    permission_classes = [IsAuthenticated]
    serializer_class = SellerProfileSerializer

    def get_profile(self):
        return get_object_or_404(Profile, user=self.request.user)

    def get(self, request, *args, **kwargs):
        user = request.user
        profile = self.get_profile()

        if not user.is_seller:
            return Response({
                "status": "error",
                "message": "Only sellers can access this endpoint."
            }, status=status.HTTP_403_FORBIDDEN)

        serializer = self.get_serializer(profile)
        return Response({
            "status": "success",
            "message": "Seller profile retrieved successfully",
            "data": serializer.data
        }, status=status.HTTP_200_OK)
    

    def patch(self, request, *args, **kwargs):
        print(f"Inside update view => data: {request.data}\nuser: {request.user}")
        profile = self.get_profile()
        serializer = self.get_serializer(
            profile,
            data=request.data,
            partial=True  # Allow partial updates
        )
        
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({
            "status": "success",
            "message": "Seller profile updated successfully",
            "data": serializer.data
        }, status=status.HTTP_200_OK)
