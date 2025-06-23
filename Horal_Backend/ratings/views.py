from django.shortcuts import get_object_or_404
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework import status
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError, PermissionDenied
from django.db.models import Avg
from .models import UserRating
from .serializers import UserRatingSerializer
from products.utility import BaseResponseMixin, IsAdminOrSuperuser
from orders.models import Order, OrderItem
from products.models import ProductIndex, ProductVariant

# Create your views here.

class UserRatingCreateView(GenericAPIView, BaseResponseMixin):
    permission_classes = [IsAuthenticated]
    serializer_class = UserRatingSerializer

    def post(self, request, product_id, *args, **kwargs):
        user = request.user

        # Check product exists in index
        try:
            product_index = ProductIndex.objects.get(id=product_id)
        except ProductIndex.DoesNotExist:
            return self.get_response(
                status.HTTP_404_NOT_FOUND,
                "Product not found"
            )
        
        # Get all delivered or paid orders by the user
        eligible_orders = Order.objects.filter(user=user, status__in=['paid', 'delivered'])

        # Get all variants related to this product
        variants_of_product = ProductVariant.objects.filter(object_id=product_index.id)

        # Check if user purchased any of those variants
        has_purchased = OrderItem.objects.filter(
            order__in=eligible_orders,
            variant__in=variants_of_product
        ).first()

        if not has_purchased:
            raise PermissionDenied("You can only review products you have purchased")

        existing_review = UserRating.objects.filter(user=user, product=product_index, order_item=has_purchased).first()
        if existing_review:
            raise ValidationError("You have already reviewed this product.")

        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(user=user, order_item=has_purchased, product=product_index)
        return self.get_response(
            status.HTTP_201_CREATED,
            "User review added successfully",
            serializer.data
        )


class ProductReviewListView(GenericAPIView, BaseResponseMixin):
    """
    List all reviews for a product
    """
    serializer_class = UserRatingSerializer
    permission_classes = [AllowAny]
    
    def get(self, request, product_id, *args, **kwargs):
        """Get all product reviews"""
        reviews = UserRating.objects.filter(product=product_id)
        serializer = self.get_serializer(reviews, many=True)

        # Inject total rating and count from view
        total_rating = UserRating.objects.filter(product=product_id).aggregate(avg_rating=Avg('rating'))['avg_rating']
        total_rating = round(total_rating, 1) if total_rating else 0.0

        count = UserRating.objects.filter(product=product_id).count()

        response_data = {
            "reviews": serializer.data,
            "total_rating": total_rating,
            "review_count": count
        }
        
        return self.get_response(
            status.HTTP_200_OK,
            "Reviews retrieved successfully",
            response_data
        )


class ProductReviewDetailView(GenericAPIView, BaseResponseMixin):
    """
    Class to handle single review view
    """
    serializer_class = UserRatingSerializer
    permission_classes = [AllowAny]


    def get(self, request, *args, **kwargs):
        """Retrive a single review"""
        review_id = self.kwargs.get('review_id')
        try:
            review = UserRating.objects.get(id=review_id)
        except UserRating.DoesNotExist:
            return self.get_response(
                status.HTTP_404_NOT_FOUND,
                "Review not found"
            )
        serializer = self.get_serializer(review)
        return self.get_response(
            status.HTTP_200_OK,
            "Review retrieve successfully",
            serializer.data
        )
    

class ProductReviewUpdateDeleteView(GenericAPIView, BaseResponseMixin):
    """
    Class to handle the update and deleting of a review
    This feature is available to admin only
    """
    serializer_class = UserRatingSerializer
    permission_classes = [IsAdminOrSuperuser]

    def put(self, request, *args, **kwargs):
        """Update feature for user review"""
        review_id = self.kwargs.get("review_id")

        try:
            review = get_object_or_404(UserRating, id=review_id)
        except UserRating.DoesNotExist:
            return self.get_response(
                status.HTTP_404_NOT_FOUND,
                "Review not found"
            )
        
        serializer = self.get_serializer(review, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return self.get_response(
            status.HTTP_200_OK,
            "Review updated successfully",
            serializer.data
        )
    

    def delete(self, request, *args, **kwargs):
        """
        Delete operation for review
        Only super admin and staff is authorize to perform this operation
        """
        review_id = self.kwargs.get("review_id")
        user = request.user

        try:
            review = UserRating.objects.filter(id=review_id)
            review.delete()
            return self.get_response(
                status.HTTP_204_NO_CONTENT,
                "Review deleted successfully"
            )
        except UserRating.DoesNotExist:
            return self.get_response(
                status.HTTP_404_NOT_FOUND,
                "Review not found"
            )

