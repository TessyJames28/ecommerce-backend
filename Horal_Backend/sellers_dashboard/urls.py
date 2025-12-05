from django.urls import path
from .views import (
    SellerProductRatingView,
    SellerOrderListView,
    SellerProfileView,
    SellerDashboardAnalyticsAPIView,
    TopSellingProductsAPIView,
    SellerOrderDetailView,
    ReauthOTPStartView,
    ReauthOTPVerifyView,
    ConfirmSellerEmailUpdateOTPView,
    ResendOTPView,
)


urlpatterns = [
    path('reviews/', SellerProductRatingView.as_view(), name="product_reviews"),
    path('orders/', SellerOrderListView.as_view(), name="seller-orders"),
    path('orders/<uuid:order_item_id>/', SellerOrderDetailView.as_view(), name="seller-order-item-details"),
    path('profile/', SellerProfileView.as_view(), name='seller-profile'),
    path("analytics/", SellerDashboardAnalyticsAPIView.as_view(), name="seller-dashboard-analytics"),
    path("topselling/", TopSellingProductsAPIView.as_view(), name="seller_top_selling_product"),
    path("reauth/otp/start/", ReauthOTPStartView.as_view(), name="reauth_otp_start"),
    path("reauth/otp/verify/", ReauthOTPVerifyView.as_view(), name="reauth_otp_verify"),
    path("profile/confirm-otp/", ConfirmSellerEmailUpdateOTPView.as_view(), name="confirm-seller-email-otp-update"),
    path("profile/resend-otp/", ResendOTPView.as_view(), name="resend-otp-email-update"),

]