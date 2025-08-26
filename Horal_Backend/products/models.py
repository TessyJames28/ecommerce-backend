from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
import uuid
from django.utils.crypto import get_random_string
from users.models import CustomUser
from shops.models import Shop
from categories.models import Category
from subcategories.models import SubCategory
from django.utils.text import slugify
from .textchoices import (
    Color, SizeOption, ProductCondition, EngineType, EngineSize,
    FuelType, Transmission, OperatingSystem, PowerSource,
    PowerOutput, Type, SkinType, FoodCondition, AgeRecommendation
)

# Create your models here.   
class PublishedProductManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_published=True)


class ProductLocationMixin(models.Model):
    """Reusable location fields for product models"""
    state = models.CharField(max_length=50)
    local_govt = models.CharField(max_length=150)

    class Meta:
        abstract = True


class IndexableProductMixin(models.Model):
    """Reusable mixin for product indexing."""

    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['title', 'is_published']),
        ]

    
class BaseProduct(models.Model):
    """Base model for products."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, blank=True)
    description = models.TextField()
    specifications = models.TextField(null=True, blank=True) 
    price = models.DecimalField(max_digits=10, decimal_places=2)    
    quantity = models.PositiveIntegerField(default=0)
    production_date = models.DateField(null=True, blank=True)
    condition = models.CharField(max_length=50, choices=ProductCondition.choices, default=ProductCondition.NEW)
    brand = models.CharField(max_length=250, null=True, blank=True)
    is_published = models.BooleanField(default=False)
    live_video_url = models.URLField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Manager
    objects = models.Manager() # default manager for all products
    published = PublishedProductManager() # only published

    class Meta:
        abstract = True


    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title)
            short_uuid = str(self.id)[:12] # Use first 12 characters of the UUID
            self.slug = f"{base_slug}-{short_uuid}"
        super().save(*args, **kwargs)

    def get_variants(self):
        return ProductVariant.objects.filter(
            content_type=ContentType.objects.get_for_model(self.__class__),
            object_id=self.id
        )
    

class ProductVariant(models.Model):
    """Model to distinguish each individual product variants per sizes and color"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.UUIDField()
    product = GenericForeignKey('content_type', 'object_id')

    # Variant properties
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name="variants")
    sku = models.CharField(max_length=50, unique=True, blank=True)
    color = models.CharField(max_length=20, choices=Color.choices, null=True,blank=True)
    custom_size_unit = models.CharField(max_length=10, choices=SizeOption.SizeUnit.choices, blank=True, null=True)
    standard_size = models.CharField(max_length=10, choices=SizeOption.StandardSize.choices, null=True, blank=True)
    custom_size_value = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    stock_quantity = models.PositiveBigIntegerField(default=0)
    reserved_quantity = models.PositiveIntegerField(default=0)
    price_override = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)


    def save(self, *args, **kwargs):
        if not self.sku:
            base = slugify(self.product.title)[:5].upper()
            color = self.color[:3].upper() if self.color else "XXX"
            size = self.standard_size or self.custom_size_value or "FRE"
            
            # Generating a unique SKU
            for _ in range(10): 
                random_part = get_random_string(4).upper()
                candidate = f"{base}-{color}-{size}-{random_part}"
                if not ProductVariant.objects.filter(sku=candidate).exists():
                    self.sku = candidate
                    break
                else:
                    raise ValueError("Unable to generate unique SKU after 10 attempts.")
        
        # Set the shop (once product is attached)
        if self.product and hasattr(self.product, "shop"):
            self.shop = self.product.shop

        super().save(*args, **kwargs)

    class Meta:
        unique_together = (
            'content_type', 'object_id',
            'standard_size', 'color',
            'custom_size_unit', 'custom_size_value'
        ) # prevent duplicate products


    @property
    def avaialble_stock(self):
        return self.stock_quantity - self.reserved_quantity
    

    def __str__(self):
        if self.standard_size:
            size_display = self.standard_size
        elif self.custom_size_value:
            size_display = f"{self.custom_size_value} {self.custom_size_unit}"
        else:
            size_display = "No size"

        color_display = self.color or "no color"
        return f"{self.product} - {size_display} - {color_display}"


class ChildrenProduct(BaseProduct, ProductLocationMixin):
    """Model for baby and children products in one unified model."""
    shop = models.ForeignKey(
        Shop,
        on_delete=models.CASCADE,
        related_name='children_products'
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        null=False,
        related_name='children_products'
    )
    sub_category = models.ForeignKey(
        SubCategory,
        on_delete=models.CASCADE,
        null=False,
        blank=False,
        related_name='children_products'
    )
    # images = models.ManyToManyField(ImageLink, related_name='baby_products', blank=False)
    material = models.CharField(max_length=250, null=True, blank=True)
    age_recommendations = models.CharField(
        max_length=50, choices=AgeRecommendation.choices,
        null=True, blank=True
    )
    weight_capacity = models.CharField(max_length=50, null=True, blank=True)
    safety_certifications = models.TextField(null=True, blank=True)


    class Meta(IndexableProductMixin.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=['title', 'brand', 'category', 'shop'],
                name='unique_children_product_per_shop'
            )
        ]


class VehicleProduct(BaseProduct, ProductLocationMixin):
    """Model for vehicle products."""
    shop = models.ForeignKey(
        Shop,
        on_delete=models.CASCADE,
        related_name='vehicle_products'
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        null=False,
        related_name='vehicle_products'
    )
    sub_category = models.ForeignKey(
        SubCategory,
        on_delete=models.CASCADE,
        null=False,
        blank=False,
        related_name='vehicle_products'
    )
    make = models.CharField(max_length=250, null=True, blank=True)
    model = models.CharField(max_length=250, null=True, blank=True)
    year = models.PositiveIntegerField(null=True, blank=True)
    mileage = models.PositiveIntegerField(null=True, blank=True)
    engine_type = models.CharField(max_length=20, choices=EngineType.choices, null=True, blank=True)
    engine_size = models.CharField(max_length=20, choices=EngineSize.choices, null=True, blank=True)
    fuel_type = models.CharField(max_length=20, choices=FuelType.choices, null=True, blank=True)
    transmission = models.CharField(max_length=50, choices=Transmission.choices, null=True, blank=True)
    num_doors = models.CharField(max_length=2, null=True, blank=True)
    num_seats = models.CharField(max_length=2, null=True, blank=True)
    vin = models.CharField(max_length=17, unique=True, null=True, blank=True)
    color_exterior = models.CharField(max_length=20, choices=Color.choices, null=True, blank=True)
    color_interior = models.CharField(max_length=20, choices=Color.choices, null=True, blank=True)
    seating_capacity = models.CharField(max_length=2, null=True, blank=True)
    # images = models.ManyToManyField(ImageLink, related_name='vehicle_products', blank=False)


    class Meta(IndexableProductMixin.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=['title', 'brand', 'category', 'shop'],
                name='unique_vehicle_product_per_shop'
            )
        ]


class GadgetProduct(BaseProduct, ProductLocationMixin):
    """Model for gadget products."""
    shop = models.ForeignKey(
        Shop,
        on_delete=models.CASCADE,
        related_name='gadget_products'
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        null=False,
        related_name='gadget_products'
    )
    sub_category = models.ForeignKey(
        SubCategory,
        on_delete=models.CASCADE,
        null=False,
        blank=False,
        related_name='gadget_products'
    )
    model = models.CharField(max_length=250, null=True, blank=True)
    processor = models.CharField(max_length=250, null=True, blank=True)
    ram = models.CharField(max_length=50, null=True, blank=True)
    storage = models.CharField(max_length=50, null=True, blank=True)
    screen_size = models.CharField(max_length=50, null=True, blank=True)
    operating_system = models.CharField(max_length=50, choices=OperatingSystem.choices, null=True, blank=True)
    connectivity = models.CharField(max_length=250, null=True, blank=True)
    # images = models.ManyToManyField(ImageLink, related_name='gadget_products', blank=False)


    class Meta(IndexableProductMixin.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=['title', 'brand', 'category', 'shop'],
                name='unique_gadget_product_per_shop'
            )
        ]

class FashionProduct(BaseProduct, ProductLocationMixin):
    """Model for fashion products."""
    shop = models.ForeignKey(
        Shop,
        on_delete=models.CASCADE,
        related_name='fashion_products'
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        null=False,
        related_name='fashion_products'
    )
    sub_category = models.ForeignKey(
        SubCategory,
        on_delete=models.CASCADE,
        null=False,
        blank=False,
        related_name='fashion_products'
    )
    # occasion = models.CharField(max_length=250, null=True, blank=True)
    material = models.CharField(max_length=250, null=True, blank=True)
    style = models.CharField(max_length=250, null=True, blank=True)
    sleeve_length = models.CharField(max_length=250, null=True, blank=True)
    neckline = models.CharField(max_length=250, null=True, blank=True)
    # images = models.ManyToManyField(ImageLink, related_name='fashion_products', blank=False)


    class Meta(IndexableProductMixin.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=['title', 'brand', 'category', 'shop'],
                name='unique_fashion_product_per_shop'
            )
        ]


class ElectronicsProduct(BaseProduct, ProductLocationMixin):
    """Model for electronics products."""
    shop = models.ForeignKey(
        Shop,
        on_delete=models.CASCADE,
        related_name='electronics_products'
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        null=False,
        related_name='electronics_products'
    )
    sub_category = models.ForeignKey(
        SubCategory,
        on_delete=models.CASCADE,
        null=False,
        blank=False,
        related_name='electronics_products'
    )
    model = models.CharField(max_length=250)
    power_output = models.CharField(max_length=50, choices=PowerOutput.choices, null=True, blank=True)
    features = models.TextField(null=True, blank=True)
    connectivity = models.CharField(max_length=250, null=True)
    voltage = models.CharField(max_length=50, blank=True)
    power_source = models.CharField(max_length=50, choices=PowerSource.choices, null=True, blank=True)
    # images = models.ManyToManyField(ImageLink, related_name='electronics_products', blank=False)

    class Meta(IndexableProductMixin.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=['title', 'brand', 'category', 'shop'],
                name='unique_electronics_product_per_shop'
            )
        ]


class AccessoryProduct(BaseProduct, ProductLocationMixin):
    """Model for accessory products."""
    shop = models.ForeignKey(
        Shop,
        on_delete=models.CASCADE,
        related_name='accessory_products'
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        null=False,
        related_name='accessory_products'
    )
    sub_category = models.ForeignKey(
        SubCategory,
        on_delete=models.CASCADE,
        null=False,
        blank=False,
        related_name='accessory_products'
    )
    material = models.CharField(max_length=250, null=True, blank=True)
    compatibility = models.CharField(max_length=250, null=True, blank=True)
    dimensions = models.CharField(max_length=250, null=True, blank=True)
    type = models.CharField(max_length=50, choices=Type.choices, null=True, blank=True)
    # images = models.ManyToManyField(ImageLink, related_name='accessory_products', blank=False)

    class Meta(IndexableProductMixin.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=['title', 'brand', 'category', 'shop'],
                name='unique_accessory_product_per_shop'
            )
        ]


class HealthAndBeautyProduct(BaseProduct, ProductLocationMixin):
    """Model for health and beauty products."""
    shop = models.ForeignKey(
        Shop,
        on_delete=models.CASCADE,
        related_name='health_beauty_products'
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        null=False,
        related_name='health_beauty_products'
    )
    sub_category = models.ForeignKey(
        SubCategory,
        on_delete=models.CASCADE,
        null=False,
        blank=False,
        related_name='health_beauty_products'
    )
    ingredients = models.TextField(null=True, blank=True)
    skin_type = models.CharField(max_length=50, choices=SkinType.choices, null=True, blank=True)
    fragrance = models.CharField(max_length=250, null=True, blank=True)
    usage_instructions = models.TextField(null=True, blank=True)
    spf = models.CharField(max_length=50, null=True, blank=True)
    shade = models.CharField(max_length=50, null=True, blank=True)
    volume = models.CharField(max_length=50, null=True, blank=True)
    benefits = models.TextField(null=True, blank=True)
    # images = models.ManyToManyField(ImageLink, related_name='health_beauty_products', blank=False)

    class Meta(IndexableProductMixin.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=['title', 'brand', 'category', 'shop'],
                name='unique_health_beauty_product_per_shop'
            )
        ]


class FoodProduct(BaseProduct, ProductLocationMixin):
    """Model for food products."""
    shop = models.ForeignKey(
        Shop,
        on_delete=models.CASCADE,
        related_name='food_products'
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        null=False,
        related_name='food_products'
    )
    sub_category = models.ForeignKey(
        SubCategory,
        on_delete=models.CASCADE,
        null=False,
        blank=False,
        related_name='food_products'
    )
    ingredients = models.TextField(null=True, blank=True)
    dietary_info = models.CharField(max_length=250, null=True, blank=True)
    origin = models.CharField(max_length=250, null=True, blank=True)
    weight = models.CharField(max_length=50, null=True, blank=True)
    food_condition = models.CharField(max_length=50, choices=FoodCondition.choices, null=True, blank=True)
    shelf_life = models.CharField(max_length=50, null=True, blank=True)
    size = models.CharField(max_length=50, null=True, blank=True)
    # images = models.ManyToManyField(ImageLink, related_name='food_products', blank=False)

    class Meta(IndexableProductMixin.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=['title', 'brand', 'category', 'shop'],
                name='unique_food_product_per_shop'
            )
        ]


class ProductIndex(models.Model):
    """
    Model to index all products created from each categories
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.UUIDField()
    linked_product = GenericForeignKey('content_type', 'object_id')
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE)
    category_name = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)


    class Meta:
        unique_together = ('object_id', 'content_type')
        indexes = [
            models.Index(fields=['category_name']),
            models.Index(fields=['object_id']),
        ]

    
    def get_real_product(self):
        """Method to retrieve the real product"""
        from .utils import CATEGORY_MODEL_MAP
        model_class = CATEGORY_MODEL_MAP.get(self.category_name)
        return model_class.objects.get(id=self.id)


    def __str__(self):
        return f"{self.category_name} - {self.object_id}"


class RecentlyViewedProduct(models.Model):
    """Model to handle users recently viewed products"""
    user = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE,
        null=True, blank=True
    )
    session_key = models.CharField(max_length=250, null=True, blank=True)
    product_index = models.ForeignKey(ProductIndex, on_delete=models.CASCADE)
    viewed_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-viewed_at']
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'product_index'],
                name='unique_user_product_view',
                condition=models.Q(user__isnull=False)
            ),
            models.UniqueConstraint(
                fields=['session_key', 'product_index'],
                name='unique_session_product_view',
                condition=models.Q(user__isnull=True)
            ),
        ]

class BaseProductImage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    url = models.URLField()
    alt_text = models.CharField(max_length=255, blank=True)

    class Meta:
        abstract = True

class VehicleImage(BaseProductImage):
    product = models.ForeignKey(VehicleProduct, related_name="images", on_delete=models.CASCADE)

class FashionImage(BaseProductImage):
    product = models.ForeignKey(FashionProduct, related_name="images", on_delete=models.CASCADE)

class ElectronicsImage(BaseProductImage):
    product = models.ForeignKey(ElectronicsProduct, related_name="images", on_delete=models.CASCADE)

class FoodImage(BaseProductImage):
    product = models.ForeignKey(FoodProduct, related_name="images", on_delete=models.CASCADE)

class HealthAndBeautyImage(BaseProductImage):
    product = models.ForeignKey(HealthAndBeautyProduct, related_name="images", on_delete=models.CASCADE)

class AccessoryImage(BaseProductImage):
    product = models.ForeignKey(AccessoryProduct, related_name="images", on_delete=models.CASCADE)

class ChildrenImage(BaseProductImage):
    product = models.ForeignKey(ChildrenProduct, related_name="images", on_delete=models.CASCADE)

class GadgetImage(BaseProductImage):
    product = models.ForeignKey(GadgetProduct, related_name="images", on_delete=models.CASCADE)
