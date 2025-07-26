from celery import shared_task
from django.utils.timezone import now
from .models import SellerKYC, KYCStatus, SellerKYCCAC, SellerKYCNIN
from celery import shared_task

@shared_task
def test_celery():
    print("It works!")


@shared_task
def verify_seller_kyc(kyc_id):
    try:
        kyc = SellerKYC.objects.get(user_id=kyc_id)
        print(kyc)

        # Force fresh queries to related models
        nin = SellerKYCNIN.objects.get(id=kyc.nin_id) if kyc.nin_id else None
        cac = SellerKYCCAC.objects.get(id=kyc.cac_id) if kyc.cac_id else None


        if kyc.nin and kyc.nin.status == KYCStatus.FAILED:
            kyc.status = KYCStatus.FAILED

        elif (kyc.cac and kyc.cac.cac_verified) or \
             (kyc.nin and kyc.nin.nin_verified):
            if not kyc.is_verified:
                kyc.is_verified = True
                kyc.status = KYCStatus.VERIFIED
        else:
            return
        
        kyc.verified_at = now()
        kyc.save(update_fields=["is_verified", "status", "verified_at"])
    
    except SellerKYC.DoesNotExist:
        pass

