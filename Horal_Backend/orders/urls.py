from django.urls import path
from .views import CheckoutView, PaymentCallbackView


urlpatterns = [
    path('checkout/', CheckoutView.as_view(), name='checkout'),
    path('payment-callback/', PaymentCallbackView.as_view(), name='payment-callback'),
    
]