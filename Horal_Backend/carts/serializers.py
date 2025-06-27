from rest_framework import serializers
from .models import Cart, CartItem
from django.contrib.contenttypes.models import ContentType
from products.models import (
    ChildrenProduct, VehicleProduct, FashionProduct, ProductVariant,
    ElectronicsProduct, AccessoryProduct, FoodProduct,
    HealthAndBeautyProduct, GadgetProduct, Color, SizeOption
)
from products.serializers import MixedProductSerializer

product_models = [
    ChildrenProduct,
    VehicleProduct,
    FashionProduct,
    GadgetProduct,
    ElectronicsProduct,
    AccessoryProduct,
    FoodProduct,
    HealthAndBeautyProduct
]



class CartItemSerializer(serializers.ModelSerializer):
    """Serializer for cart item"""
    item_total_price = serializers.SerializerMethodField()
    product = serializers.SerializerMethodField()
    user_selected_variant = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = ['id', 'variant', 'quantity', 'item_total_price', 'product', 'user_selected_variant']
        read_only_fields = ['id', 'variant', 'quantity', 'item_total_price', 'product']
    

    def get_product(self, obj):
        """Get product"""
        product = obj.variant.product
        if not product:
            return None  # or a fallback serializer/data
        try:
            return MixedProductSerializer().to_representation(product)
        except Exception as e:
            print(f"Error serializing product: {e}")
            return None


    def get_user_selected_variant(self, obj):
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
    items = CartItemSerializer(many=True, read_only=True, source='cart_item')
    total_price = serializers.SerializerMethodField()
    total_item = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = ['id', 'created_at', 'total_item', 'items', 'total_price']
        read_only_fields = ['id', 'created_at', 'items', 'total_price']


    def get_total_price(self, obj):
        return obj.total_price
    
    def get_total_item(self, obj):
        return obj.total_item
    

class CartItemCreateSerializer(serializers.Serializer):
    """Handles the creation of cart items based on existing product"""
    product_id = serializers.UUIDField()
    color = serializers.ChoiceField(choices=Color.choices, required=False, allow_null=True)
    quantity = serializers.IntegerField(default=1, min_value=1)
    standard_size = serializers.ChoiceField(choices=SizeOption.StandardSize.choices, allow_null=True, required=False)
    custom_size_unit = serializers.ChoiceField(choices=SizeOption.SizeUnit.choices, allow_null=True, required=False)
    custom_size_value = serializers.DecimalField(max_digits=5, decimal_places=2, allow_null=True, required=False)


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
        filter_kwargs = {
            'content_type': content_type,
            'object_id': product.id,
        }

        # Conditionally include additional fields
        if data.get('standard_size') is not None:
            filter_kwargs['standard_size'] = data['standard_size']
        if data.get('custom_size_unit') is not None:
            filter_kwargs['custom_size_unit'] = data['custom_size_unit']
        if data.get('custom_size_value') is not None:
            filter_kwargs['custom_size_value'] = data['custom_size_value']
        if data.get('color') is not None:
            filter_kwargs['color'] = data['color']
       
        variant = ProductVariant.objects.filter(**filter_kwargs).first()

        if not variant:
            raise serializers.ValidationError("No matching variant found")
        
        if variant.stock_quantity < data.get('quantity', 1):
            raise serializers.ValidationError("Insufficient stock for this product variant")
        
        data['variant'] = variant
        return data
    


    def create(self, validated_data):
        """Create cart item for authenticated or anonymous users"""
        request = self.context['request']

        # Use the cart provided in context (if available) or get from request
        cart = self.context.get('cart')
        if not cart:
            # Get or create cart based on user authentication status
            if request.user.is_authenticated:
                cart, _ = Cart.objects.get_or_create(user=request.user)
            else:
                session_key = request.session.session_key
                if not session_key:
                    request.session.create()
                    session_key = request.session.session_key

                cart, _ = Cart.objects.get_or_create(session_key=session_key)

        variant = validated_data['variant']
        quantity = validated_data['quantity']

        # Check if the item already exists in the cart
        cart_item, created = CartItem.objects.get_or_create(
            cart=cart,
            variant=variant,
            defaults={'quantity': quantity}
        )

        if not created:
            cart_item.quantity += quantity
            # Ensure stock quantity is not exceeded
            if cart_item.quantity > cart_item.variant.stock_quantity:
                cart_item.quantity = cart_item.variant.stock_quantity
            cart_item.save()

        return cart_item