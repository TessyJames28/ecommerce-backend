from rest_framework import serializers
from django.db.models import Q
from .models import (
    ChildrenProduct, ImageLink,
    Occasion, ProductVariant, VehicleProduct, GadgetProduct,
    FashionProduct, ElectronicsProduct, AccessoryProduct,
    HealthAndBeautyProduct, FoodProduct,
)
from categories.serializers import CategorySerializer
from subcategories.serializers import SubCategoryProductSerializer
from categories.models import Category
from subcategories.models import SubCategory


class ImageLinkSerializer(serializers.ModelSerializer):
    """Image serializer to handle adding image link to the db"""
    class Meta:
        model = ImageLink
        fields = ['id', 'url', 'alt_text']
        read_only_fields = ['id']


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
        names = validated_data.pop("occasion", [])

        instance = self.Meta.model.objects.create(**validated_data)

        # create and save image in image model
        for img in images:
            image = ImageLink.objects.create(**img)
            instance.images.add(image)


        # Create variants
        for data in variants:
            ProductVariant.objects.create(product=instance, **data)

        # Create occasion
        # Dynamic mapping of filtering
        occasion_query = Q()
        for name in names:
            occasion_query |= Q(name__iexact=name)
        if names:
            occasions = Occasion.objects.filter(occasion_query)
            instance.occasion.set(occasions)

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
    

class UniqueProductPerShopMixin:
    def validate(self, attrs):
        title = attrs.get('title')
        brand = attrs.get('brand')
        category = attrs.get('category')
        shop = attrs.get('shop')

        # skip validation if essential fields are missiing
        if not title or not shop or not category:
            return attrs
        
        model = self.Meta.model
        queryset = model.objects.filter(
            title=title, shop=shop,
            category=category
        )

        if brand is not None:
            queryset = queryset.filter(brand=brand)
        else:
            queryset = queryset.filter(brand__isnull=True)

        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)

        if queryset.exists():
            raise serializers.ValidationError({
                "non_field_errors": ["This product already existings and is being duplicated."]
            })
        
        return attrs
    

class ProductRepresentationMixin:
    def to_representation(self, instance):
        """Centralize the to_representation logic"""
        from .utility import update_quantity
        update_quantity(instance)
        data = super().to_representation(instance)
        data['category'] = CategorySerializer(instance.category).data
        data['sub_category'] = SubCategoryProductSerializer(instance.sub_category).data

        # List of base_field attributes
        base_fields = {
            'id', 'title', 'description', 'price', 'quantity',
            'production_date', 'condition', 'brand', 'specifications',
            'is_published', 'live_video_url', 'created_at',
            'updated_at', 'shop', 'state', 'local_govt'
        }

        cat_data = ['category', 'sub_category']

        fields = ["images", "variants_details"]

        base_data = {}
        spec_data = {}
        category_data ={}
        field_data = {}

        for key, value in data.items():
            if key in base_fields:
                base_data[key] = value
            elif key in fields:
                field_data[key] = value
            elif key in cat_data:
                category_data[key] = value
            else:
                spec_data[key] = value

        return {
            **base_data,
            **field_data,
            "category_object": category_data,
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
    

# Pre-category product serializers
class ChildrenProductSerializer(
    UniqueProductPerShopMixin,
    ProductCreateMixin,
    ProductRepresentationMixin,
    BaseProductSerializer
):

    """Serializer to handle baby category"""
    category = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all()
    )
    sub_category = serializers.PrimaryKeyRelatedField(
        queryset=SubCategory.objects.all()
    )

    class Meta:
        model = ChildrenProduct
        fields = '__all__'
        read_only_fields = ['id']
    

class VehicleProductSerializer(
    UniqueProductPerShopMixin,
    ProductCreateMixin,
    ProductRepresentationMixin,
    BaseProductSerializer
):
    
    """serializer to handle vehicle product category creation"""
    category = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all()
    )
    sub_category = serializers.PrimaryKeyRelatedField(
        queryset=SubCategory.objects.all()
    )

    class Meta:
        model = VehicleProduct
        fields = '__all__'
        read_only_fields = ['id']
    

class GadgetProductSerializer(
    UniqueProductPerShopMixin,
    ProductCreateMixin,
    ProductRepresentationMixin,
    BaseProductSerializer
):
    
    """serializer for Gadget product model creation"""
    category = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all()
    )
    sub_category = serializers.PrimaryKeyRelatedField(
        queryset=SubCategory.objects.all()
    )

    class Meta:
        model = GadgetProduct
        fields = '__all__'
        read_only_fields = ['id']


class OccasionSerializer(serializers.ModelSerializer):
    """Occasion Serializer"""
    class Meta:
        model = Occasion 
        fields = "__all__"


class FashionProductSerializer(
    UniqueProductPerShopMixin,
    ProductCreateMixin,
    ProductRepresentationMixin,
    BaseProductSerializer
):
    """Serializer to handle fashion category product creation"""
    category = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all()
    )
    sub_category = serializers.PrimaryKeyRelatedField(
        queryset=SubCategory.objects.all()
    )
    occasion = serializers.SlugRelatedField(
        queryset=Occasion.objects.all(),
        many=True,
        slug_field='name'  # we are matching by the "name" field
    )

    class Meta:
        model = FashionProduct
        fields = '__all__'
        read_only_fields = ['id']


class ElectronicsProductSerializer(
    UniqueProductPerShopMixin,
    ProductCreateMixin,
    ProductRepresentationMixin,
    BaseProductSerializer
):
    """serializer to handle electronics product category creation"""
    category = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all()
    )
    sub_category = serializers.PrimaryKeyRelatedField(
        queryset=SubCategory.objects.all()
    )

    class Meta:
        model = ElectronicsProduct
        fields = '__all__'
        read_only_fields = ['id']


class AccessoryProductSerializer(
    UniqueProductPerShopMixin,
    ProductCreateMixin,
    ProductRepresentationMixin,
    BaseProductSerializer
):
    """Serializer to handle Accesory product category creation"""
    category = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all()
    )
    sub_category = serializers.PrimaryKeyRelatedField(
        queryset=SubCategory.objects.all()
    )

    class Meta:
        model = AccessoryProduct
        fields = '__all__'
        read_only_fields = ['id']


class HealthAndBeautyProductSerializer(
    UniqueProductPerShopMixin,
    ProductCreateMixin,
    ProductRepresentationMixin,
    BaseProductSerializer
):
    """
    Serializer to handle the creation of health 
    and beauty products category
    """
    category = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all()
    )
    sub_category = serializers.PrimaryKeyRelatedField(
        queryset=SubCategory.objects.all()
    )

    class Meta:
        model = HealthAndBeautyProduct
        fields = '__all__'
        read_only_fields = ['id']


class FoodProductSerializer(
    UniqueProductPerShopMixin,
    ProductCreateMixin,
    ProductRepresentationMixin,
    BaseProductSerializer
):
    """serializer to handle Food product category creation"""
    category = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all()
    )
    sub_category = serializers.PrimaryKeyRelatedField(
        queryset=SubCategory.objects.all()
    )
    
    class Meta:
        model = FoodProduct
        fields = '__all__'
        read_only_fields = ['id']


class MixedProductSerializer(serializers.Serializer):
    def to_representation(self, instance):
        model_name = instance.__class__.__name__.lower()

        mapping = {
            'fashionproduct': FashionProductSerializer,
            'foodproduct': FoodProductSerializer,
            'gadgetproduct': GadgetProductSerializer,
            'electronicsproduct': ElectronicsProductSerializer,
            'accessoryproduct': AccessoryProductSerializer,
            'healthandbeautyproduct': HealthAndBeautyProductSerializer,
            'vehicleproduct': VehicleProductSerializer,
            'childrenproduct': ChildrenProductSerializer,
        }

        serializer_class = mapping.get(model_name)
        if not serializer_class:
            raise serializers.ValidationError(f"No serializer found for model {model_name}")
        
        return serializer_class(instance).data


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

    return mapping.get(category_name.strip().lower())