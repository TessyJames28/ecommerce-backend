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


class Station(models.Model):
    station_id = models.IntegerField(unique=True)  # API stationId
    station_name = models.CharField(max_length=255)
    station_code = models.CharField(max_length=10, blank=True, null=True)
    state_id = models.IntegerField()
    state_name = models.CharField(max_length=255, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.station_name} - {self.state_name}"
    

class GIGLExperienceCentre(models.Model):
    """Model to store all GIGL experience centers"""
    # Station address, longitute and latitude
    address = models.CharField(max_length=255)
    state = models.CharField(max_length=50, db_index=True)
    centre_name = models.CharField(max_length=50)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.state} => {self.address}"


class GIGLWebhookCredentials(models.Model):
    """
    Store the webhook credentials for GIGL
    and allow verification of incoming webhook events
    """
    user_id = models.UUIDField(unique=True)
    channel_code = models.CharField(max_length=20, unique=True)
    secret = models.CharField(max_length=255)
    webhook_url = models.URLField(max_length=500)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.channel_code} ({self.user_id})"


class GIGLShipment(models.Model):
    """
    Store decrypted shipment data from GIGL webhook.
    Each record corresponds to a shipment (waybill).
    Status can be updated whenever a new webhook event is received.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_shipment = models.ForeignKey(
        'orders.OrderShipment', on_delete=models.PROTECT,
        related_name="shipment_item"
    )
    waybill = models.CharField(max_length=50, unique=True)
    sender_address = models.TextField()
    receiver_address = models.TextField()
    location = models.CharField(max_length=255, null=True, blank=True)
    status = models.CharField(max_length=255)
    status_code = models.CharField(max_length=20, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.waybill} - {self.status}"

