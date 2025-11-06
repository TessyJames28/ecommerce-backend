from django.db import models
from users.models import CustomUser, phone_number_validator
from products.models import ProductVariant
from carts.models import Cart
from sellers.models import SellerKYC
import uuid
from .utils import generate_reference


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
        DELIVERED = "delivered", "Delivered"
        ONGOING = "ongoing", "Ongoing"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='orders')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    discount_applied = models.BooleanField(default=False, db_index=True)
    
    # Financial fields
    product_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)  # product_total + shipping_cost
    shipping_total = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    status = models.CharField(max_length=50, choices=Status.choices, default=Status.PENDING)

    class Meta:
        indexes = [
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"Order #{self.id} by {self.user}"
    

    def get_carts(self):
        return Cart.objects.filter(user=self.user).first()
    


class OrderShipment(models.Model):
    """Represents a single shipment from a seller containing one or more order items."""

    class Status(models.TextChoices):
        """Enum for order status"""
        SHIPMENT_INITIATED = "shipment_initiated", "Shipment Initiated"
        ACCEPTED_AT_INVENTORY_FACILITY = "accepted_at_inventory_facility", "Accepted At Inventory Facility"
        ACCEPTED_AT_LAST_MILE_HUB = "accepted_at_last_mile_hub", "Accepted At Last Mile Hub"
        ASSIGNED_TO_A_RIDER = "assigned_to_a_rider", "Assigned To A Rider"
        DELIVERED = "delivered", "Delivered"
        DISPATCHED = "dispatched", "Dispatched"
        ENROUTE_TO_LAST_MILE_HUB = "enroute_to_last_mile_hub", "Enroute To Last Mile Hub"
        ENROUTE_TO_FIRST_MILE_HUB = "enroute_to_first_mile_hub", "Enroute To First Mile Hub"
        FAILED_PICKUP = "failed_pickup", "Failed Pick-Up"
        IN_RETURN_TO_CUSTOMER = "in_return_to_customer", "In Return To Customer"
        IN_RETURN_TO_FIRST_MILE_HUB = "in_return_to_first_mile_hub", "In Return To First Mile Hub"
        IN_RETURN_TO_LAST_MILE_HUB = "in_return_to_last_mile_hub", "In Return To Last Mile Hub"
        PENDING_PICKUP = "pending_pickup", "Pending Pick-Up"
        PENDING_RECIPIENT_PICKUP = "pending_recipient_pickup", "Pending Recipient Pick-Up"
        PICKED_UP = "picked_up", "Picked-Up"
        REJECTED_AT_INVENTORY_FACILITY = "rejected_at_inventory_facility", "Rejected At Inventory Facility"
        REJECTED_AT_LAST_MILE_HUB = "rejected_at_last_mile_hub", "Rejected At Last Mile Hub"
        RETURNED = "returned", "Returned"
        RETURNED_TO_FIRST_MILE_HUB = "returned_to_first_mile_hub", "Returned To First Mile Hub"
        RETURNED_TO_LAST_MILE_HUB = "returned_to_last_mile_hub", "Returned To Last Mile Hub"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="shipments")
    seller = models.ForeignKey(SellerKYC, on_delete=models.CASCADE, related_name="shipments")
    waybill_number = models.CharField(max_length=50, null=True, blank=True, db_index=True)
    fez_order_id = models.CharField(max_length=50, null=True, blank=True, db_index=True)
    status = models.CharField(max_length=50, choices=Status.choices, null=True, blank=True)
    unique_id = models.CharField(max_length=50, null=True, blank=True)
    batch_id = models.CharField(max_length=50, null=True, blank=True)
    quantity = models.PositiveIntegerField(null=True, blank=True)
    total_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_weight = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    delivered_at = models.DateTimeField(null=True, blank=True)

    # reminder flags for the shipment
    reminder_2h_sent = models.BooleanField(default=False, db_index=True)
    reminder_24h_sent = models.BooleanField(default=False, db_index=True)
    reminder_48h_sent = models.BooleanField(default=False, db_index=True)

    # Auto completion of order
    auto_completion = models.BooleanField(default=False)
    auto_completion_email_sent = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["seller", "order"]),
        ]

    def __str__(self):
        return f"Shipment #{self.id} for Order {self.order.id}"

    

class OrderItem(models.Model):
    """Model that represent each variant ordered in the order"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='order_items')
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE)
    shipment = models.ForeignKey(OrderShipment, on_delete=models.CASCADE, related_name="items", null=True, blank=True)
    quantity = models.PositiveIntegerField()
    is_returned = models.BooleanField(default=False, db_index=True)
    is_return_requested = models.BooleanField(default=False, db_index=True)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    is_completed = models.BooleanField(default=False, db_index=True)
    delivered_at = models.DateTimeField(null=True, blank=True, db_index=True)
    

    @property
    def total_price(self):
        return self.unit_price * self.quantity
    

    def __str__(self):
        return f"{self.variant} X {self.quantity}"

    class Meta:
        indexes = [
            models.Index(fields=["order", "variant"]),
            models.Index(fields=["shipment", "variant"])
        ]
        
    

class OrderReturnRequest(models.Model):

    """
    Model to handle order cancellation
    Users request for order refund
    """

    class Status(models.TextChoices):
        REQUESTED = "requested", "Requested"
        PROCESSING = "processing", "Processing"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        COMPLETED = "completed", "Completed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_item = models.ForeignKey(OrderItem, on_delete=models.CASCADE, related_name="order_return_request")
    reason = models.TextField()
    reference = models.CharField(
        max_length=12, unique=True, editable=False,
        default=generate_reference
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.REQUESTED)
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["order_item", "status"]),
        ]


    def __str__(self):
        return f"Return request for {self.order_item.id}"


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


# maps external logistics status label to internal enum value
FEZ_STATUS_MAP = {
    "Accepted At Inventory Facility": OrderShipment.Status.ACCEPTED_AT_INVENTORY_FACILITY,
    "Accepted At Last Mile Hub": OrderShipment.Status.ACCEPTED_AT_LAST_MILE_HUB,
    "Assigned To A Rider": OrderShipment.Status.ASSIGNED_TO_A_RIDER,
    "Delivered": OrderShipment.Status.DELIVERED,
    "Dispatched": OrderShipment.Status.DISPATCHED,
    "Enroute To Last Mile Hub": OrderShipment.Status.ENROUTE_TO_LAST_MILE_HUB,
    "Enroute To First Mile Hub": OrderShipment.Status.ENROUTE_TO_FIRST_MILE_HUB,
    "Failed Pick-Up": OrderShipment.Status.FAILED_PICKUP,
    "In Return To Customer": OrderShipment.Status.IN_RETURN_TO_CUSTOMER,
    "In Return To First Mile Hub": OrderShipment.Status.IN_RETURN_TO_FIRST_MILE_HUB,
    "In Return To Last Mile Hub": OrderShipment.Status.IN_RETURN_TO_LAST_MILE_HUB,
    "Pending Pick-Up": OrderShipment.Status.PENDING_PICKUP,
    "Picked-Up": OrderShipment.Status.PICKED_UP,
    "Rejected At Inventory Facility": OrderShipment.Status.REJECTED_AT_INVENTORY_FACILITY,
    "Rejected At Last Mile Hub": OrderShipment.Status.REJECTED_AT_LAST_MILE_HUB,
    "Returned": OrderShipment.Status.RETURNED,
    "Returned To First Mile Hub": OrderShipment.Status.RETURNED_TO_FIRST_MILE_HUB,
    "Returned To Last Mile Hub": OrderShipment.Status.RETURNED_TO_LAST_MILE_HUB,
}
