from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
import os

# Create your models here.
def upload_to(instance, filename):
    """Function to define the upload path for KYC documents"""
    return f'kyc_documents/seller{instance.user.id}/{filename}'


def validate_file_extension(value):
    """Validator to check the file extension of uploaded documents"""
    ext = os.path.splitext(value.name)[1]  # Get the file extension
    valid_extensions = ['.pdf', '.jpg', '.jpeg', '.png']
    if not ext.lower() in valid_extensions:
        raise ValidationError(
            _('Unsupported file extension. Allowed extensions: %(valid_extensions)s'),
        )


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
    nin = models.FileField(
        upload_to=upload_to,
        null=False,
        blank=False,
        help_text="Upload a government-issued ID (pdf, jpg, png)"
    )
    cac = models.FileField(
        upload_to=upload_to,
        null=True,
        blank=True,
        help_text="Upload a CAC Certificate (pdf, jpg, png)"
    )
    utility_bill = models.FileField(
        upload_to=upload_to,
        null=True,
        blank=True,
        help_text="Upload a proof of address (utility bill, bank statement, etc as pdf, jpg, png)"
    )
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
