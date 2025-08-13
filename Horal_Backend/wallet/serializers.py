from rest_framework import serializers
from collections import defaultdict
from datetime import date, timedelta
from .models import SellersBankDetails, Payout, SellerTransactionHistory, Bank
from sellers_dashboard.utils import (
    get_total_revenue,
    get_withdrawable_revenue
)
from shops.models import Shop


class SellerTransactionHistorySerializer(serializers.ModelSerializer):
    """Serializer to serialize seller transaction history"""
    class Meta:
        model = SellerTransactionHistory
        fields = "__all__"


class GroupedSellerTransactionHistorySerializer(serializers.Serializer):
    """
    Serializer to handle the grouping of transaction
    history for sellers
    """
    date = serializers.CharField()
    transactions = SellerTransactionHistorySerializer(many=True)


    def get_grouped_transaction_history(self, seller):
        """
        Get all transcation history grouped per day
        ordered from newest first
        """
        transactions = SellerTransactionHistory.objects.filter(
            seller=seller
        ). order_by('-created_at')

        grouped_data = defaultdict(list)

        for tx in transactions:
            tx_date = tx.created_at.date()
            today = date.today()

            if tx_date == today:
                label = "Today"
            elif tx_date == today - timedelta(days=1):
                label = "Yesterday"
            else:
                label = tx_date.strftime("%d %B %Y")
            
            grouped_data[label].append(tx)

        # Convert to serializer-friendly format
        result = []
        for label, tx_list in grouped_data.items():
            result.append({
                "data": label,
                "transactions": SellerTransactionHistorySerializer(tx_list, many=True).data
            })

        return result


class SellersBankDetailsSerializer(serializers.ModelSerializer):
    """Serializer for sellers bank details"""
    total_revenue = serializers.SerializerMethodField()
    withdraw = serializers.SerializerMethodField()
    transaction_history = serializers.SerializerMethodField()

    class Meta:
        model = SellersBankDetails
        fields = [
            "bank_name", "account_number", "account_name",
            "total_revenue", "withdraw", "transaction_history"
        ]

    def get_total_revenue(self, obj):
        shop = Shop.objects.get(owner=obj.seller.kyc)
        return get_total_revenue(shop.id)
    
    def get_withdraw(self, obj):
        shop = Shop.objects.get(owner=obj.seller.kyc)
        return get_withdrawable_revenue(shop.id)
    
    def get_transaction_history(self, obj):
        grouped_data = GroupedSellerTransactionHistorySerializer()
        return grouped_data.get_grouped_transaction_history(obj.seller)


class SellerBankDataSerializer(serializers.ModelSerializer):
    """Serializer for sellers bank details"""

    class Meta:
        model = SellersBankDetails
        fields = [
            "bank_name", "account_number", "account_name",
        ]


class PayoutSerializer(serializers.ModelSerializer):
    """Serializer for payout model"""
    bank_data = serializers.SerializerMethodField()
    class Meta:
        model = Payout
        fields = "__all__"


    def get_bank_data(self, obj):
        data = SellersBankDetails.objects.get(seller=obj.seller)
        bank_data = SellerBankDataSerializer(data).data
        return bank_data


class BankSerializer(serializers.ModelSerializer):
    """Serializes bank data"""

    class Meta:
        model = Bank
        fields = ["name", "slug", "active"]
