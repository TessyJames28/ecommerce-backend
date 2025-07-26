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
    BRONZE = 'bronze', 'Bronze'
    NAVY = 'navy', 'Navy'
    CORAL = 'coral', 'Coral'
    SALMON = 'salmon', 'Salmon'
    KHAKI = 'khaki', 'Khaki'
    LAVENDER = 'lavender', 'Lavender'
    PEACH = 'peach', 'Peach'
    MINT = 'mint', 'Mint'
    

class SizeOption:
    class SizeUnit(models.TextChoices):
        STANDARD = "standard", "Standard Size (e.g. S, M, L)"
        INCH = "INCH", "Inch"
        CM = "CM", "Centimeter"
        KG = "KG", "Kilogram"
        G = "G", "Gram"
        ML = "ML", "Milliliter"
        L = "L", "Liter"

    class StandardSize(models.TextChoices):
        XS = "XS", "Extra Small"
        S = "S", "Small"
        M = "M", "Medium"
        L = "L", "Large"
        XL = "XL", "Extra Large"
        XXL = "XXL", "Double Extra Large"
        XXXL = "XXXL", "Triple Extra Large"
        XXXXL = "XXXXL", "Quad Extra Large"
        XXXXXL = "XXXXXL", "Quint Extra Large"

    
class AgeRecommendation(models.TextChoices):
    NEWBORN_0_3M = "0-3m", "0 - 3 Months"
    INFANT_3_6M = "3-6m", "3 - 6 Months"
    INFANT_6_12M = "6-12m", "6 - 12 Months"
    TODDLER_1_2Y = "1-2y", "1 - 2 Years"
    PRESCHOOL_3_4Y = "3-4y", "3 - 4 Years"
    EARLY_CHILDHOOD_5_6Y = "5-6y", "5 - 6 Years"
    CHILD_7_9Y = "7-9y", "7 - 9 Years"
    PRETEEN_10_12Y = "10-12y", "10 - 12 Years"
    TEEN_13Y = "13y", "13 Years"
    

class ProductCondition(models.TextChoices):
    NEW = 'brand new', 'Brand New'
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
    DRY_OILY = 'dry and oily', 'Dry and Oily'


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
