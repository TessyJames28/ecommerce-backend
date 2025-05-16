from rest_framework import serializers
from .models import Order, OrderItem
from carts.models import Cart, CartItem


class OrderItemSerializer(serializers.ModelSerializer):
    """Serializer for Order Item model"""
    total_price = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = ['id', 'variant', 'quantity', 'unit_price', 'total_price']


    def get_total_price(self, obj):
        return obj.total_price
    

class OrderSerializer(serializers.ModelSerializer):
    """Serializer for order model"""
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = ['id', 'user', 'created_at', 'status', 'total_amount', 'items']