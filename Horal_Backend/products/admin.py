from django.contrib import admin
from .models import (
    ChildrenProduct, GadgetProduct, AccessoryProduct,
    VehicleProduct, ElectronicsProduct, FashionProduct,
    HealthAndBeautyProduct, ProductVariant, FoodProduct,
)

# Register your models here.
# admin.site.register(BaseProduct)
admin.site.register(ChildrenProduct)
admin.site.register(GadgetProduct)
admin.site.register(VehicleProduct)
admin.site.register(ElectronicsProduct)
admin.site.register(FashionProduct)
admin.site.register(HealthAndBeautyProduct)
admin.site.register(ProductVariant)
admin.site.register(AccessoryProduct)
admin.site.register(FoodProduct)
# admin.site.register(ProductCondition)
# admin.site.register(PowerSource)
