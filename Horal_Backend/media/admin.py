from django.contrib import admin
from .models import UploadedAsset

@admin.register(UploadedAsset)
class UploadedAssetAdmin(admin.ModelAdmin):
    list_display = ("vendor_id", "original_filename", "media_type", "size", "is_private", "created_at")
    list_filter = ("media_type", "is_private", "created_at")
    search_fields = ("seller__username", "original_filename", "key")  
    ordering = ("-created_at",)

    @admin.display(description="Vendor ID")
    def vendor_id(self, obj):
        return obj.seller.id if obj.seller else None
