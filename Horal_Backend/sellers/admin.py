from django.contrib import admin
from .models import SellerKYC, SellerSocials, Shop

# Register your models here.
admin.site.register(SellerSocials)
admin.site.register(SellerKYC)
admin.site.register(Shop)
