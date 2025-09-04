from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
import uuid

User = get_user_model()

class Notification(models.Model):
    """Unified notification model"""
    class ChannelChoices(models.TextChoices):
        EMAIL = "email", "Email"
        INAPP = "inapp", "In-App"
        SMS = "sms", "SMS"
        PUSH = "push", "Push"

    class Type(models.TextChoices):
        WELCOME = "welcome", "Welcome"
        ORDER = "order", "Order"
        ORDER_RETURN = "order_return", "Order Return"
        SUPPORT = "support", "Support Message"
        GENERAL = "general", "General"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"
        READ = "read", "Read"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")
    type = models.CharField(max_length=50, choices=Type.choices)
    channel = models.CharField(max_length=20, choices=ChannelChoices.choices, default=ChannelChoices.INAPP)
    subject = models.CharField(max_length=255, blank=True, null=True)
    message = models.TextField()

    # Generic relation to link notification to any model (Order, SupportTicket, etc.)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.UUIDField()
    parent = GenericForeignKey("content_type", "object_id")

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)  # pending, sent, failed, read
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)

    def mark_as_read(self):
        self.status = "read"
        self.is_read = True
        self.read_at = timezone.now()
        self.save(update_fields=["status", "read_at", "is_read"])

