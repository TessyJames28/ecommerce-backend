from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
import uuid


class SellerKYC(models.Model):
    """Model to store KYC documents for sellers"""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name='kyc'
    )
    country = models.CharField(
        max_length=100,
        null=False,
        blank=False,
        default='Nigeria',
    )
    nin = models.URLField()
    cac = models.URLField(null=True, blank=True)
    utility_bill = models.URLField()
    is_verified = models.BooleanField(default=False)
    submitted_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True, blank=True)


    def __str__(self):
        return f"KYC for {self.user}"
    

class SellerSocials(models.Model):
    """Model to store social media links for sellers"""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        primary_key=True,
    )
    facebook = models.URLField(max_length=255, blank=True, null=True)
    instagram = models.URLField(max_length=255, blank=True, null=True)
    tiktok = models.URLField(max_length=255, blank=True, null=True)

    def __str__(self):
        return f"Socials for {self.user}"
    

class Shop(models.Model):
    """Model for sellers shops."""
    class OwnerType(models.TextChoices):
        SELLER = 'seller', 'Seller'
        PLATFORM = 'platform', 'Platform'


    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner_type = models.CharField(
        max_length=20,
        choices=OwnerType.choices,
        default=OwnerType.SELLER
    )
    owner = models.ForeignKey(
        SellerKYC,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='seller_shops'
    )
    name = models.CharField(max_length=100, unique=True, blank=True, null=True)
    created_by_admin = models.BooleanField(default=False)
    location = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)


    def save(self, *args, **kwargs):
        """Override the save method"""
        if self.owner_type == self.OwnerType.PLATFORM:
            self.owner = None
            self.created_by_admin = True
        elif self.owner_type == self.OwnerType.SELLER and not self.owner:
            raise ValueError("Seller must be provided for seller owned shops.")
        super().save(*args, **kwargs)


    def __str__(self):
        return self.name
