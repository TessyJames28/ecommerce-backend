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
        SHIPMENT_CREATED = "shipment_created", "Shipment Created (CRT)"
        SHIPMENT_CREATED_BY_CUSTOMER = "shipment_created_by_customer", "Shipment Created by Customer (MCRT)"
        AVAILABLE_FOR_PICKUP = "available_for_pickup", "Available for Pick-Up (AD)"
        SHIPMENT_PICKED_UP = "shipment_picked_up", "Shipment Picked Up (MPIK)"
        SHIPMENT_ARRIVED_FINAL_DESTINATION = "shipment_arrived_final_destination", "Shipment Arrived Final Destination (MAFD)"
        OUT_FOR_DELIVERY = "out_for_delivery", "Out for Delivery / With Courier (OFDU)"
        DELIVERED_TO_CUSTOMER_ADDRESS = "delivered_to_customer_address", "Delivered to Customer Address (MAHD)"
        DELIVERED_TO_PICKUP_POINT = "delivered_to_pickup_point", "Delivered to Pickup Point (OKC)"
        DELIVERED_TO_TERMINAL = "delivered_to_terminal", "Delivered to Terminal (OKT)"
        DELAYED_DELIVERY = "delayed_delivery", "Delayed Delivery (DLD)"
        DELAYED_PICKUP = "delayed_pickup", "Delayed Pickup (DLP)"
        DELAYED_PICKUP_BY_CUSTOMER = "delayed_pickup_by_customer", "Delayed Pickup By Customer"


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

    # Set delivery and pickup stations
    # seller_station = models.PositiveIntegerField()
    # buyer_station = models.PositiveIntegerField()

    # reminder flags for the shipment
    reminder_2h_sent = models.BooleanField(default=False, db_index=True)
    reminder_24h_sent = models.BooleanField(default=False, db_index=True)
    reminder_48h_sent = models.BooleanField(default=False, db_index=True)

    # Auto completion of order
    auto_completion = models.BooleanField(default=False)

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


GIGL_TO_ORDER_STATUS = {
    'CRT': OrderShipment.Status.SHIPMENT_CREATED,
    'MCRT': OrderShipment.Status.SHIPMENT_CREATED_BY_CUSTOMER,
    'AD': OrderShipment.Status.AVAILABLE_FOR_PICKUP,
    'MPIK': OrderShipment.Status.SHIPMENT_PICKED_UP,
    'OFDU': OrderShipment.Status.OUT_FOR_DELIVERY,
    'MAFD': OrderShipment.Status.SHIPMENT_ARRIVED_FINAL_DESTINATION,
    'MAHD': OrderShipment.Status.DELIVERED_TO_CUSTOMER_ADDRESS,
    'OKC': OrderShipment.Status.DELIVERED_TO_PICKUP_POINT,
    'OKT': OrderShipment.Status.DELIVERED_TO_TERMINAL,
    'DLD': OrderShipment.Status.DELAYED_DELIVERY,
    'DLP': OrderShipment.Status.DELAYED_PICKUP,
    'DUBC': OrderShipment.Status.DELAYED_PICKUP_BY_CUSTOMER
}


PICKUP_STATUSES = [
    OrderShipment.Status.AVAILABLE_FOR_PICKUP,
]

DELIVERED_STATUSES = [
    OrderShipment.Status.DELIVERED_TO_CUSTOMER_ADDRESS,
    OrderShipment.Status.DELIVERED_TO_PICKUP_POINT,
    OrderShipment.Status.DELIVERED_TO_TERMINAL,
]

DELAY_STATUSES = [
    OrderShipment.Status.DELAYED_DELIVERY,
]

DELAY_STATUSES_CUSTOMER = [
    OrderShipment.Status.DELAYED_PICKUP,
    OrderShipment.Status.DELAYED_PICKUP_BY_CUSTOMER,
]
