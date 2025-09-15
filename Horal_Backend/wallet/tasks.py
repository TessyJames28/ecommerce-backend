from celery import shared_task
import logging
from django.utils.timezone import now

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=5, default_retry_delay=60*60)
def retry_payout(self, payout_id):
    """Retry payout failure caused by insufficient balance"""
    from .models import Payout, SellersBankDetails
    from .utils import initiate_payout, balance_topup

    try:
        payout = Payout.objects.get(id=payout_id)

        if payout.retry_count >= 5:
            logger.warning(f"Payout {payout.id} reached max retries.")
            payout.status = Payout.StatusChoices.FAILED
            payout.save(update_fields=["status"])
            return
        
        seller_bank = SellersBankDetails.objects.get(seller=payout.seller)

        result = initiate_payout(
            recipient_code=seller_bank.recipient_code,
            seller=payout.seller,
            amount_kobo=int(payout.amount_naira * 100),
            payout=payout,
            reason=payout.reason or "Payout Retry"
        )

        if isinstance(result, str):
            balance_topup(
                amount=payout.amount_naira,
                seller=payout.seller.full_name,
                reference_id=payout.reference_id,
                transfer_code=payout.paystack_transfer_code
            )

        else:
            # If not a transfer code, then it's a payout instance
            payout.retry_count += 1
            payout.last_retry_at = now()
            payout.save(update_fields=["retry_count", "last_retry_at"])
            logger.info(f"Payout {payout.id} still pending, retry {payout.retry_count}/5")

    except Exception as e:
        logger.error(f"Retry failed for payout {payout_id}: {e}")
        # requeue automatically until max_retries reached
        raise self.retry(exc=e)
    
