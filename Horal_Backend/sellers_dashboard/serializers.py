from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from .models import ProductRatingSummary
from shops.serializers import ShopSerializer
from orders.models import OrderItem
from products.serializers import ProductVariantSerializer
from sellers.models import SellerKYC
from sellers.serializers import SellerSerializer
from users.serializers import ShippingAddressSerializer
from user_profile.models import Profile, Image
import logging

logger = logging.getLogger(__name__)


class ProductRatingSummarySerializer(serializers.ModelSerializer):
    """
    Serializer to aggregate ratings across sellers listed products
    """
    product = serializers.UUIDField(source='product.id')
    average_rating = serializers.FloatField()
    total_ratings = serializers.IntegerField()
    created_at = serializers.DateTimeField(source='product.created_at')

    # For product metadata
    title = serializers.SerializerMethodField()
    images = serializers.SerializerMethodField()

    class Meta:
        model = ProductRatingSummary
        fields = [
            'product', 'title', 'images', 'average_rating',
            'total_ratings', 'created_at'
        ]

    
    def get_title(self, obj):
        return getattr(obj.product.linked_product, 'title', '')
    

    def get_images(self, obj):
        """Retrieve product image"""
        linked_product = obj.product.linked_product
        if hasattr(linked_product, 'images'):
            first_image = linked_product.images.first()
            if first_image and hasattr(first_image, 'url'):
                return first_image.url
        return None
    

class SellerProductRatingsSerializer(serializers.Serializer):
    shop = ShopSerializer()
    reviews = ProductRatingSummarySerializer(many=True)


class SellerOrderItemSerializer(serializers.ModelSerializer):
    """
    Serializer to retrieve all orders for a specific seller
    """
    title = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()
    buyer = serializers.CharField(source="order.user.full_name")
    order_id = serializers.UUIDField(source="order.id")
    shipment_id = serializers.UUIDField(source="shipment.id")
    price = serializers.SerializerMethodField()
    order_date = serializers.DateTimeField(source='order.created_at')
    order_status = serializers.CharField(source='order.status')
    shipment_status = serializers.CharField(source='shipment.status')
    variant = ProductVariantSerializer()


    class Meta:
        model = OrderItem
        fields = [
            'id', 'title', 'image', 'buyer', 'order_id', 'shipment_id', 'unit_price', 'price',
            'order_date', 'order_status', 'shipment_status', 'quantity', 'is_returned',
            'is_return_requested', 'is_completed', 'delivered_at', 'variant'
        ]

    def get_title(self, obj):
        return getattr(obj.variant.product, 'title', None)
    
    def get_image(self, obj):
        product = obj.variant.product
        return getattr(product.images.first(), 'url', None)
    
    def get_price(self, obj):
        return obj.total_price
    

class SellerProductOrdersSerializer(serializers.Serializer):
    shop = ShopSerializer()
    orders = SellerOrderItemSerializer(many=True)


class SellerProfileSerializer(serializers.ModelSerializer):
    image = serializers.CharField(required=False)
    kyc_data = SellerSerializer(source="user.kyc")
    shop = serializers.SerializerMethodField()
    shipping_address = ShippingAddressSerializer(read_only=True)
    phone_number = serializers.CharField(source='user.phone_number')
    is_seller = serializers.CharField(source="user.is_seller", read_only=True)

    class Meta:
        model = Profile
        fields = [
            'user', 'full_name', 'email', 'phone_number', 'is_seller', 'image',
            'kyc_data', 'shop', 'shipping_address'
        ]
        read_only_fields = ['id', 'is_seller', 'shop']

    def get_shop(self, obj):
        try:
            return ShopSerializer(obj.user.kyc.owner.first()).data
        except Exception as e:
            logger.warning(f"Error occurred when fetching shop in seller profile serializer: {e}")
            return None
    

    def update(self, instance, validated_data):
        # Update base CustomUser fields
        user_data = validated_data.pop("user", {})
        phone_number = user_data.get("phone_number")
        kyc_data = user_data.get("kyc", {})

        address_data = kyc_data.get("address")
        socials_data = kyc_data.get("socials")

        image_url = validated_data.pop("image", None)

        # Raise error if KYC contains disallowed fields
        allowed_keys = {"address", "socials"}
        kyc_keys = set(kyc_data.keys())

        disallowed_keys = kyc_keys - allowed_keys
        if disallowed_keys:
            raise ValidationError({
                "kyc": f"You are not allowed to update the following fields: {', '.join(disallowed_keys)}"
            })

        user = instance.user

        if phone_number:
            user.phone_number = phone_number
            user.save(update_fields=["phone_number"])

        if image_url:
            image_obj, _ = Image.objects.update_or_create(
                url=image_url,
            )
            instance.image = image_obj

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Get seller kyc data
        seller_kyc = SellerKYC.objects.get(user=user)
        address = seller_kyc.address
        socials = seller_kyc.socials

        if address_data:
            for attr, value in address_data.items():
                setattr(address, attr, value)
            address.save()

        # Update socials
        # socials_data = data.get("request")
        if socials_data:
            for attr, value in socials_data.items():
                setattr(socials, attr, value)
            socials.save()
    

        return instance
