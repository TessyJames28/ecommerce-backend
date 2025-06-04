from rest_framework import serializers
from .models import Order, OrderItem
from carts.models import Cart, CartItem
from carts.serializers import CartItemSerializer


class OrderItemSerializer(serializers.ModelSerializer):
    """Serializer for Order Item model"""
    total_price = serializers.SerializerMethodField()
    product = serializers.SerializerMethodField()
    variant_detail = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = ['id', 'variant', 'quantity', 'unit_price', 'total_price', 'product', 'variant_detail']


    def get_product(self, obj):
        """Get product"""
        product = obj.variant.product

        # Retrieve product image
        image_url = None
        if hasattr(product, 'images'):
            images = product.images.all()
            if images.exists():
                image_url = images.first().url

        return {
            'id': str(product.id),
            'title': product.title,
            'price': str(product.price),
            'category': product.category.name if hasattr(product, 'category') else None,
            'subcategory': product.sub_category.name if hasattr(product, 'sub_category') else None,
            'type': product.__class__.__name__,
            'image': image_url
        }
    
    def get_variant_detail(self, obj):
        variant = obj.variant

        if variant.standard_size:
            custom_size = obj.variant.standard_size
        elif variant.custom_size_value:
            custom_size = obj.variant.custom_size_value
        else:
            custom_size = None

        return {
            'id': str(variant.id),
            'color': variant.color,
            'custom_size_unit': variant.custom_size_unit,
            'custom_size': custom_size,
            'stock_quantity': variant.stock_quantity,
            'price_override': str(variant.price_override) if variant.price_override else None
        }

    def get_total_price(self, obj):
        return obj.total_price
    

class OrderSerializer(serializers.ModelSerializer):
    """Serializer for order model"""
    items = OrderItemSerializer(many=True, read_only=True, source='order_items')

    class Meta:
        model = Order
        fields = ['id', 'user', 'created_at', 'status', 'total_amount', 'items']


    def get_items(self, obj):
        """Retrieve all order items"""
        return OrderItemSerializer(obj.order_items.all(), many=True).data