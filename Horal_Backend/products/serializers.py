from rest_framework import serializers
from django.db.models import Q, Avg
from .models import (
    ChildrenProduct, ImageLink,
    ProductVariant, VehicleProduct, GadgetProduct,
    FashionProduct, ElectronicsProduct, AccessoryProduct,
    HealthAndBeautyProduct, FoodProduct, ProductIndex
)
from categories.serializers import CategorySerializer
from subcategories.serializers import SubCategoryProductSerializer
from categories.models import Category
from subcategories.models import SubCategory
from django.contrib.contenttypes.models import ContentType
from ratings.models import UserRating

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


class ImageLinkSerializer(serializers.ModelSerializer):
    """Image serializer to handle adding image link to the db"""
    class Meta:
        model = ImageLink
        fields = ['id', 'url', 'alt_text']
        read_only_fields = ['id']


class ProductVariantSerializer(serializers.ModelSerializer):
    """Serializer for product variant model which include sizes and colors."""
    color = serializers.CharField(required=False)
    standard_size = serializers.CharField(required=False)
    custom_size_unit = serializers.CharField(required=False)

    class Meta:
        model = ProductVariant
        fields = [
            'id', 'color', 'custom_size_unit', 'standard_size', 'sku',
            'custom_size_value', 'stock_quantity', 'reserved_quantity', 'price_override'
        ]
        read_only_fields = ['id', 'sku']

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
        images = validated_data.pop('images', [])
        variants = validated_data.pop('variants', [])
        # names = validated_data.pop("occasion", [])

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
        # occasion_query = Q()
        # for name in names:
        #     occasion_query |= Q(name__iexact=name)
        # if names:
        #     occasions = Occasion.objects.filter(occasion_query)
        #     instance.occasion.set(occasions)

        # Update product quantity based on stock
        from .utils import update_quantity
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

        fields = ["images", "variants_details"]

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
    BaseProductSerializer,
    ProductRatingMixin
):
    
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
    category = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all()
    )
    sub_category = serializers.PrimaryKeyRelatedField(
        queryset=SubCategory.objects.all()
    )
    food_condition = serializers.CharField(required=False)
    condition = serializers.CharField(required=False)
    
    class Meta:
        model = FoodProduct
        fields = '__all__'
        read_only_fields = ['id']

    def validate_food_condition(self, value):
        return normalize_choice(value, FoodCondition)
    
    def validate_condition(self, value):
        return normalize_choice(value, ProductCondition)


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
