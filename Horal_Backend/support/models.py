from django.db import models
from users.models import CustomUser
from orders.models import OrderReturnRequest
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
import uuid
from .utils import generate_reference

# Create your models here.
  

class Support(models.Model):
    """Model to handle customer support form"""
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        UNRESOLVED = "unresolved", "Unresolved"
        RESOLVED = "resolved", "Resolved"

    class Source(models.TextChoices):
        WEBFORM = "webform", "Webform"
        EMAIL = "email", "Email"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE,
        null=True, blank=True,
        related_name="customer_support"
    )
    source = models.CharField(
        max_length=20,
        choices=Source.choices,
        default=Source.WEBFORM
    )
    reference = models.CharField(
        max_length=12, unique=True, editable=False,
        default=generate_reference
    )
    email = models.EmailField()
    subject = models.CharField(max_length=150)
    body = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Support for customer {self.email} on {self.subject} - {self.status}"


class Message(models.Model):
    """
    Model to track email exchange / messages between
    customers and support staff for a support ticket
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Generic link to either Support or Return
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.UUIDField()  
    parent = GenericForeignKey('content_type', 'object_id')

    sender = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="sent_support_messages"
    )
    team_email = models.EmailField(null=True, blank=True)
    subject = models.CharField(max_length=150, blank=True, null=True)
    body = models.TextField()
    sent_at = models.DateTimeField(auto_now_add=True)
    from_staff = models.BooleanField(default=False)

    def __str__(self):
        direction = "Staff" if self.from_staff else "Customer"
        return f"{direction} message for ticket {self.parent}"


class SupportAttachment(models.Model):
    """Class for multiple attachment"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    message = models.ForeignKey(
        Message, on_delete=models.CASCADE,
        related_name="attachments"
    )
    url = models.URLField(null=True, blank=True)
    alt = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return f"Attachment for message {self.message.id}"
    


class SupportTeam(models.Model):
    """Model to add support teams"""
    team = models.OneToOneField(
        CustomUser, primary_key=True,
        related_name="support_team",
        on_delete=models.PROTECT
    )
    name = models.CharField(max_length=250)
    email = models.EmailField()
    current_tickets = models.PositiveIntegerField(default=0)
    completed_tickets = models.PositiveIntegerField(default=0)
    total_tickets = models.PositiveIntegerField(default=0)
    is_lead = models.BooleanField(default=False)
    added_at = models.DateTimeField(auto_now_add=True)
    last_completed = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.name} =>\n\tTotal Tickets: {self.total_tickets}\n\t \
            Current Tickets: {self.current_tickets}\n\tCompleted Tickets: {self.completed_tickets}"


class Tickets(models.Model):
    """
    Model to aggregate all customer support request
    Also assign tickets to individual team member
    """
    class State(models.TextChoices):
        ASSIGNED = "assigned", "Assigned"
        UNASSIGNED = "unassigned", "Unassigned"


    class Status(models.TextChoices):
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"

    
    class TicketType(models.TextChoices):
        RETURNS = "returns", "Returns"
        SUPPORT = "support", "Support"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket_type = models.CharField(max_length=20, choices=TicketType.choices)
    
    # Generic link to either Support or Return
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.UUIDField()  
    parent = GenericForeignKey('content_type', 'object_id')

    ticket_state = models.CharField(max_length=20, choices=State.choices, default=State.UNASSIGNED)
    assigned_to = models.ForeignKey(
        SupportTeam, on_delete=models.SET_NULL,
        related_name="assigned_team",
        null=True, blank=True
    )
    re_assigned = models.BooleanField(default=False)
    re_assigned_to = models.ForeignKey(
        SupportTeam, on_delete=models.SET_NULL,
        related_name="re_assigned_team",
        null=True, blank=True
    )
    status = models.CharField(max_length=20, choices=Status.choices, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    assigned_at = models.DateTimeField(null=True, blank=True)
    re_assigned_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
