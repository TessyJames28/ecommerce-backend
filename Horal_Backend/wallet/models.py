from django.db import models
from users.models import CustomUser
from django.core.validators import RegexValidator
import uuid
from django.utils.translation import gettext_lazy as _
from django.utils.timezone import now

account_number_validator = RegexValidator(
    regex=r'^\d{10}$',
    message=_("account number must be exactly 10 digits long."),
)


# Create your models here.
class Bank(models.Model):
    """
    Model to collect and store bank codes for name matching
    """
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=10)
    slug = models.CharField(max_length=100, blank=True, null=True)
    active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} ({self.code})"


class SellersBankDetails(models.Model):
    """
    Model to collect sellers bank details for
    verification and storage
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    seller = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="seller_bank")
    bank_name = models.CharField(max_length=150)
    account_number = models.CharField(max_length=10, unique=True, validators=[account_number_validator])
    bank_code = models.CharField(max_length=10)
    account_name = models.CharField(max_length=150)
    recipient_code = models.CharField(max_length=50, blank=True, null=True)

    def __str__(self):
        return self.bank_name


class Payout(models.Model):
    """Model to handle sellers payout"""
    class StatusChoices(models.TextChoices):
        PROCESSING = "processing", "Processing"
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    seller = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="payout")
    reference_id = models.CharField(max_length=100)
    total_withdrawable = models.DecimalField(max_digits=12, decimal_places=2)
    commission = models.DecimalField(max_digits=12, decimal_places=2)
    amount_naira = models.DecimalField(max_digits=12, decimal_places=2)
    paystack_transfer_code = models.CharField(max_length=100, blank=True, null=True)
    retry_count = models.SmallIntegerField(default=0)
    last_retry_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=StatusChoices.choices, default=StatusChoices.PROCESSING)
    reason = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(default=now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Payout to {self.seller.full_name} - {self.status}"


class SellerTransactionHistory(models.Model):
    """Model to populate all sellers transaction history"""
    class TransactionType(models.TextChoices):
        WITHDRAWAL = "withdrawal", "Withdrawal"
        ORDER = "order", "Order"

    
    class TransactionStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    seller = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="transaction_history")
    reference_id = models.CharField(max_length=100)
    message = models.TextField()
    transaction_type = models.CharField(max_length=20, choices=TransactionType.choices, default=TransactionType.ORDER)
    transaction_status = models.CharField(max_length=20, choices=TransactionStatus.choices, default=TransactionStatus.PENDING)    
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.message}"
    