from rest_framework import serializers
from .models import Cart, CartItem
from products.utility import product_models
from django.contrib.contenttypes.models import ContentType
from products.models import (
    BabyProduct, VehicleProduct, FashionProduct, ProductVariant,
    ElectronicsProduct, AccessoryProduct, FoodProduct,
    HealthAndBeautyProduct, GadgetProduct, Color, SizeOption
)


class CartItemSerializer(serializers.ModelSerializer):
    """Serializer for cart item"""
    item_total_price = serializers.SerializerMethodField()
    product = serializers.SerializerMethodField()
    variant_detail = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = ['id', 'variant', 'quantity', 'item_total_price', 'product', 'variant_detail']
        read_only_fields = ['id', 'variant', 'quantity', 'item_total_price', 'product', 'variant_detail']
    

    def get_product(self, obj):
        """Get product"""
        product = obj.variant.product
        return {
            'id': str(product.id),
            'title': product.title,
            'price': str(product.price),
            'category': product.category.name,
            'type': product.__class__.__name__
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
    

    def get_item_total_price(self, obj):
        return obj.item_total_price
    

class CartSerializer(serializers.ModelSerializer):
    """Serializer for the cart model"""
    items = CartItemSerializer(many=True, read_only=True)
    total_price = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = ['id', 'user', 'created_at', 'items', 'total_price']
        read_only_fields = ['id', 'user', 'created_at', 'items', 'total_price']


    def get_total_price(self, obj):
        return obj.total_price
    

class CartItemCreateSerializer(serializers.Serializer):
    """Handles the creation of cart items based on existing product"""
    product_id = serializers.UUIDField()
    color = serializers.ChoiceField(choices=Color.choices)
    standard_size = serializers.ChoiceField(choices=SizeOption.StandardSize.choices, required=True)
    custom_size_unit = serializers.ChoiceField(choices=SizeOption.SizeUnit.choices, required=True)
    custom_size_value = serializers.DecimalField(max_digits=5, decimal_places=2, required=True)


    def validate(self, data):
        """Validate product in the cart"""
        product = None
        for model in product_models:
            try:
                product = model.objects.get(id=data['product_id'])
                break
            except model.DoesNotExist:
                continue

        
        if not product:
            raise serializers.ValidationError("Product not found")
        

        content_type = ContentType.objects.get_for_model(product)
        variant = ProductVariant.objects.filter(
            content_type=content_type,
            object_id=product.id,
            color=data['color'],
            standard_size=data.get('standard_size'),
            custom_size_unit=data.get('custom_size_unit'),
            custom_size_value=data.get('custom_size_value'),
        ).first()

        if not variant:
            raise serializers.ValidationError("No matching variant found")
        
        if variant.stock_quantity < data['quantity']:
            raise serializers.ValidationError("Insufficient stock for this product variant")
        
        data['variant'] = variant
        return data
    


    def create(self, validated_data):
        """Create cart using existing product"""
        user = self.context['request'].user
        cart, _ = Cart.objects.get_or_create(user=user)
        variant = validated_data['variant']
        quantity = validated_data['quantity']

        cart_item, created = CartItem.objects.get_or_create(cart=cart, variant=variant)
        if not created:
            cart_item.quantity += quantity
        else:
            cart_item.quantity = quantity


        cart_item.save()
        return cart_item