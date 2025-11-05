from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from products.textchoices import LogisticSizeUnit
from django.core.exceptions import ValidationError
from products.models import ProductVariant
import uuid

# Create your models here.

class Logistics(models.Model):
    """Logistic feature for handling product weight"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product_variant = models.ForeignKey(
        ProductVariant, on_delete=models.CASCADE,
        related_name="logistics_variant",
        null=True, blank=True
    )
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.UUIDField(null=True, blank=True)
    product = GenericForeignKey('content_type', 'object_id')

    weight_measurement = models.CharField(max_length=10, choices=LogisticSizeUnit.choices)
    total_weight = models.DecimalField(max_digits=5, decimal_places=2)
    

    def __str__(self):
        target = self.product_variant or self.product
        return f"{target} - {self.total_weight}{self.weight_measurement}"
