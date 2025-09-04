from django.urls import path
from .views import (
    UserRatingCreateView,
    ProductReviewListView,
    ProductReviewDetailView,
    ProductReviewUpdateDeleteView,
)

urlpatterns = [
    path('product/<uuid:product_id>/reviews/', ProductReviewListView.as_view(), name='product-reviews'),
    path('product/<uuid:product_id>/add/', UserRatingCreateView.as_view(), name='add-review'),
    path('<uuid:review_id>/', ProductReviewDetailView.as_view(), name='review-detail'),
    path('<uuid:review_id>/update/', ProductReviewUpdateDeleteView.as_view(), name='review-update'),
    path('<uuid:review_id>/delete/', ProductReviewUpdateDeleteView.as_view(), name='review-delete'),
    
]
