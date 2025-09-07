from django.db import models
from users.models import CustomUser
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
import uuid

# Create your models here.
class OrderStatusLog(models.Model):
    """Model to keep track of order log"""
    class OrderType(models.TextChoices):
        ORDER = "order", "Order"
        ORDERRETURNREQUEST = "order_return_request", "Order_Return_Request"

    order_type = models.CharField(
        max_length=20, choices=OrderType.choices,
        default=OrderType.ORDER
    )

    # Generic link to either Support or Return
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.UUIDField()  
    parent = GenericForeignKey('content_type', 'object_id')

    old_status = models.CharField(max_length=50)
    new_status = models.CharField(max_length=50)
    changed_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Order {self.object_id}: {self.old_status} → {self.new_status} by {self.changed_by}"


class PaystackTransaction(models.Model):
    """Model to handle paystack transaction response"""
    class StatusChoices(models.TextChoices):
        PENDING = 'pending', 'Pending'
        SUCCESS = 'success', 'Success'
        FAILED = 'failed', 'Failed'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference = models.CharField(max_length=100, unique=True, db_index=True)
    email = models.EmailField()
    order = models.ForeignKey(
        'orders.Order', # app_level.model_name
        on_delete=models.CASCADE, related_name="transactions",
        null=True, blank=True
    )
    user = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name="transactions")
    amount = models.PositiveIntegerField(help_text="Amount in Kobo")
    status = models.CharField(max_length=10, choices=StatusChoices.choices, default=StatusChoices.PENDING)
    gateway_response = models.TextField(blank=True, null=True)
    authorization_url = models.URLField(max_length=500, blank=True, null=True)
    access_code= models.CharField(max_length=50, blank=True, null=True)
    paid_at = models.DateTimeField(blank=True, null=True)
    refund_attempted = models.BooleanField(default=False)
    refund_successful = models.BooleanField(default=False)
    refund_response = models.JSONField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.email} - {self.reference} - {self.status}"