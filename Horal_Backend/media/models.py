from django.db import models
from django.conf import settings

class UploadedAsset(models.Model):
    MEDIA_TYPE_CHOICES = (
        ("image", "Image"),
        ("video", "Video"),
        ("document", "Document"),
        ("file", "File"), 
    )

    uploader = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="uploaded_assets"
    )
    
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="vendor_assets"
    )
    
    media_type = models.CharField(max_length=20, choices=MEDIA_TYPE_CHOICES)
    original_filename = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100)
    size = models.PositiveIntegerField()
    key = models.CharField(max_length=500, unique=True)
    url = models.URLField(max_length=1000, null=True, blank=True)  
    is_private = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.original_filename} ({self.media_type})"

    def can_delete(self, user):
        if not user.is_authenticated:
            return False
        if user.is_superuser or user.is_staff:
            return True
        if user == self.uploader:
            return True
        if self.seller and user == self.seller:
            return True
        return False
