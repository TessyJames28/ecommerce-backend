from rest_framework import serializers
from .models import Order, OrderItem, OrderReturnRequest
from users.serializers import ShippingAddressSerializer
from users.models import ShippingAddress


class OrderItemSerializer(serializers.ModelSerializer):
    """Serializer for Order Item model"""
    total_price = serializers.SerializerMethodField()
    product = serializers.SerializerMethodField()
    variant_detail = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = [
            'id', 'variant', 'quantity', 'unit_price', 'total_price',
            'product', 'delivered_at', 'is_completed', 'is_returned',
             'is_return_requested', 'variant_detail'
        ]


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
            'slug': product.slug,
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
    user_email = serializers.SerializerMethodField()
    shipping_address = serializers.DictField(write_only=True, required=False)

    class Meta:
        model = Order
        fields = [
            'id', 'user', 'user_email', 'created_at', 'updated_at', 'status',
            'total_amount', 'items', 'shipping_address'
        ]
        read_only_fields = ['user', 'total_amount', 'status', 'created_at', 'items', 'user_email']

    def get_user_email(self, obj):
        return obj.user.email
    

    # def get_shipping_address(self, obj):
    #     """
    #     Get the shipping address data from the order
    #     Group them under shipping_address in the response
    #     """
    #     fields = [
    #         'street_address', 'local_govt', 'landmark',
    #         'country', 'state', 'phone_number'
    #     ]

    #     address_data = {}
    #     for field in fields:
    #         address_data[field] = getattr(obj, field, None)
    #     # Return None if all fields are empty
    #     if not any(address_data.values()):
    #         return None
    #     return address_data
    

    def to_representation(self, instance):
        data = super().to_representation(instance)

        address_fields = [
            'street_address', 'local_govt', 'landmark',
            'country', 'state', 'phone_number'
        ]
        data['shipping_address'] = {
            field: getattr(instance, field, None) for field in address_fields
        }

        # Optional: Return None if all values are None
        if not any(data['shipping_address'].values()):
            data['shipping_address'] = None

        return data

    

    def update(self, instance, validated_data):
        """Allow the user to set shipping address only once during first checkout"""
        shipping_address_data = validated_data.pop('shipping_address', None)
        print(shipping_address_data)

        # Check that the order status is still pending
        if instance.status != Order.Status.PENDING:
            raise serializers.ValidationError("Address can only be updated when status is pending.")
        
        user = instance.user

        # Update base Order fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Update shipping address when provided or changed by timers
        if shipping_address_data:
            ShippingAddress.objects.update_or_create(
                user=user,
                defaults=shipping_address_data
            )

            # Copy data into the order snapshot fields
            # address_fields = [
            #     'street_address', 'local_govt', 'landmark',
            #     'country', 'state', 'phone_number'
            # ]
            for field in [
                'street_address', 'local_govt', 'landmark',
                'country', 'state', 'phone_number'
            ]:
                value = shipping_address_data.get(field)
                if value:
                    setattr(instance, field, value) 
            instance.save()

        return instance
    

class OrderReturnRequestSerializer(serializers.ModelSerializer):
    """Serializer for order return request"""
    order = OrderSerializer()

    class Meta:
        model = OrderReturnRequest
        fields = "__all__"