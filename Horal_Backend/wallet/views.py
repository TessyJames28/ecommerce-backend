from django.shortcuts import render, get_object_or_404
from django.utils.decorators import method_decorator
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.generics import GenericAPIView
from rest_framework.exceptions import ValidationError
from django.conf import settings
from decimal import Decimal
from shops.models import Shop
from sellers.models import SellerKYC
from sellers_dashboard.helper import validate_uuid
from .utils import (
    get_bank_code,
    verify_bank_account,
    create_transfer_recipient,
    initiate_payout
)
from users.views import CookieTokenAuthentication
from users.models import CustomUser
from products.utils import BaseResponseMixin
from .models import SellersBankDetails, Payout, SellerTransactionHistory, Bank
from .serializers import (
    SellersBankDetailsSerializer,
    SellerBankDataSerializer,
    PayoutSerializer,
    SellerTransactionHistorySerializer, 
    BankSerializer
)
from sellers_dashboard.utils import get_withdrawable_revenue
from sellers_dashboard.decorators import require_reauth
import uuid

# Create your views here.


class VerifySellerBankDetailsView(APIView, BaseResponseMixin):
    """
    class to verify sellers bank details
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [CookieTokenAuthentication]

    def post(self, request):
        """Post method to get and verify seller bank details"""
        seller = request.user
        bank_name = request.data.get("bank_name")
        account_number = request.data.get("account_number").strip()
        
        if not account_number.isdigit() or len(account_number) != 10:
            raise ValidationError(f"Account number must be exactly 10 digits")

        try:
            user = CustomUser.objects.get(id=seller.id, is_seller=True)
        except CustomUser.DoesNotExist:
            return self.get_response(
                status.HTTP_404_NOT_FOUND,
                "This user is not an authenticated seller"
            )
        
        # Get bank code
        bank_code = get_bank_code(bank_name)
        if not bank_code:
            return self.get_response(
                status.HTTP_400_BAD_REQUEST,
                "Invalid bank name"
            )
        
        account_name = verify_bank_account(account_number, bank_code)
        if not account_name:
            return self.get_response(
                status.HTTP_400_BAD_REQUEST,
                "Bank verification failed"
            )
        
        # Get Seller name to compare to bank name
        seller_kyc = SellerKYC.objects.get(user=user)
        first_name = seller_kyc.address.first_name or ""
        middle_name = seller_kyc.address.middle_name or ""
        last_name = seller_kyc.address.last_name or ""
        business_name = seller_kyc.address.business_name or ""

        # Normalize to lowercase and remove extra spaces
        full_name = " ".join([first_name, middle_name, last_name]).strip().lower()
        business_name = business_name.strip().lower()
        account_name_clean = account_name.strip().lower()

        # Name comparison
        def names_match(registered, account):
            registered_set = set(registered.split())
            account_set = set(account.split())
            overlap = registered_set & account_set
            return len(overlap) / len(account_set) >= 0.6
        
        # full_name_set = set(full_name.split())
        # business_name_set = set(business_name.split())
        # account_name_set = set(account_name_clean.split())

        # # Fail only if it doesn't match either personal name or business name
        # if not (account_name_set <= full_name_set or account_name_set <= business_name_set):
        #     return self.get_response(
        #         status.HTTP_400_BAD_REQUEST,
        #         "The bank account name does not match your registered name or business name."
        #     )

        if not (names_match(full_name, account_name_clean) or names_match(business_name, account_name_clean)):
            return self.get_response(
                status.HTTP_400_BAD_REQUEST,
                "The bank account name does not sufficiently match your registered name or business name."
            )
        
        # Create transfer recipient
        recipient_code = create_transfer_recipient(account_name, account_number, bank_code)

        # Save bank details
        seller = SellersBankDetails.objects.create(
            bank_name=bank_name,
            account_name=account_name,
            seller=user,
            account_number=account_number,
            bank_code=bank_code,
            recipient_code=recipient_code
        )
        seller.save()

        return Response({
            "status": "success",
            "status_code": status.HTTP_200_OK,
            "message": "Bank details verified and saved successfully",
            "account_name": account_name
        }, status=status.HTTP_200_OK)
    

class UpdateSellerBankDetailsView(APIView, BaseResponseMixin):
    """
    class to verify sellers bank details
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [CookieTokenAuthentication]

    @method_decorator(require_reauth)
    def put(self, request):
        """Post method to get and verify seller bank details"""
        seller = request.user
        bank_name = request.data.get("bank_name")
        account_number = request.data.get("account_number").strip()
        
        if not account_number.isdigit() or len(account_number) != 10:
            raise ValidationError(f"Account number must be exactly 10 digits")

        try:
            user = CustomUser.objects.get(id=seller.id, is_seller=True)
        except CustomUser.DoesNotExist:
            return self.get_response(
                status.HTTP_404_NOT_FOUND,
                "This user is not an authenticated seller"
            )
        
        # Get bank code
        bank_code = get_bank_code(bank_name)
        if not bank_code:
            return self.get_response(
                status.HTTP_400_BAD_REQUEST,
                "Invalid bank name"
            )
        
        account_name = verify_bank_account(account_number, bank_code)
        if not account_name:
            return self.get_response(
                status.HTTP_400_BAD_REQUEST,
                "Bank verification failed"
            )
        
        # Get Seller name to compare to bank name
        seller_kyc = SellerKYC.objects.get(user=user)
        first_name = seller_kyc.address.first_name or ""
        middle_name = seller_kyc.address.middle_name or ""
        last_name = seller_kyc.address.last_name or ""
        business_name = seller_kyc.address.business_name or ""

        # Normalize to lowercase and remove extra spaces
        full_name = " ".join([first_name, middle_name, last_name]).strip().lower()
        business_name = business_name.strip().lower()
        account_name_clean = account_name.strip().lower()

        # Name comparison
        def names_match(registered, account):
            registered_set = set(registered.split())
            account_set = set(account.split())
            overlap = registered_set & account_set
            return len(overlap) / len(account_set) >= 0.6
        # full_name_set = set(full_name.split())
        # business_name_set = set(business_name.split())
        # account_name_set = set(account_name_clean.split())

        # # Fail only if it doesn't match either personal name or business name
        # if not (account_name_set <= full_name_set or account_name_set <= business_name_set):
        #     return self.get_response(
        #         status.HTTP_400_BAD_REQUEST,
        #         "The bank account name does not match your registered name or business name."
        #     )

        if not (names_match(full_name, account_name_clean) or names_match(business_name, account_name_clean)):
            return self.get_response(
                status.HTTP_400_BAD_REQUEST,
                "The bank account name does not sufficiently match your registered name or business name."
            )
        
        # create transfer recipient
        recipient_code = create_transfer_recipient(account_name, account_number, bank_code)

        # save / update bank details
        seller, created = SellersBankDetails.objects.update_or_create(
            seller=user,
            defaults={
                "bank_name": bank_name,
                "account_name": account_name,
                "account_number": account_number,
                "bank_code": bank_code,
                "recipient_code": recipient_code,
            }
        )

        return Response({
            "status": "success",
            "status_code": status.HTTP_200_OK,
            "message": "Bank details updated and verified successfully",
            "account_name": account_name
        }, status=status.HTTP_200_OK)


class ConfirmWithdrawalView(APIView, BaseResponseMixin):
    """Class to handle sellers withdrawal"""
    permission_classes = [IsAuthenticated]
    authentication_classes = [CookieTokenAuthentication]


    @method_decorator(require_reauth)
    def post(self, request):
        """Post method for confirm withdrawal"""
        user = request.user

        seller_id = CustomUser.objects.get(id=user.id)
        seller_bank = SellersBankDetails.objects.get(seller=seller_id)

        # ===============Commented out for testing===================
        # Check for existing payout
        exists = Payout.objects.filter(
            seller=seller_id,
            status=Payout.StatusChoices.PROCESSING
        ).exists()

        if exists:
            return self.get_response(
                status.HTTP_400_BAD_REQUEST,
                "You have an already processing withdrawal"
            )
        
        if not seller_bank.recipient_code:
            return self.get_response(
                status.HTTP_400_BAD_REQUEST,
                "Seller does not have a recipient code. Please verify your bank details"
            )

        payout = initiate_payout(seller_bank.recipient_code, seller_id)

       
        bank_data = PayoutSerializer(payout).data

        data = {
            "amount_withdrawn": payout.amount_naira,
            "bank_data": bank_data
        }

        return self.get_response(
            status.HTTP_200_OK,
            "Withdrawal is successful and processing",
            data
        )



class SellerBankDetailView(GenericAPIView, BaseResponseMixin):
    """
    Class to get seller bank details as well as
    total revenue and withdrawable revenue
    """
    serializer_class = SellersBankDetailsSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [CookieTokenAuthentication]

    def get_bank_data(self):
        return get_object_or_404(SellersBankDetails, seller=self.request.user)
    
    def get(self, request):
        """Get seller bank detail and revenue"""
        bank_data = self.get_bank_data()
        serializer = self.get_serializer(bank_data)

        return self.get_response(
            status.HTTP_200_OK,
            "Seller bank and revenue details retrieved successfully",
            serializer.data
        )
    

class InitiateWithdrawalView(APIView, BaseResponseMixin):
    """
    Class to display initial withdraw view with details
    of seller 
        - total withdrawable revenue
        - commission
        - amount to withdraw
    """

    permission_classes = [IsAuthenticated]
    authentication_classes = [CookieTokenAuthentication]

    def get(self, request):
        """Get seller withdrawal overview"""
        seller = request.user

        try:
            shop = Shop.objects.get(owner=seller.kyc)
        except Shop.DoesNotExist:
            return self.get_response(
                status.HTTP_404_NOT_FOUND,
                "Seller not found for this witdrawal"
            )
    
        withdrawable = get_withdrawable_revenue(shop.id)

        if withdrawable <= 0:
            raise ValidationError("No withdrawable balance available.")

        withdrawable = Decimal(str(withdrawable))
        commission = (withdrawable * Decimal("0.05")).quantize(Decimal("0.01"))
        amount_naira = withdrawable - commission
        
        user = CustomUser.objects.get(id=seller.id, is_seller=True)

        bank = SellersBankDetails.objects.get(seller=user)

        # Get back data
        bank_data = SellerBankDataSerializer(bank).data

        data = {
            "total_amount": withdrawable,
            "commission": commission,
            "amount_naira": amount_naira,
            "bank_data": bank_data
        }

        return Response({
            "status": "success",
            "status_code": status.HTTP_200_OK,
            "message": "withdrawal information retrieve successfully",
            "data": data
        }, status=status.HTTP_200_OK)
    

class SingleSellerPayoutView(GenericAPIView, BaseResponseMixin):
    """Class to display seller payout data by payout id"""
    permission_classes = [IsAuthenticated]
    authentication_classes = [CookieTokenAuthentication]
    serializer_class = PayoutSerializer


    def get(self, request, payout_id):
        """Get method to retrieve seller payour data by id"""

        seller = request.user

        payout_id = validate_uuid(payout_id)

        if not payout_id:
            return self.get_response(
                status.HTTP_400_BAD_REQUEST,
                "Please provide the payout id"
            )
        
        payout = Payout.objects.get(id=payout_id, seller=seller)
        serializer = self.get_serializer(payout)

        return self.get_response(
            status.HTTP_200_OK,
            "withdrawal data",
            serializer.data
        )


class SingleTransactionHistoryView(GenericAPIView, BaseResponseMixin):
    """Class to handle the retrieval of a single transaction history"""
    serializer_class = SellerTransactionHistorySerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [CookieTokenAuthentication]


    def get(self, request, transaction_id):
        """Retrieve single transaction detail"""
        seller = request.user

        transaction_id = validate_uuid(transaction_id)

        if not transaction_id:
            return self.get_response(
                status.HTTP_400_BAD_REQUEST,
                "Please provide a correct transaction id"
            )

        try:
            data = SellerTransactionHistory.objects.get(id=transaction_id, seller=seller)
        except SellerTransactionHistory.DoesNotExist:
            return self.get_response(
                status.HTTP_404_NOT_FOUND,
                "Transaction with this id does not exists"
            )
        
        serializer = self.get_serializer(data)

        return self.get_response(
            status.HTTP_200_OK,
            "Transaction detail retrieved successfully",
            serializer.data
        )
    

class AllBankDataView(GenericAPIView, BaseResponseMixin):
    """
    Class to handle the retrieval of all bank data
    For frontend usage
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [CookieTokenAuthentication]
    serializer_class = BankSerializer

    def get_queryset(self):
        return Bank.objects.all()
    

    def get(self, request):
        """API to display different bank"""
        query = self.get_queryset()
        serializer = self.get_serializer(query, many=True)

        return self.get_response(
            status.HTTP_200_OK,
            "Bank data retrieved successfully",
            serializer.data
        )
