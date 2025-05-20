from rest_framework import serializers
from .models import (
    AccessorySubCategory, Category, ChildrenProduct,
    ChildrenSubCategory, ElectronicsSubCategory,
    FashionSubCategory, GadgetSubCategory, ImageLink,
    Occasion, ProductVariant, SubCategory, VehicleProduct, GadgetProduct,
    FashionProduct, ElectronicsProduct, AccessoryProduct,
    HealthAndBeautyProduct, FoodProduct, BaseProduct
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


class SubCategorySerializer(serializers.ModelSerializer):
    """Class that handles subcategory serialization"""

    class Meta:
        model = SubCategory 
        fields = ['id', 'name', 'slug', 'category']


class ProductVariantSerializer(serializers.ModelSerializer):
    """Serializer for product variant model which include sizes and colors."""
    class Meta:
        model = ProductVariant
        fields = [
            'id', 'color', 'custom_size_unit', 'standard_size',
            'custom_size_value', 'stock_quantity', 'reserved_quantity', 'price_override'
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

        # Update product quantity based on stock
        from .utility import update_quantity
        update_quantity(instance)

        return instance
    

    def update(self, instance, validated_data):
        """
        Product update especially for nested fields like images and variants
        """
        images = validated_data.pop('images', [])
        variants = validated_data.pop('variants', [])

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if images:
            instance.images.clear()
            for img in images:
                image = ImageLink.objects.create(**img)
                instance.images.add(image)

        if variants:
            instance.get_variants().delete()
            for data in variants:
                ProductVariant.objects.create(product=instance, **data)

        # Update product quantity based on stock
        from .utility import update_quantity
        update_quantity(instance)

        return instance 
    

class ProductRepresentationMixin:
    def to_representation(Self, instance):
        """Centralize the to_representation logic"""
        from .utility import update_quantity
        update_quantity(instance)
        data = super().to_representation(instance)

        # List of base_field attributes
        base_fields = {
            'id', 'title', 'description', 'price', 'quantity',
            'production_date', 'condition', 'brand',
            'is_published', 'live_video_url', 'created_at',
            'updated_at', 'images', 'shop', 'category'
        }

        base_data = {}
        spec_data = {}

        for key, value in data.items():
            if key in base_fields or key == "images":
                base_data[key] = value
            elif key == "state" or key == "local_govt":
                base_data[key] = value
            else:
                spec_data[key] = value

        return {
            **base_data,
            "specification": spec_data
        }
    

class BaseProductSerializer(serializers.ModelSerializer):
    """Serializer for the base product model"""
    images = ImageLinkSerializer(many=True)
    variants = ProductVariantSerializer(many=True, write_only=True, required=False)
    variants_details = serializers.SerializerMethodField(read_only=True)
    quantity = serializers.SerializerMethodField()
    
    def get_variants_details(self, obj):
        variant_qs = obj.get_variants() # defined in BaseProduct
        return ProductVariantSerializer(variant_qs, many=True).data

    def validate_images(self, value):
        if not value:
            raise serializers.ValidationError("At least one image is required.")
        return value
    
    def get_quantity(self, obj):
        return obj.quantity
    
    # def get_location(self, obj):
    #     if obj.location:
    #         return {
    #             "id": str(obj.location.id),
    #             "state": obj.location.state,
    #             "local_govt": obj.location.local_govt,
    #             "landmark": obj.location.landmark,
    #             "street_address": obj.location.street_address,
    #         }
    #     return None

    

# Pre-category product serializers
class ChildrenProductSerializer(
    ProductCreateMixin,
    ProductRepresentationMixin,
    BaseProductSerializer
):

    sub_category = serializers.ChoiceField(choices=ChildrenSubCategory.choices)

    """Serializer to handle baby category"""
    class Meta:
        model = ChildrenProduct
        fields = '__all__'
        read_only_fields = ['id']
    

class VehicleProductSerializer(
    ProductCreateMixin,
    ProductRepresentationMixin,
    BaseProductSerializer
):
    
    """serializer to handle vehicle product category creation"""
    class Meta:
        model = VehicleProduct
        fields = '__all__'
        read_only_fields = ['id']
    

class GadgetProductSerializer(
    ProductCreateMixin,
    ProductRepresentationMixin,
    BaseProductSerializer
):
    sub_category = serializers.ChoiceField(choices=GadgetSubCategory.choices)
    
    """serializer for Gadget product model creation"""
    class Meta:
        model = GadgetProduct
        fields = '__all__'
        read_only_fields = ['id']


class OccasionSerializer(serializers.ModelSerializer):
    """Occasion Serializer"""
    class Meta:
        model = Occasion 
        fields = ['id', 'name']


class FashionProductSerializer(
    ProductCreateMixin,
    ProductRepresentationMixin,
    BaseProductSerializer
):
    """Serializer to handle fashion category product creation"""
    sub_category = serializers.ChoiceField(choices=FashionSubCategory.choices)
    occasions = OccasionSerializer(many=True, read_only=True)

    class Meta:
        model = FashionProduct
        fields = '__all__'
        read_only_fields = ['id']


class ElectronicsProductSerializer(
    ProductCreateMixin,
    ProductRepresentationMixin,
    BaseProductSerializer
):
    """serializer to handle electronics product category creation"""
    sub_category = serializers.ChoiceField(choices=ElectronicsSubCategory.choices)

    class Meta:
        model = ElectronicsProduct
        fields = '__all__'
        read_only_fields = ['id']


class AccessoryProductSerializer(
    ProductCreateMixin,
    ProductRepresentationMixin,
    BaseProductSerializer
):
    """Serializer to handle Accesory product category creation"""
    sub_category = serializers.ChoiceField(choices=AccessorySubCategory.choices)

    class Meta:
        model = AccessoryProduct
        fields = '__all__'
        read_only_fields = ['id']


class HealthAndBeautyProductSerializer(
    ProductCreateMixin,
    ProductRepresentationMixin,
    BaseProductSerializer
):
    """
    Serializer to handle the creation of health 
    and beauty products category
    """
    class Meta:
        model = HealthAndBeautyProduct
        fields = '__all__'
        read_only_fields = ['id']


class FoodProductSerializer(
    ProductCreateMixin,
    ProductRepresentationMixin,
    BaseProductSerializer
):
    """serializer to handle Food product category creation"""
    class Meta:
        model = FoodProduct
        fields = '__all__'
        read_only_fields = ['id']


# Dynamic serializer solver (for views)
def get_product_serializer(category_name):
    mapping = {
        'children': ChildrenProductSerializer,
        'vehicles': VehicleProductSerializer,
        'gadget': GadgetProductSerializer,
        'fashion': FashionProductSerializer,
        'electronics': ElectronicsProductSerializer,
        'accessories': AccessoryProductSerializer,
        'health and beauty': HealthAndBeautyProductSerializer,
        'foods': FoodProductSerializer
    }

    return mapping.get(category_name.lower())