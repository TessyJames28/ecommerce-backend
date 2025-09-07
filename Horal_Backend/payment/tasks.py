from celery import shared_task
from .utils import fetch_and_store_bank
from wallet.utils import initiate_payout
from wallet.models import SellersBankDetails, Payout
from django.utils.timezone import now
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


@shared_task
def get_and_store_bank():
    fetch_and_store_bank()


@shared_task(bind=True, max_retries=settings.MAX_RETRIES)
def retry_payout_transfer(self, payout_id):
    """Celery task to handle the retry of payout"""

    try:
        payout = Payout.objects.get(id=payout_id)
    except Payout.DoesNotExist as e:
        logger.error(f"Payout with id {payout_id} not found in retry_payout_transfer: {str(e)}")
        return

    if payout.status == "success":
        return

    if payout.retry_count >= settings.MAX_RETRIES:
        logger.warning(f"Payout {payout_id} has reached max retries.")
        payout.status = "failed"
        payout.last_retry_at = now()
        payout.save(update_fields=["status", "last_retry_at"])
        return

    seller = SellersBankDetails.objects.get(seller=payout.seller)
    amount_kobo = payout.amount_naira * 100

    try:
        initiate_payout(
            seller.recipient_code, payout.seller,
            amount_kobo=amount_kobo,
            payout=payout
        )
        payout.retry_count += 1
        payout.save(update_fields=["retry_count"])
        logger.info(f"Payout {payout_id} retry initiated successfully.")

        # Schedule next retry if not successful
        self.retry(args=[payout_id], countdown=600)

    except Exception as e:
        logger.error(f"Error initiating payout for payout {payout_id}: {str(e)}")
        self.retry(args=[payout_id], countdown=600)

        