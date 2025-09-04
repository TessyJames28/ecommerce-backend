from django.urls import path
from . import views


urlpatterns = [
    path('paystack/initialize/', views.InitializeTransaction.as_view(), name='initialize-transaction'),
    path('paystack/verify/<str:reference>/', views.VerifyTransaction.as_view(), name='verify-transaction'),
    path('paystack/webhook/', views.transaction_webhook, name='paystack-webhook'),
    path('refund/retry/', views.RetryRefundView.as_view(), name='retry-refund'),
    # path('callback/', views.Callback.as_view(), name='retry-refund'),

]