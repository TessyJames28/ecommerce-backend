from django.db import models
from sellers.models import SellerKYC
import uuid

# Create your models here.

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
        on_delete=models.CASCADE,
        related_name='owner'
    )
    name = models.CharField(max_length=100, unique=True, blank=True, null=True)
    created_by_admin = models.BooleanField(default=False)
    # location = models.CharField(max_length=255)
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
