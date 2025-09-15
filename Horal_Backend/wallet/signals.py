from .models import SellerTransactionHistory, Payout, SellersBankDetails
from orders.models import OrderItem, Order
from .tasks import retry_payout
from django.db.models.signals import post_save
from django.dispatch import receiver, Signal
from django.conf import settings
from django.utils.timezone import now
from notifications.tasks import send_email_task
from django.conf import settings
import uuid


payout_retry_signal = Signal()

@receiver(payout_retry_signal)
def schedule_payout_retry(sender, payout, **kwargs):
    # Schedule retries — e.g. every 1 hour up to 5 hours
    retry_payout.apply_async((payout.id,), countdown=60*300)  # 5 hour later


@receiver(post_save, sender=OrderItem)
def order_item_transaction(sender, instance, created, **kwargs):
    """
    Populate transaction history for orders:
    - Create PENDING record when delivered but not yet paid
    - Create COMPLETED record when payout is done
    """
    if not instance.is_completed or instance.delivered_at:
        return 
    
    seller = instance.variant.shop.owner.user
    amount = instance.unit_price * instance.quantity
    
    # Avoid duuplicate checks if transaction record already exists
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
    if instance.status not in [
        Payout.StatusChoices.PROCESSING,
        Payout.StatusChoices.SUCCESS,
        Payout.StatusChoices.FAILED
    ]:
        return
    
    # Find existing record
    record = SellerTransactionHistory.objects.filter(
        seller=instance.seller,
        transaction_status=SellerTransactionHistory.TransactionStatus.PENDING,
        transaction_type=SellerTransactionHistory.TransactionType.WITHDRAWAL,
        reference_id=getattr(instance, "reference_id", None)
    ).first()

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


@receiver(post_save, sender=Payout)
def notify_seller_of_initiated_withdrawal(sender, instance, **kwargs):
    """
    Signal to send email to seller after initiating withdrawal
    """
    if instance.status != Payout.StatusChoices.PROCESSING:
        return
    
    if instance.email_sent and instance.status == Payout.StatusChoices.PROCESSING:
        return
    
    # Get seller bank details
    bank_details = SellersBankDetails.objects.get(seller=instance.seller)

    recipient = instance.seller.email
    seller_name = instance.seller.full_name
    amount = instance.amount_naira
    transaction_id = instance.id
    bank_name = bank_details.bank_name
    expected_arrival = "Within 1-2 business days"

    subject = "Congratulations on Successful Withdrawal"
    from_email = f"Horal Wallet <{settings.DEFAULT_FROM_EMAIL}>"

    send_email_task.delay(
        recipient=recipient,
        subject=subject,
        from_email=from_email,
        template_name="notifications/emails/withdrawal_email.html",
        context={
            "seller_name": seller_name,
            "withdrawal_amount": amount,
            "transaction_id": transaction_id,
            "bank_name": bank_name,
            "expected_arrival": expected_arrival
        }
    )

    # Mark as sent
    Payout.objects.filter(id=instance.id).update(email_sent=True)


@receiver(post_save, sender=Payout)
def notify_seller_of_transfer_success(sender, instance, **kwargs):
    """
    Signal to send email to seller after successful transfer
    """
    if instance.status not in [
        Payout.StatusChoices.SUCCESS,
        Payout.StatusChoices.FAILED
    ]:
        return
    
    # Get seller bank details
    bank_details = SellersBankDetails.objects.get(seller=instance.seller)

    recipient = instance.seller.email
    seller_name = instance.seller.full_name
    amount = instance.amount_naira
    transaction_id = instance.id
    bank_name = bank_details.bank_name
    from_email = f"Horal Wallet <{settings.DEFAULT_FROM_EMAIL}>"

    if instance.status == Payout.StatusChoices.SUCCESS:
        body_paragraphs = [
            f"Congratulations! Your recent withdrawal has been successfully processed. The funds has been delivered to your bank account."
        ]
        subject = "Transfer Successful"

    elif instance.status == Payout.StatusChoices.FAILED:
        body_paragraphs = [
            f"Unfortunately, we are unable to process your withdrawal for the below transaction. Kindly initiate an another withdrawal.",
            f"We are sorry for the inconvenience."
        ]
        subject = "Transfer Failure"

    send_email_task.delay(
        recipient=recipient,
        subject=subject,
        from_email=from_email,
        template_name="notifications/emails/withdrawal_template.html",
        context={
            "seller_name": seller_name,
            "body_paragraphs": body_paragraphs,
            "withdrawal_amount": amount,
            "transaction_id": transaction_id,
            "bank_name": bank_name,
        }
    )
