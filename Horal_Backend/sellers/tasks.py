from celery import shared_task
from django.utils.timezone import now
from .models import SellerKYC, KYCStatus, SellerKYCCAC, SellerKYCNIN
from django.db import IntegrityError
from users.models import CustomUser
from shops.models import Shop
import logging

logger = logging.getLogger(__name__)


@shared_task
def verify_seller_kyc(kyc_id):
    try:
        kyc = SellerKYC.objects.get(user_id=kyc_id)

        # Force fresh queries to related models
        nin = SellerKYCNIN.objects.get(id=kyc.nin_id) if kyc.nin_id else None
        cac = SellerKYCCAC.objects.get(id=kyc.cac_id) if kyc.cac_id else None

        if kyc.nin and kyc.nin.status == KYCStatus.FAILED:
            kyc.status = KYCStatus.FAILED
            kyc.is_verified = False

        elif kyc.nin and kyc.nin.nin_verified and (
            not kyc.cac or (kyc.cac and kyc.cac.cac_verified)
        ):
            if not kyc.is_verified:
                kyc.is_verified = True
                kyc.status = KYCStatus.VERIFIED

                # update seller profile and create shop
                user = CustomUser.objects.get(id=kyc_id)
                user.is_seller = True
                user.save(update_fields=['is_seller'])

                # Decide shop name base
                business_name = (kyc.address.business_name or "").strip()
                first_name = kyc.address.first_name
                last_name = kyc.address.last_name

                if business_name:
                    shop_name = business_name

                    # If already taken, use first name + business name
                    if Shop.objects.filter(name=shop_name).exists():
                        shop_name = f"{first_name} {business_name}".strip()

                        # Fallback: use last name + business name if taken
                        if Shop.objects.filter(name=shop_name).exists():
                            shop_name = f"{last_name} {business_name}".strip()

                            # Final fallback: use business name + user id slice
                            if Shop.objects.filter(name=shop_name).exists():
                                shop_name = f"{business_name}-{user.id[0:4]}"
                else:
                    shop_name = f"{first_name} {last_name}'s shop"

                shop, _ = Shop.objects.get_or_create(
                    owner=kyc,
                    defaults= {"name": shop_name}
                )

        kyc.verified_at = now()
        kyc.save(update_fields=["is_verified", "status", "verified_at"])
        
    except SellerKYC.DoesNotExist:
        pass

    logger.info("Scheduled Celery task ran.")

