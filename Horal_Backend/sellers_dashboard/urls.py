from django.urls import path
from .views import (
    SellerProductRatingView,
    SellerOrderListView,
    SellerProfileView,
    SellerDashboardAnalyticsAPIView,
    TopSellingProductsAPIView
)


urlpatterns = [
    path('reviews/', SellerProductRatingView.as_view(), name="product_reviews"),
    path('orders/', SellerOrderListView.as_view(), name="seller-orders"),
    path('profile/', SellerProfileView.as_view(), name='seller-profile'),
    path("analytics/", SellerDashboardAnalyticsAPIView.as_view(), name="seller-dashboard-analytics"),
    path("topselling/", TopSellingProductsAPIView.as_view(), name="seller_top_selling_product"),
    
]