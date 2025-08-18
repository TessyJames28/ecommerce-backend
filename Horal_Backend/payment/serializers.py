from rest_framework import serializers
from .models import PaystackTransaction
from orders.serializer import OrderSerializer


class PaystackTransactionSerializer(serializers.ModelSerializer):
    """Serializer to serialize the PaystackTransaction model"""
    order = OrderSerializer()

    class Meta:
        model = PaystackTransaction
        fields = "__all__"
        