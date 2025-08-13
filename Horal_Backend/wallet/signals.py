from .models import SellerTransactionHistory, Payout
from orders.models import OrderItem, Order
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from django.utils.timezone import now
import uuid


@receiver(post_save, sender=OrderItem)
def order_item_transaction(sender, instance, created, **kwargs):
    """
    Populate transaction history for orders:
    - Create PENDING record when delivered but not yet paid
    - Create COMPLETED record when payout is done
    """
    if not instance.is_completed or instance.order.status != Order.Status.DELIVERED:
        return 
    
    seller = instance.variant.shop.owner.user
    amount = instance.unit_price * instance.quantity
    
    # Aoid duuplicate checks if transaction record already exists
    record = SellerTransactionHistory.objects.filter(
        seller=seller,
        message__icontains=f"order #{instance.order.id}",
        transaction_status=SellerTransactionHistory.TransactionStatus.PENDING,
        transaction_type=SellerTransactionHistory.TransactionType.ORDER
    ).first()

    if record and instance.is_completed:
        # Create record for the same refernce id
        SellerTransactionHistory.objects.create(
            seller=seller,
            reference_id=record.reference_id,
            amount=record.amount,
            transaction_status=SellerTransactionHistory.TransactionStatus.COMPLETED,
            transaction_type=SellerTransactionHistory.TransactionType.ORDER,
            message=f"You have received payment for order #{instance.order.id}"
        )

    elif not record:
        # create a new pending record for delivered order
        SellerTransactionHistory.objects.create(
            seller=seller,
            amount=amount,
            reference_id=str(uuid.uuid4()),
            message=f"You have a pending payment for order #{instance.order.id}",
            transaction_type=SellerTransactionHistory.TransactionType.ORDER,
            transaction_status=SellerTransactionHistory.TransactionStatus.PENDING
        )


@receiver(post_save, sender=Payout)
def payout_transaction(sender, instance, created, **kwargs):
    """
    Populate transaction history for withdrawals:
    - Create PENDING record when withdrawal requested
    - Create COMPLETED record when successful
    """
    print(f"signal triggered: {instance.status}")
    if instance.status not in [
        Payout.StatusChoices.PROCESSING,
        Payout.StatusChoices.SUCCESS,
        Payout.StatusChoices.FAILED
    ]:
        value = instance.status == Payout.StatusChoices.SUCCESS
        print(f"Payout status: {Payout.StatusChoices.SUCCESS}")
        print(f"Value: {value}")
        return
    
    # Find existing record
    record = SellerTransactionHistory.objects.filter(
        seller=instance.seller,
        transaction_status=SellerTransactionHistory.TransactionStatus.PENDING,
        transaction_type=SellerTransactionHistory.TransactionType.WITHDRAWAL,
        reference_id=getattr(instance, "reference_id", None)
    ).first()
    print(f"Record: {record}")

    if record and instance.status == Payout.StatusChoices.SUCCESS:
        SellerTransactionHistory.objects.create(
            seller=instance.seller,
            amount=record.amount,
            reference_id=record.reference_id,
            message=f"Your withdrawal {record.amount} is successful",
            transaction_type=SellerTransactionHistory.TransactionType.WITHDRAWAL,
            transaction_status=SellerTransactionHistory.TransactionStatus.COMPLETED
        )
    elif record and (instance.retry_count >= settings.MAX_RETRIES and instance.status == Payout.StatusChoices.FAILED):
        SellerTransactionHistory.objects.create(
            seller=instance.seller,
            amount=record.amount,
            reference_id=record.reference_id,
            message=f"Your withdrawal {record.amount} failed",
            transaction_type=SellerTransactionHistory.TransactionType.WITHDRAWAL,
            transaction_status=SellerTransactionHistory.TransactionStatus.FAILED
        )
    elif not record and instance.status == Payout.StatusChoices.PROCESSING:
        SellerTransactionHistory.objects.create(
            seller=instance.seller,
            amount=instance.amount_naira,
            reference_id=instance.reference_id,
            message=f"You have a pending withdrawal {instance.amount_naira}",
            transaction_type=SellerTransactionHistory.TransactionType.WITHDRAWAL,
            transaction_status=SellerTransactionHistory.TransactionStatus.PENDING
        )
