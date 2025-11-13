from rest_framework import serializers
from django.db.models import Q, Avg
from .models import (
    ChildrenProduct,
    ProductVariant, VehicleProduct, GadgetProduct,
    FashionProduct, ElectronicsProduct, AccessoryProduct,
    HealthAndBeautyProduct, FoodProduct, ProductIndex,
    VehicleImage, FashionImage, ElectronicsImage, FoodImage,
    HealthAndBeautyImage, AccessoryImage, ChildrenImage, GadgetImage
)
from django.core.exceptions import ValidationError as DRFValidationError
from categories.serializers import CategorySerializer
from subcategories.serializers import SubCategoryProductSerializer
from categories.models import Category
from subcategories.models import SubCategory
from django.contrib.contenttypes.models import ContentType
from ratings.models import UserRating
from logistics.serializers import LogisticsSerializer

from .textchoices import (
    Color, SizeOption, ProductCondition, EngineType, EngineSize,
    FuelType, Transmission, OperatingSystem, PowerSource,
    PowerOutput, Type, SkinType, FoodCondition, AgeRecommendation
)


def normalize_choice(value, enum_class):
    """
    Normalize a text input (case-insensitive) to match a Django TextChoices value.
    """
    if not value:
        return value
    
    normalized = value.lower()

    for choice in enum_class:
        if choice.value.lower() == normalized:
            return choice.value

    valid_choices = [choice.value for choice in enum_class]
    raise ValueError(
        f"Invalid value '{value}'. Must be one of: {valid_choices}"
    )


# Base serializer for all product images
class BaseProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        fields = ["id", "url", "alt_text"]
        abstract = True


# Subclass serializers for each product image type
class VehicleImageSerializer(BaseProductImageSerializer):
    class Meta(BaseProductImageSerializer.Meta):
        model = VehicleImage


class FashionImageSerializer(BaseProductImageSerializer):
    class Meta(BaseProductImageSerializer.Meta):
        model = FashionImage


class ElectronicsImageSerializer(BaseProductImageSerializer):
    class Meta(BaseProductImageSerializer.Meta):
        model = ElectronicsImage


class FoodImageSerializer(BaseProductImageSerializer):
    class Meta(BaseProductImageSerializer.Meta):
        model = FoodImage


class HealthAndBeautyImageSerializer(BaseProductImageSerializer):
    class Meta(BaseProductImageSerializer.Meta):
        model = HealthAndBeautyImage


class AccessoryImageSerializer(BaseProductImageSerializer):
    class Meta(BaseProductImageSerializer.Meta):
        model = AccessoryImage


class ChildrenImageSerializer(BaseProductImageSerializer):
    class Meta(BaseProductImageSerializer.Meta):
        model = ChildrenImage


class GadgetImageSerializer(BaseProductImageSerializer):
    class Meta(BaseProductImageSerializer.Meta):
        model = GadgetImage



class ProductVariantSerializer(serializers.ModelSerializer):
    """Serializer for product variant model which include sizes and colors."""
    color = serializers.CharField(required=False)
    standard_size = serializers.CharField(required=False)
    custom_size_unit = serializers.CharField(required=False)
    logistics = LogisticsSerializer(write_only=True, required=False)
    logistics_data = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = ProductVariant
        fields = [
            'id', 'color', 'custom_size_unit', 'standard_size', 'sku', 'size',
            'custom_size_value', 'stock_quantity', 'reserved_quantity', 'price_override',
            'logistics', 'logistics_data'
        ]
        read_only_fields = ['id', 'sku', 'logistics_data']
    
    def get_logistics_data(self, obj):
        logistics_qs = obj.get_logistics() # defined in BaseProduct
        return LogisticsSerializer(logistics_qs, many=True).data

    def validate_custom_size_unit(self, value):
        return normalize_choice(value, SizeOption.SizeUnit)

    def validate_standard_size(self, value):
        return normalize_choice(value, SizeOption.StandardSize)

    def validate_color(self, value):
        return normalize_choice(value, Color)
    

    def create(self, validated_data):
        instance = super().create(validated_data)
        if instance.product and hasattr(instance.product, "shop"):
            instance.shop = instance.product.shop
            instance.save(update_fields=["shop"])
        return instance

class ProductRatingMixin(serializers.Serializer):
    average_rating = serializers.SerializerMethodField()
    total_reviews = serializers.SerializerMethodField()

    def get_average_rating(self, obj):
        index = self._get_product_index(obj)
        if index:
            return UserRating.objects.filter(product=index).aggregate(
                avg=Avg('rating')
            )['avg']
        return None

    def get_total_reviews(self, obj):
        index = self._get_product_index(obj)
        if index:
            return UserRating.objects.filter(product=index).count()
        return 0

    def _get_product_index(self, obj):
        content_type = ContentType.objects.get_for_model(obj)
        return ProductIndex.objects.filter(
            content_type=content_type,
            object_id=obj.id
        ).first()


class ProductCreateMixin:
    def create(self, validated_data):
        from .utils import image_model_map, validate_logistics_vs_variants
        from logistics.models import Logistics
        from logistics.serializers import LogisticsSerializer

        # Pop nested relationships so they don’t go into model.create()
        images = validated_data.pop('images', [])
        variant_data = validated_data.pop('variants', [])
        logistic_data = validated_data.pop('logistics', {})

        # Check variant logistics consistency
        variant_have_logistics = [v.get('logistics') is not None for v in variant_data]
        if any(variant_have_logistics) and logistic_data:
            raise serializers.ValidationError(
                    "Logistics can either be at variant or product level not both"
                )
        elif any(variant_have_logistics):
            if not all(variant_have_logistics):
                raise serializers.ValidationError(
                    "if any variant has logistics, all variant must have logistics"
                )
        else:
            if not logistic_data:
                raise serializers.ValidationError(
                    "No variant logistics provided, product-level is required if no variant logistics"
                )
        
        # Ensure proper weight values are provided
        validate_logistics_vs_variants(logistic_data, variant_data)

        # Now create the product safely
        instance = self.Meta.model.objects.create(**validated_data)

        # Dynamically resolve image model
        model_name = instance.__class__.__name__
        image_model_class = image_model_map.get(model_name)

        if image_model_class:
            for img in images:
                image_model_class.objects.create(product=instance, **img)

        # Create variants and their logistics
        for variant in variant_data:
            variant_logistics = variant.pop('logistics', None)
            variant_instance = ProductVariant.objects.create(product=instance, **variant)

            # Create logistics for this variant if provided
            if variant_logistics:
                # logistic_data['product_variant'] = variant_instance.id
                serializer = LogisticsSerializer(data=variant_logistics)
                if serializer.is_valid():
                    serializer.save(product_variant=variant_instance)  # attach variant
                else:
                    raise serializers.ValidationError(serializer.errors)
                # Logistics.objects.create(product_variant=variant_logistics, **variant_logistics)
        
        # Create logistics for a single product if provided
        if not any(variant_have_logistics) and logistic_data:
                serializer = LogisticsSerializer(data=logistic_data)
                if serializer.is_valid(raise_exception=True):
                    serializer.save(product=instance)  # attach product
        # Logistics.objects.create(product=instance, **logistic_data)

        # Update product quantity based on stock
        from .utils import update_quantity
        update_quantity(instance)

        return instance
    

    def update(self, instance, validated_data):
        from .utils import image_model_map
        from logistics.models import Logistics
        """
        Product update especially for nested fields like images and variants
        """
        from .utils import validate_logistics_vs_variants

        images = validated_data.pop('images', [])
        variant_data = validated_data.pop('variants', [])
        logistic_data = validated_data.pop('logistics', {})

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Dynamically resolve image model
        model_name = instance.__class__.__name__
        image_model_class = image_model_map[model_name]

        if image_model_class and images:
            # Clear old images before adding new ones
            image_model_class.objects.filter(product=instance).delete()
            for img in images:
                image_model_class.objects.create(product=instance, **img)

        # Check variant logistics consistency
        variant_have_logistics = [v.get('logistics') is not None for v in variant_data]
        if any(variant_have_logistics) and logistic_data:
            raise serializers.ValidationError(
                    "Logistics can either be at variant or product level not both"
                )
        elif any(variant_have_logistics):
            if not all(variant_have_logistics):
                raise serializers.ValidationError(
                    "if any variant has logistics, all variant must have logistics"
                )
        else:
            # Only raise error if neither the instance nor the payload have logistics
            if not logistic_data and not instance.get_logistics().exists() and not any(v.logistics_variant.exists() for v in instance.get_variants()):
                raise serializers.ValidationError(
                    "No variant logistics provided, product-level is required if no variant logistics"
                )
        
        # Ensure proper weight values are provided
        validate_logistics_vs_variants(logistic_data, variant_data)

        if variant_data:
            instance.get_variants().delete()
            for variant in variant_data:
                variant_logistics = variant.pop('logistics', None)
                variant_instance = ProductVariant.objects.create(product=instance, **variant)

                # Update variant logistics if updated
                if variant_logistics:
                    serializer = LogisticsSerializer(data=variant_logistics)
                    if serializer.is_valid(raise_exception=True):
                        serializer.save(product_variant=variant_instance)  # attach product
                    else:
                        raise serializers.ValidationError(serializer.errors)
                    # variant_instance.logistics_variant.delete()
                    # Logistics.objects.create(product_variant=variant_instance, **variant_logistics)

        # Update product-level logistics if variants have None
        if not any(variant_have_logistics) and logistic_data:
            # Delete old product logistics
            instance.get_logistics().delete()
            serializer = LogisticsSerializer(data=logistic_data)
            if serializer.is_valid(raise_exception=True):
                serializer.save(product=instance)  # attach product
           
            # instance.get_logistics().delete()
            # Logistics.objects.create(product=instance, **logistic_data)
        
        # Update product quantity based on stock
        from .utils import update_quantity
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
        from .utils import update_quantity
        update_quantity(instance)
        data = super().to_representation(instance)
        data['category'] = CategorySerializer(instance.category).data
        data['sub_category'] = SubCategoryProductSerializer(instance.sub_category).data

        # List of base_field attributes
        base_fields = {
            'id', 'title', 'slug', 'description', 'price', 'quantity',
            'production_date', 'condition', 'brand', 'specifications',
            'is_published', 'live_video_url', 'created_at',
            'updated_at', 'shop', 'state', 'local_govt'
        }

        cat_data = ['category', 'sub_category']

        fields = ["images", "variants_details", "logistics_data"]

        rating_data = ['average_rating', 'total_reviews']

        base_data = {}
        spec_data = {}
        category_data ={}
        field_data = {}
        review_data = {}

        for key, value in data.items():
            if key in base_fields:
                base_data[key] = value
            elif key in fields:
                field_data[key] = value
            elif key in cat_data:
                category_data[key] = value
            elif key in rating_data:
                review_data[key] = value
            else:
                spec_data[key] = value

        return {
            **base_data,
            **field_data,
            "category_object": category_data,
            "specification": spec_data,
            "review": review_data
        }
    

class BaseProductSerializer(serializers.ModelSerializer):
    """Serializer for the base product model"""
    variants = ProductVariantSerializer(many=True, write_only=True, required=False)
    variants_details = serializers.SerializerMethodField(read_only=True)
    logistics = LogisticsSerializer(write_only=True, required=False)
    logistics_data = serializers.SerializerMethodField(read_only=True)
    quantity = serializers.SerializerMethodField()
    
    def get_variants_details(self, obj):
        variant_qs = obj.get_variants() # defined in BaseProduct
        return ProductVariantSerializer(variant_qs, many=True).data
    
    def get_logistics_data(self, obj):
        logistics_qs = obj.get_logistics() # defined in base product
        return LogisticsSerializer(logistics_qs, many=True).data

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
    BaseProductSerializer,
    ProductRatingMixin
):
    images = ChildrenImageSerializer(many=True)
    age_recommendation = serializers.CharField(required=False)
    condition = serializers.CharField(required=False)

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

    def validate_age_recommendation(self, value):
        return normalize_choice(value, AgeRecommendation)
    
    def validate_condition(self, value):
        return normalize_choice(value, ProductCondition)
    

class VehicleProductSerializer(
    UniqueProductPerShopMixin,
    ProductCreateMixin,
    ProductRepresentationMixin,
    BaseProductSerializer,
    ProductRatingMixin
):
    
    """serializer to handle vehicle product category creation"""
    images = VehicleImageSerializer(many=True)
    category = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all()
    )
    sub_category = serializers.PrimaryKeyRelatedField(
        queryset=SubCategory.objects.all()
    )
    fuel_type = serializers.CharField(required=False)
    condition = serializers.CharField(required=False)
    color_interior = serializers.CharField(required=False)
    color_exterior = serializers.CharField(required=False)
    engine_size = serializers.CharField(required=False)
    engine_type = serializers.CharField(required=False)
    transmission = serializers.CharField(required=False)

    class Meta:
        model = VehicleProduct
        fields = '__all__'
        read_only_fields = ['id']

    def validate_color_exterior(self, value):
        return normalize_choice(value, Color)
    
    def validate_color_interior(self, value):
        return normalize_choice(value, Color)
    
    def validate_engine_type(self, value):
        return normalize_choice(value, EngineType)
    
    def validate_engine_size(self, value):
        return normalize_choice(value, EngineSize)
    
    def validate_fuel_type(self, value):
        return normalize_choice(value, FuelType)
    
    def validate_transmission(self, value):
        return normalize_choice(value, Transmission)
    
    def validate_condition(self, value):
        return normalize_choice(value, ProductCondition)
    

class GadgetProductSerializer(
    UniqueProductPerShopMixin,
    ProductCreateMixin,
    ProductRepresentationMixin,
    BaseProductSerializer,
    ProductRatingMixin
):
    
    """serializer for Gadget product model creation"""
    images = GadgetImageSerializer(many=True)
    category = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all()
    )
    sub_category = serializers.PrimaryKeyRelatedField(
        queryset=SubCategory.objects.all()
    )
    operating_system = serializers.CharField(required=False)
    condition = serializers.CharField(required=False)

    class Meta:
        model = GadgetProduct
        fields = '__all__'
        read_only_fields = ['id']

    
    def validate_operating_system(self, value):
        return normalize_choice(value, OperatingSystem)
    
    def validate_condition(self, value):
        return normalize_choice(value, ProductCondition)


class FashionProductSerializer(
    UniqueProductPerShopMixin,
    ProductCreateMixin,
    ProductRepresentationMixin,
    BaseProductSerializer,
    ProductRatingMixin
):
    """Serializer to handle fashion category product creation"""
    images = FashionImageSerializer(many=True)
    category = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all()
    )
    sub_category = serializers.PrimaryKeyRelatedField(
        queryset=SubCategory.objects.all()
    )
    condition = serializers.CharField(required=False)

    class Meta:
        model = FashionProduct
        fields = '__all__'
        read_only_fields = ['id']


    def validate_condition(self, value):
        return normalize_choice(value, ProductCondition)


class ElectronicsProductSerializer(
    UniqueProductPerShopMixin,
    ProductCreateMixin,
    ProductRepresentationMixin,
    BaseProductSerializer,
    ProductRatingMixin
):
    """serializer to handle electronics product category creation"""
    images = ElectronicsImageSerializer(many=True)
    category = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all()
    )
    sub_category = serializers.PrimaryKeyRelatedField(
        queryset=SubCategory.objects.all()
    )
    power_source = serializers.CharField(required=False)
    condition = serializers.CharField(required=False)
    power_output = serializers.CharField(required=False)

    class Meta:
        model = ElectronicsProduct
        fields = '__all__'
        read_only_fields = ['id']

    
    def validate_power_source(self, value):
        return normalize_choice(value, PowerSource)
    
    def validate_power_output(self, value):
        return normalize_choice(value, PowerOutput)
    
    def validate_condition(self, value):
        return normalize_choice(value, ProductCondition)


class AccessoryProductSerializer(
    UniqueProductPerShopMixin,
    ProductCreateMixin,
    ProductRepresentationMixin,
    BaseProductSerializer,
    ProductRatingMixin
):
    """Serializer to handle Accesory product category creation"""
    images = AccessoryImageSerializer(many=True)
    category = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all()
    )
    sub_category = serializers.PrimaryKeyRelatedField(
        queryset=SubCategory.objects.all()
    )
    type = serializers.CharField(required=False)
    condition = serializers.CharField(required=False)

    class Meta:
        model = AccessoryProduct
        fields = '__all__'
        read_only_fields = ['id']

    
    def validate_type(self, value):
        return normalize_choice(value, Type)
    
    def validate_condition(self, value):
        return normalize_choice(value, ProductCondition)


class HealthAndBeautyProductSerializer(
    UniqueProductPerShopMixin,
    ProductCreateMixin,
    ProductRepresentationMixin,
    BaseProductSerializer,
    ProductRatingMixin
):
    """
    Serializer to handle the creation of health 
    and beauty products category
    """
    images = HealthAndBeautyImageSerializer(many=True)
    category = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all()
    )
    sub_category = serializers.PrimaryKeyRelatedField(
        queryset=SubCategory.objects.all()
    )
    skin_type = serializers.CharField(required=False)
    condition = serializers.CharField(required=False)

    class Meta:
        model = HealthAndBeautyProduct
        fields = '__all__'
        read_only_fields = ['id']

    def validate_skin_type(self, value):
        return normalize_choice(value, SkinType)
    
    def validate_condition(self, value):
        return normalize_choice(value, ProductCondition)


class FoodProductSerializer(
    UniqueProductPerShopMixin,
    ProductCreateMixin,
    ProductRepresentationMixin,
    BaseProductSerializer,
    ProductRatingMixin
):
    """serializer to handle Food product category creation"""
    images = FoodImageSerializer(many=True)
    category = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all()
    )
    sub_category = serializers.PrimaryKeyRelatedField(
        queryset=SubCategory.objects.all()
    )
    # food_condition = serializers.CharField(required=False)
    condition = serializers.CharField(required=False)
    
    class Meta:
        model = FoodProduct
        fields = '__all__'
        read_only_fields = ['id']

    def validate_condition(self, value):
        return normalize_choice(value, FoodCondition)
    
    # def validate_condition(self, value):
    #     return normalize_choice(value, ProductCondition)


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
    

# class ProductIndexSerializer(serializers.ModelSerializer, ProductRatingMixin):
#     """Serializer for product index model"""
#     image = serializers.SerializerMethodField()

#     class Meta:
#         model = ProductIndex
#         fields = [
#             "id", "title", "slug", "price", "image",
#             "state", "local_govt", "condition",
#             "category_name", "shop",
#         ]

#     def get_image(self, instance):
#         if hasattr(instance, "images"):
#             first_image = instance.images.first()
#             return first_image.url if first_image else None
#         return None



class ProductIndexSerializer(serializers.ModelSerializer):
    average_rating = serializers.SerializerMethodField()
    total_reviews = serializers.SerializerMethodField()

    class Meta:
        model = ProductIndex
        fields = [
            "id", "title", "slug", "price", "image", "brand",
            "state", "local_govt", "condition", "description", 'quantity',
            "category", "sub_category", "shop", "is_published", "specifications",
            "average_rating", "total_reviews", 'created_at',
        ]


    def get_average_rating(self, instance):
        product = instance.linked_product
        if hasattr(product, "reviews"):
            agg = product.reviews.aggregate(avg=Avg("rating"))
            return agg["avg"] or 0
        return 0

    def get_total_reviews(self, instance):
        product = instance.linked_product
        if hasattr(product, "reviews"):
            return product.reviews.count()
        return 0


