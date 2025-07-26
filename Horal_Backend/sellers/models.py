from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from users.models import phone_number_validator
import uuid


class KYCStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    FAILED = 'failed', 'Failed'
    VERIFIED = 'verified', 'Verified'


class SellerKYCCAC(models.Model):
    """Model to store sellers CAC detail"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    rc_number = models.CharField(max_length=8, unique=True)
    company_type = models.CharField(max_length=255)
    company_name = models.CharField(max_length=50, null=True, blank=True)
    status = models.CharField(max_length=20, choices=KYCStatus, default=KYCStatus.PENDING)
    cac_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)


class SellerKYCNIN(models.Model):
    """Model to store sellers NIN for kyc verification"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nin = models.CharField(max_length=11, unique=True)
    selfie = models.URLField()
    status = models.CharField(max_length=20, choices=KYCStatus, default=KYCStatus.PENDING)
    nin_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)


class SellerKYCAddress(models.Model):
    """Model to store sellers Address info"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    first_name = models.CharField(max_length=225)
    last_name = models.CharField(max_length=225)
    middle_name = models.CharField(max_length=225, default=None)
    dob = models.DateField()
    gender = models.CharField(max_length=20)
    mobile = models.CharField(
        max_length=11,
        unique=True,
        validators=[phone_number_validator],
    )
    street = models.CharField(max_length=500)
    landmark = models.CharField(max_length=250)
    lga = models.CharField(max_length=50)
    state = models.CharField(max_length=50)
    business_name = models.CharField(max_length=200)
    # status = models.CharField(max_length=20, choices=KYCStatus, default=KYCStatus.PENDING)
    # address_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)



class SellerSocials(models.Model):
    """Model to store social media links for sellers"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    facebook = models.URLField(max_length=255, blank=True, null=True, unique=True)
    instagram = models.URLField(max_length=255, blank=True, null=True, unique=True)
    tiktok = models.URLField(max_length=255, blank=True, null=True, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)


class SellerKYC(models.Model):
    """Model to store KYC documents for sellers"""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name='kyc'
    )
    country = models.CharField(max_length=100, default='Nigeria')
    nin = models.OneToOneField(SellerKYCNIN, on_delete=models.PROTECT, null=True, blank=True)
    cac = models.OneToOneField(SellerKYCCAC, on_delete=models.SET_NULL, null=True)
    address = models.OneToOneField(SellerKYCAddress, on_delete=models.PROTECT, null=True)
    socials = models.OneToOneField(SellerSocials, on_delete=models.PROTECT, null=True, blank=True)
    status = models.CharField(max_length=20, choices=KYCStatus, default=KYCStatus.PENDING)
    is_verified = models.BooleanField(default=False)
    info_completed_notified = models.BooleanField(default=False)
    status_notified = models.BooleanField(default=False)

    submitted_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True, blank=True)


    def __str__(self):
        return f"KYC for {self.user.full_name}"
    