from django.db import models


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