from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
import uuid
from shops.models import Shop
from categories.models import Category
from subcategories.models import SubCategory

# Create your models here.
class ImageLink(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    url = models.URLField(unique=True)
    alt_text = models.CharField(max_length=255, null=True, blank=True)
    
    def __str__(self):
        return self.url or self.alt_text
    

class Color(models.TextChoices):
    """Model for product colors."""
    RED = 'red', 'Red'
    GREEN = 'green', 'Green'
    BLUE = 'blue', 'Blue'
    YELLOW = 'yellow', 'Yellow'
    BLACK = 'black', 'Black'
    SILVER = 'silver', 'Silver'
    GOLD = 'gold', 'Gold'
    BLACK_GOLD = 'black gold', 'Black Gold'
    WHITE = 'white', 'White'
    ORANGE = 'orange', 'Orange'
    PURPLE = 'purple', 'Purple'
    CYAN = 'cyan', 'Cyan'
    MAGENTA = 'magenta', 'Magenta'
    LIME = 'lime', 'Lime'
    AMBER = 'amber', 'Amber'
    TEAL = 'teal', 'Teal'
    PINK = 'pink', 'Pink'
    BROWN = 'brown', 'Brown'
    GRAY = 'gray', 'Gray'
    INDIGO = 'indigo', 'Indigo'
    MAROON = 'maroon', 'Maroon'
    TURQUOISE = 'turquoise', 'Turquoise'
    OLIVE = 'olive', 'Olive'
    BEIGE = 'beige', 'Beige'
    TRANSPARENT = 'transparent', 'Transparent'
    

class SizeOption(models.Model):
    class SizeUnit(models.TextChoices):
        STANDARD = "standard", "Standard Size (e.g. S, M, L)"
        INCH = "inch", "Inch"
        CM = "cm", "Centimeter"
        KG = "kg", "Kilogram"
        G = "g", "Gram"
        ML = "ml", "Mililiter"
        L = "l", "Liter"

    class StandardSize(models.TextChoices):
        XS = "XS", "Extra Small"
        S = "S", "Small"
        M = "M", "Medium"
        L = "L", "Large"
        XL = "XL", "Extra Large"
        XXL = "XXL", "Double Extra Large"

    value = models.CharField(max_length=20) # e.g., "S", "55", "30"
    unit = models.CharField(max_length=10, choices=SizeUnit.choices)

    def __str__(self):
        return f"{self.value} {self.get_unit_display()}" if self.unit != "standard" else self.value
    

class ProductCondition(models.TextChoices):
    NEW = 'brand_new', 'Brand New'
    USED = 'used', 'Used'


class EngineType(models.TextChoices):
    PETROL = 'petrol', 'Petrol'
    DIESEL = 'diesel', 'Diesel'
    ELECTRIC = 'electric', 'Electric'

class Transmission(models.TextChoices):
    MANUAL = 'manual', 'Manual'
    AUTOMATIC = 'automatic', 'Automatic'


class OperatingSystem(models.TextChoices):
    WINDOWS = 'windows', 'Windows'
    MAC = 'mac', 'Mac'
    LINUX = 'linux', 'Linux'
    ANDROID = 'android', 'Android'
    IOS = 'ios', 'iOS'


class PowerSource(models.TextChoices):
    BATTERY = 'battery', 'Battery'
    ELECTRIC = 'electric', 'Electric'
    SOLAR = 'solar', 'Solar'


class PowerOutput(models.TextChoices):
    LOW = "low", "Low (<10W)"
    MEDIUM = "medium", "Medium (10-30W)"
    HIGH = "high", "High (30-65W)"
    ULTRA = "ultra", "Ultra (65W+)"


class Type(models.TextChoices):
    CASE = 'case', 'Case'
    CHARGER = 'charger', 'Charger'
    SCREEN_PROTECTOR = 'screen_protector', 'Screen Protector'
    STRAP = 'strap', 'Strap'


class SkinType(models.TextChoices):
    DRY = 'dry', 'Dry'
    OILY = 'oily', 'Oily'
    COMBINATION = 'combination', 'Combination'


class FoodCondition(models.TextChoices):
    FRESH = 'fresh', 'Fresh'
    FROZEN = 'frozen', 'Frozen'
    CANNED = 'canned', 'Canned'

class FuelType(models.TextChoices):
    PETROL = 'petrol', 'Petrol'
    DIESEL = 'diesel', 'Diesel'
    CNG = 'cng', 'CNG'
    LPG = 'lpg', 'LPG'


class EngineSize(models.TextChoices):
    EXTRASMALL = 'extra-small', 'under 1.0-liter'
    SMALL = 'small', '1.0-2.0-liter'
    MEDIUM = 'medium', '2.0-3.0-liter'
    LARGE = 'large', '3.0-liter+'


class SleeveLength(models.TextChoices):
    SLEEVELESS = "sleeveless", "Sleeveless"
    SHORT = "short", "Short Sleeve"
    THREE_QUARTER = "3/4", "Three Quarter"
    LONG = "long", "Long Sleeve"
    CAP = "cap", "Cap Sleeve"

class Neckline(models.TextChoices):
    ROUND = "round", "Round Neck"
    V_NECK = "v_neck", "V-Neck"
    COLLARED = "collared", "Collared"
    OFF_SHOULDER = "off_shoulder", "Off Shoulder"
    SWEETHEART = "sweetheart", "Sweetheart"
    HALTER = "halter", "Halter"
    TURTLENECK = "turtleneck", "Turtleneck"


class Occasion(models.Model):
    """Occassion options for fashion products"""
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name
    
    # occasion_list = ['Casual', 'Formal', 'Wedding', 'Party', 'Sports', 'Office', 'Traditional']
    # for name in occasion_list:
    #     Occasion.objects.get_or_create(name=name)


class PublishedProductManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_published=True)


class ProductLocationMixin(models.Model):
    """Reusable location fields for product models"""
    state = models.CharField(max_length=50)
    local_govt = models.CharField(max_length=150)

    class Meta:
        abstract = True

    
class BaseProduct(models.Model):
    """Base model for products."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    description = models.TextField()
    specifications = models.TextField(null=True, blank=True) 
    price = models.DecimalField(max_digits=10, decimal_places=2)    
    quantity = models.PositiveIntegerField(default=0)
    production_date = models.DateField(null=True, blank=True)
    condition = models.CharField(max_length=50, choices=ProductCondition.choices, default=ProductCondition.NEW)
    brand = models.CharField(max_length=100, null=True, blank=True)
    is_published = models.BooleanField(default=False)
    live_video_url = models.URLField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Manager
    objects = models.Manager() # default manager for all products
    published = PublishedProductManager() # only published

    class Meta:
        abstract = True


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
    color = models.CharField(max_length=20, choices=Color.choices, null=True,blank=True)
    custom_size_unit = models.CharField(max_length=10, choices=SizeOption.SizeUnit.choices, blank=True, null=True)
    standard_size = models.CharField(max_length=10, choices=SizeOption.StandardSize.choices, null=True, blank=True)
    custom_size_value = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    stock_quantity = models.PositiveBigIntegerField(default=0)
    reserved_quantity = models.PositiveIntegerField(default=0)
    price_override = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

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
    images = models.ManyToManyField(ImageLink, related_name='baby_products', blank=False)
    material = models.CharField(max_length=100, null=True, blank=True)
    weight_capacity = models.CharField(max_length=50, null=True, blank=True)
    safety_certifications = models.TextField(null=True, blank=True)


    class Meta:
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
    make = models.CharField(max_length=100, null=True, blank=True)
    model = models.CharField(max_length=100, null=True, blank=True)
    year = models.PositiveIntegerField()
    mileage = models.PositiveIntegerField()
    engine_type = models.CharField(max_length=20, choices=EngineType.choices, default=EngineType.PETROL)
    engine_size = models.CharField(max_length=20, choices=EngineSize.choices, default=EngineSize.SMALL)
    fule_type = models.CharField(max_length=20, choices=FuelType.choices, default=FuelType.PETROL)
    transmission = models.CharField(max_length=50, choices=Transmission.choices, default=Transmission.MANUAL)
    num_doors = models.PositiveIntegerField()
    num_seats = models.PositiveIntegerField()
    vin = models.CharField(max_length=17, unique=True)
    color_exterior = models.CharField(max_length=20, choices=Color.choices, null=True, blank=True)
    color_interior = models.CharField(max_length=20, choices=Color.choices, null=True, blank=True)
    seating_capacity = models.PositiveIntegerField()
    images = models.ManyToManyField(ImageLink, related_name='vehicle_products', blank=False)


    class Meta:
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
    model = models.CharField(max_length=100)
    processor = models.CharField(max_length=100)
    ram = models.CharField(max_length=50)
    storage = models.CharField(max_length=50)
    screen_size = models.CharField(max_length=50)
    operating_system = models.CharField(max_length=50, choices=OperatingSystem.choices, default=OperatingSystem.WINDOWS)
    connectivity = models.CharField(max_length=100)
    images = models.ManyToManyField(ImageLink, related_name='gadget_products', blank=False)


    class Meta:
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
    occasion = models.ManyToManyField(Occasion, related_name="fashion_products", blank=True)
    material = models.CharField(max_length=100, null=True, blank=True)
    style = models.CharField(max_length=100, null=True, blank=True)
    sleeve_length = models.CharField(max_length=20, choices=SleeveLength.choices, null=True, blank=True)
    neckline = models.CharField(max_length=30, choices=Neckline.choices, null=True, blank=True)
    images = models.ManyToManyField(ImageLink, related_name='fashion_products', blank=False)


    class Meta:
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
    model = models.CharField(max_length=100)
    power_output = models.CharField(max_length=50, choices=PowerOutput.choices, default=PowerOutput.LOW)
    features = models.TextField(null=True, blank=True)
    connectivity = models.CharField(max_length=100)
    voltage = models.CharField(max_length=50)
    power_source = models.CharField(max_length=50, choices=PowerSource.choices, default=PowerSource.ELECTRIC)
    images = models.ManyToManyField(ImageLink, related_name='electronics_products', blank=False)

    class Meta:
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
    material = models.CharField(max_length=100, null=True, blank=True)
    compatibility = models.CharField(max_length=100, null=True, blank=True)
    dimensions = models.CharField(max_length=100, null=True, blank=True)
    type = models.CharField(max_length=50, choices=Type.choices, default=Type.CASE)
    images = models.ManyToManyField(ImageLink, related_name='accessory_products', blank=False)

    class Meta:
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
    skin_type = models.CharField(max_length=50, choices=SkinType.choices, default=SkinType.DRY)
    fragrance = models.CharField(max_length=100, null=True, blank=True)
    usage_instructions = models.TextField(null=True, blank=True)
    spf = models.CharField(max_length=50, null=True, blank=True)
    shade = models.CharField(max_length=50, null=True, blank=True)
    volume = models.CharField(max_length=50, null=True, blank=True)
    benefits = models.TextField(null=True, blank=True)
    color = models.CharField(max_length=50, null=True, blank=True)
    images = models.ManyToManyField(ImageLink, related_name='health_beauty_products', blank=False)

    class Meta:
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
    dietary_info = models.CharField(max_length=100, null=True, blank=True)
    origin = models.CharField(max_length=100, null=True, blank=True)
    weight = models.CharField(max_length=50, null=True, blank=True)
    condition = models.CharField(max_length=50, choices=FoodCondition.choices, default=FoodCondition.FRESH)
    shelf_life = models.CharField(max_length=50, null=True, blank=True)
    size = models.CharField(max_length=50, null=True, blank=True)
    images = models.ManyToManyField(ImageLink, related_name='food_products', blank=False)

    class Meta:
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
    product = GenericForeignKey('content_type', 'object_id')
    category_name = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)


    class Meta:
        unique_together = ('object_id', 'content_type')
        indexes = [
            models.Index(fields=['category_name']),
            models.Index(fields=['object_id']),
        ]


    def __str__(self):
        return f"{self.category_name} - {self.object_id}"
    