from rest_framework import serializers
from .models import (
    Category, ImageLink, ProductVariant, SizeOption,
    Shop, BabyProduct, VehicleProduct, GadgetProduct,
    FashionProduct, ElectronicsProduct, AccessoryProduct,
    HealthAndBeautyProduct, FoodProduct
)


class ImageLinkSerializer(serializers.ModelSerializer):
    """Image serializer to handle adding image link to the db"""
    class Meta:
        model = ImageLink
        fields = ['id', 'url', 'alt_text']
        read_only_fields = ['id']


class CategorySerializer(serializers.ModelSerializer):
    """Serializer for category creation"""
    class Meta:
        model = Category
        fields = '__all__'
        read_only_fields = ['id']

class ProductVariantSerializer(serializers.ModelSerializer):
    """Serializer for product variant model which include sizes and colors."""
    class Meta:
        model = ProductVariant
        fields = [
            'id', 'color', 'custom_size_unit', 'standard_size',
            'custom_size_value', 'stock_quantity', 'price_override'
        ]
        read_only_fields = ['id']


class ProductCreateMixin:
    def create(self, validated_data):
        images = validated_data.pop('images', [])
        variants = validated_data.pop('variants', [])
        instance = self.Meta.model.objects.create(**validated_data)

        # create and save image in image model
        for img in images:
            image = ImageLink.objects.create(**img)
            instance.images.add(image)


        # Create variants
        for data in variants:
            ProductVariant.objects.create(product=instance, **data)

        return instance
    

class BaseProductSerializer(serializers.ModelSerializer):
    """Serializer for the base product model"""
    images = ImageLinkSerializer(many=True)
    variants = ProductVariantSerializer(many=True, write_only=True, required=False)
    variants_details = serializers.SerializerMethodField(read_only=True)

    def get_variants_details(self, obj):
        variant_qs = obj.get_variants() # defined in BaseProduct
        return ProductVariantSerializer(variant_qs, many=True).data

    def validate_images(self, value):
        if not value:
            raise serializers.ValidationError("At least one image is required.")
        return value
    

# Pre-category product serializers
class BabyProductSerializer(ProductCreateMixin, BaseProductSerializer):
    """Serializer to handle baby category"""
    class Meta:
        model = BabyProduct
        fields = '__all__'
        read_only_fields = ['id']
    

class VehicleProductSerializer(ProductCreateMixin, BaseProductSerializer):
    """serializer to handle vehicle product category creation"""
    class Meta:
        model = VehicleProduct
        fields = '__all__'
        read_only_fields = ['id']
    

class GadgetProductSerializer(ProductCreateMixin, BaseProductSerializer):
    """serializer for Gadget product model creation"""
    class Meta:
        model = GadgetProduct
        fields = '__all__'
        read_only_fields = ['id']


class FashionProductSerializer(ProductCreateMixin, BaseProductSerializer):
    """Serializer to handle fashion category product creation"""
    class Meta:
        model = FashionProduct
        fields = '__all__'
        read_only_fields = ['id']


class ElectronicsProductSerializer(ProductCreateMixin, BaseProductSerializer):
    """serializer to handle electronics product category creation"""
    class Meta:
        model = ElectronicsProduct
        fields = '__all__'
        read_only_fields = ['id']


class AccessoryProductSerializer(ProductCreateMixin, BaseProductSerializer):
    """Serializer to handle Accesory product category creation"""
    class Meta:
        model = AccessoryProduct
        fields = '__all__'
        read_only_fields = ['id']


class HealthAndBeautyProductSerializer(ProductCreateMixin, BaseProductSerializer):
    """
    Serializer to handle the creation of health 
    and beauty products category
    """
    class Meta:
        model = HealthAndBeautyProduct
        fields = '__all__'
        read_only_fields = ['id']


class FoodProductSerializer(ProductCreateMixin, BaseProductSerializer):
    """serializer to handle Food product category creation"""
    class Meta:
        model = FoodProduct
        fields = '__all__'
        read_only_fields = ['id']


# Dynamic serializer solver (for views)
def get_product_serializer(category_name):
    mapping = {
        'babies': BabyProductSerializer,
        'vehicles': VehicleProductSerializer,
        'gadget': GadgetProductSerializer,
        'fashion': FashionProductSerializer,
        'electronics': ElectronicsProductSerializer,
        'accessories': AccessoryProductSerializer,
        'health and beauty': HealthAndBeautyProductSerializer,
        'foods': FoodProductSerializer
    }

    return mapping.get(category_name.lower())