from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
import uuid
from sellers.models import SellerKYC, Shop

# Create your models here.
class Category(models.Model):
    """Model for product categories."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.name
    

class ImageLink(models.Model):
    url = models.URLField()
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


class AgeGroup(models.TextChoices):
    NEW_BORN = 'new_born', 'New Born'
    INFANT = 'infant', 'Infant'
    TODDLER = 'toddler', 'Toddler'


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


class Type(models.TextChoices):
    CASE = 'case', 'Case'
    CHARGER = 'charger', 'Charger'
    SCREEN_PROTECTOR = 'screen_protector', 'Screen Protector'


class SkinType(models.TextChoices):
    DRY = 'dry', 'Dry'
    OILY = 'oily', 'Oily'
    COMBINATION = 'combination', 'Combination'


class FoodCondition(models.TextChoices):
    FRESH = 'fresh', 'Fresh'
    FROZEN = 'frozen', 'Frozen'
    CANNED = 'canned', 'Canned'

    
class BaseProduct(models.Model):
    """Base model for products."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)    
    quantity = models.PositiveIntegerField(default=0)
    condition = models.CharField(max_length=50, choices=ProductCondition.choices, default=ProductCondition.NEW)
    brand_name = models.CharField(max_length=100, null=True, blank=True)
    location = models.CharField(max_length=255, null=True, blank=True)
    live_video_url = models.URLField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

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
    price_override = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    class Meta:
        unique_together = (
            'content_type', 'object_id',
            'standard_size', 'color',
            'custom_size_unit', 'custom_size_value'
        ) # prevent duplicate products

    def __str__(self):
        if self.standard_size:
            size_display = self.standard_size
        elif self.custom_size_value:
            size_display = f"{self.custom_size_value} {self.custom_size_unit}"
        else:
            size_display = "No size"

        color_display = self.color or "no color"
        return f"{self.product} - {size_display} - {color_display}"


class BabyProduct(BaseProduct):
    """Model for baby products."""
    shop = models.ForeignKey(
        Shop,
        on_delete=models.CASCADE,
        related_name='baby_products'
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        null=False,
        related_name='baby_products'
    )
    material = models.CharField(max_length=100, null=True, blank=True)
    age_group = models.CharField(max_length=50, choices=AgeGroup.choices, default=AgeGroup.NEW_BORN)
    weight_capacity = models.CharField(max_length=50, null=True, blank=True)
    safety_certifications = models.TextField(null=True, blank=True)
    images = models.ManyToManyField(ImageLink, related_name='baby_products', blank=False)


class VehicleProduct(BaseProduct):
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
    make = models.CharField(max_length=100, null=True, blank=True)
    model = models.CharField(max_length=100, null=True, blank=True)
    year = models.PositiveIntegerField()
    mileage = models.PositiveIntegerField()
    engine_type = models.CharField(max_length=50, choices=EngineType.choices, default=EngineType.PETROL)
    transmission = models.CharField(max_length=50, choices=Transmission.choices, default=Transmission.MANUAL)
    num_doors = models.PositiveIntegerField()
    num_seats = models.PositiveIntegerField()
    vin = models.CharField(max_length=17, unique=True)
    color_exterior = models.CharField(max_length=50, null=True, blank=True)
    color_interior = models.CharField(max_length=50, null=True, blank=True)
    seating_capacity = models.PositiveIntegerField()
    images = models.ManyToManyField(ImageLink, related_name='vehicle_products', blank=False)


class GadgetProduct(BaseProduct):
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
    model = models.CharField(max_length=100)
    processor = models.CharField(max_length=100)
    ram = models.CharField(max_length=50)
    storage = models.CharField(max_length=50)
    screen_size = models.CharField(max_length=50)
    operating_system = models.CharField(max_length=50, choices=OperatingSystem.choices, default=OperatingSystem.WINDOWS)
    connectivity = models.CharField(max_length=100)
    color = models.CharField(max_length=50, null=True, blank=True)
    images = models.ManyToManyField(ImageLink, related_name='gadget_products', blank=False)

class FashionProduct(BaseProduct):
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
    material = models.CharField(max_length=100, null=True, blank=True)
    style = models.CharField(max_length=100, null=True, blank=True)
    color = models.CharField(max_length=50, null=True, blank=True)
    images = models.ManyToManyField(ImageLink, related_name='fashion_products', blank=False)


class ElectronicsProduct(BaseProduct):
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
    model = models.CharField(max_length=100)
    power_output = models.CharField(max_length=50)
    features = models.TextField(null=True, blank=True)
    connectivity = models.CharField(max_length=100)
    voltage = models.CharField(max_length=50)
    color = models.CharField(max_length=50, null=True, blank=True)
    power_source = models.CharField(max_length=50, choices=PowerSource.choices, default=PowerSource.ELECTRIC)
    images = models.ManyToManyField(ImageLink, related_name='electronics_products', blank=False)


class AccessoryProduct(BaseProduct):
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
    material = models.CharField(max_length=100, null=True, blank=True)
    compatibility = models.CharField(max_length=100, null=True, blank=True)
    dimensions = models.CharField(max_length=100, null=True, blank=True)
    color = models.CharField(max_length=50, null=True, blank=True)
    type = models.CharField(max_length=50, choices=Type.choices, default=Type.CASE)
    images = models.ManyToManyField(ImageLink, related_name='accessory_products', blank=False)


class HealthAndBeautyProduct(BaseProduct):
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


class FoodProduct(BaseProduct):
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
    ingredients = models.TextField(null=True, blank=True)
    dietary_info = models.CharField(max_length=100, null=True, blank=True)
    origin = models.CharField(max_length=100, null=True, blank=True)
    weight = models.CharField(max_length=50, null=True, blank=True)
    condition = models.CharField(max_length=50, choices=FoodCondition.choices, default=FoodCondition.FRESH)
    shelf_life = models.CharField(max_length=50, null=True, blank=True)
    size = models.CharField(max_length=50, null=True, blank=True)
    images = models.ManyToManyField(ImageLink, related_name='food_products', blank=False)
