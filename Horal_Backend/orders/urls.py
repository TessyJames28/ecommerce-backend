from django.urls import path
from .views import (
    CheckoutView, PaymentCallbackView, OrderDeleteView,
    AdminAllOrderView, UserOrderListView, OrderDetailView
)


urlpatterns = [
    path('<uuid:order_id>/', OrderDetailView.as_view(), name='order-detail'),
    path('checkout/', CheckoutView.as_view(), name='checkout'),
    path('payment-callback/', PaymentCallbackView.as_view(), name='payment-callback'),
    path('<uuid:pk>/', OrderDeleteView.as_view(), name='order-deletion'),
    path('admin/all/', AdminAllOrderView.as_view(), name='admin-all-orders'),
    path('user-orders/', UserOrderListView.as_view(), name='user-order-list'),

]