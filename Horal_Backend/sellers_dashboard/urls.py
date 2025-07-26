from django.urls import path
from .views import (
    SellerProductRatingView,
    SellerOrderListView,
    SellerProfileView
)


urlpatterns = [
    path('reviews/', SellerProductRatingView.as_view(), name="product_reviews"),
    path('orders/', SellerOrderListView.as_view(), name="seller-orders"),
    path('profile/', SellerProfileView.as_view(), name='seller-profile'),

]