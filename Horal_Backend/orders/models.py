from django.db import models
from users.models import CustomUser, phone_number_validator
from products.models import ProductVariant
from carts.models import Cart
import uuid


# Create your models here.
class ShippingSnapshotMixin(models.Model):
    street_address = models.CharField(max_length=500, blank=True, null=True)
    local_govt = models.CharField(max_length=150, blank=True, null=True)
    landmark = models.CharField(max_length=150, blank=True, null=True)
    country = models.CharField(max_length=50, blank=True, null=True, default="Nigeria")
    state = models.CharField(max_length=50, default="Lagos", blank=True, null=True  )
    phone_number = models.CharField(max_length=11, validators=[phone_number_validator], blank=True, null=True)

    class Meta:
        abstract = True


class Order(ShippingSnapshotMixin, models.Model):
    """Model to represents a user's placed order"""
    class Status(models.TextChoices):
        """Enum for order status"""
        PENDING = "pending", "Pending"
        PAID = "paid", "Paid"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"
        SHIPPED = "shipped", "Shipped"
        AT_PICK_UP= "at_pick_up", "At_Pick_Up"
        DELIVERED = "delivered", "Delivered"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='orders')
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=50, choices=Status.choices, default=Status.PENDING)

    def __str__(self):
        return f"Order #{self.id} by {self.user}"
    

    def get_carts(self):
        return Cart.objects.filter(user=self.user).first()
    

class OrderItem(models.Model):
    """Model that represent each variant ordered in the order"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='order_items')
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    is_returned = models.BooleanField(default=False)
    is_return_requested = models.BooleanField(default=False)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    is_completed = models.BooleanField(default=False)
    delivered_at = models.DateTimeField(null=True, blank=True)

    @property
    def total_price(self):
        return self.unit_price * self.quantity
    

    def __str__(self):
        return f"{self.variant} X {self.quantity}"
    

class OrderReturnRequest(models.Model):

    """
    Model to handle order cancellation
    Users request for order refund
    """

    class Status(models.TextChoices):
        REQUESTED = "requested", "Requested"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        COMPLETED = "completed", "Completed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_item = models.ForeignKey(OrderItem, on_delete=models.CASCADE, related_name="order_return_request")
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.REQUESTED)
    approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)


    def __str__(self):
        return f"Return request for {self.order.id}"


    def save(self, *args, **kwargs):
        """Override save to sync with OrderItem fields"""
        is_new = self._state.adding # True if creating, False if updating
        super().save(*args, **kwargs)

        order_item = self.order_item

        if self.status == self.Status.REQUESTED:
            order_item.is_return_requested = True
            order_item.is_returned = False
        elif self.status == self.Status.APPROVED:
            order_item.is_return_requested = True
            order_item.is_returned = False
        elif self.status == self.Status.REJECTED:
            order_item.is_return_requested = False
            order_item.is_returned = False
        elif self.status == self.Status.COMPLETED:
            order_item.is_return_requested = True
            order_item.is_returned = True

        order_item.save(update_fields=["is_return_requested", "is_returned"])
