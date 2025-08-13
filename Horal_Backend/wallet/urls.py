from django.urls import path
from .views import (
    SellerBankDetailView,
    InitiateWithdrawalView,
    SingleSellerPayoutView,
    SingleTransactionHistoryView,
    VerifySellerBankDetailsView,
    ConfirmWithdrawalView,
    AllBankDataView
)


urlpatterns = [
    path('verify-bank/', VerifySellerBankDetailsView.as_view(), name="verify_bank_detail"),
    path("initiate-withdrawal/", InitiateWithdrawalView.as_view(), name="initiate-withdraw"),
    path("withdraw/", ConfirmWithdrawalView.as_view(), name="confirm-withdrawal"),
    path("transaction/", SellerBankDetailView.as_view(), name="bank_and_transaction_data"),
    path("withdrawal/<uuid:payout_id>/", SingleSellerPayoutView.as_view(), name="single_withdrawal_detail"),
    path("transaction-history/<uuid:transaction_id>/", SingleTransactionHistoryView.as_view(), name="single_transaction_detail"),
    path("banks/", AllBankDataView.as_view(), name="all_bank_data"),
    
]
