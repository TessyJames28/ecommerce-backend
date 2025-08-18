from celery import shared_task
from .utils import fetch_and_store_bank
from wallet.utils import initiate_payout
from wallet.models import SellersBankDetails, Payout
from django.utils.timezone import now
from django.conf import settings


@shared_task
def get_and_store_bank():
    fetch_and_store_bank()


@shared_task(bind=True, max_retries=settings.MAX_RETRIES)
def retry_payout_transfer(self, payout_id):
    """Celery task to handle the retry of payout"""
    print(f"[Celery] Retrying payout {payout_id}")

    try:
        payout = Payout.objects.get(id=payout_id)
    except Payout.DoesNotExist:
        print(f"[Celery] Payout {payout_id} not found.")
        return

    if payout.status == "success":
        print(f"[Celery] Payout {payout_id} already successful. Stopping retries.")
        return

    if payout.retry_count >= settings.MAX_RETRIES:
        print(f"[Celery] Max retries reached for payout {payout_id}. Marking failed.")
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
        print(f"[Celery] Retry #{payout.retry_count} scheduled again.")

        # Schedule next retry if not successful
        self.retry(args=[payout_id], countdown=600)

    except Exception as e:
        print(f"[Celery] Error initiating payout: {e}")
        self.retry(args=[payout_id], countdown=600)

        