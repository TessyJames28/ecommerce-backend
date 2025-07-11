from django.db import models
from users.models import CustomUser
from products.models import ProductVariant
from carts.models import Cart
import uuid


# Create your models here.
class Order(models.Model):
    class Status(models.TextChoices):
        """Enum for order status"""
        PENDING = "pending", "Pending"
        PAID = "paid", "Paid"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"
        SHIPPED = "shipped", "Shipped"
        DELIVERED = "delivered", "Delivered"
        RETURN_REQUESTED = "return_requested", "Return Requested"
        RETURNED = "returned", "Returned"


    """Model to represents a user's placed order"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='orders')
    created_at = models.DateTimeField(auto_now_add=True)
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
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)


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
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    reason = models.TextField()
    approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)


    def __str__(self):
        return f"Return request for {self.order.id}"
