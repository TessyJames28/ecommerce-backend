from django.urls import path
from .views import (
    CheckoutView, OrderDeleteView,
    AdminAllOrderView, UserOrderListView, OrderDetailView,
    OrderReturnRequestView, ApproveReturnView,
    RejectReturnView, 
    ReturnsEmailWebhookView
)


urlpatterns = [
    path('<uuid:pk>/', OrderDeleteView.as_view(), name='order-deletion'),
    path('get/<uuid:order_id>/', OrderDetailView.as_view(), name='order-detail'),
    path('checkout/', CheckoutView.as_view(), name='checkout'),
    path('admin/all/', AdminAllOrderView.as_view(), name='admin-all-orders'),
    path('user-orders/', UserOrderListView.as_view(), name='user-order-list'),
    path('cancel/', OrderReturnRequestView.as_view(), name='order-cancellation'),
    path('return-approval/', ApproveReturnView.as_view(), name='return-approval'),
    path('return-rejection/', RejectReturnView.as_view(), name='return-rejection'),
    path('webhook/returns/', ReturnsEmailWebhookView.as_view(), name="returns-webhook"),   
]