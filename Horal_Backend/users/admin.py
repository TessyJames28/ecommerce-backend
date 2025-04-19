from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser
from django.utils.translation import gettext_lazy as _

# Modify users/admin.py to customize the admin interface for the CustomUser model
class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ('email', 'full_name', 'is_staff', 'is_seller', 'is_active')
    list_filter = ('is_staff', 'is_seller', 'is_active')
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        (_('Personal info'), {'fields': ('full_name', 'phone_number')}),
        (_('Permissions'), {'fields': ('is_staff', 'is_active', 'is_verified', 'is_seller')}),
        (_('Important dates'), {'fields': ('last_login',)}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'full_name', 'password1', 'password2', 'is_staff', 'is_active', 'is_verified', 'is_seller')
        }),
    )

    search_fields = ("email",)
    ordering = ("email",)

admin.site.register(CustomUser, CustomUserAdmin)