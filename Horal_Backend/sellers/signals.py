from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from users.models import CustomUser
from .models import SellerKYC, SellerKYCCAC, SellerKYCNIN, SellerKYCAddress, SellerSocials
from .tasks import verify_seller_kyc  # Celery task
from django.core.cache import cache
from notifications.emails import (
    send_kyc_final_status_email,
    send_kyc_info_completed_email,
)


@receiver(post_save, sender=SellerKYCNIN)
@receiver(post_save, sender=SellerKYCCAC)
def trigger_related_kyc_verification(sender, instance, update_fields=None, **kwargs):
    fields_of_interest = {'status', 'cac_verified', 'nin_verified'}
    
    # Only act if relevant fields changed
    if update_fields is not None and not fields_of_interest.intersection(update_fields):
        return

    try:
        if sender == SellerKYCNIN:
            kyc = SellerKYC.objects.get(nin=instance)
        elif sender == SellerKYCCAC:
            kyc = SellerKYC.objects.get(cac=instance)
        else:
            return

        cache_key = f"verify-kyc-{kyc.user.id}"
        if cache.get(cache_key):
            return  # Debounce active; skip triggering task
        cache.set(cache_key, True, timeout=10)  # Debounce for 10 seconds
        verify_seller_kyc(kyc.user.id)

    except SellerKYC.DoesNotExist:
        pass


@receiver(post_save, sender=SellerKYC)
def notify_kyc_info_completed(sender, instance, created, **kwargs):
    """Signal to send notification on kyc completion"""
    kyc = instance
    if (
        kyc.address
        and kyc.socials
        and kyc.nin
        and (not kyc.cac or kyc.cac)
    ):
    # Safe to send confirmation email
        if not kyc.info_completed_notified:
            send_kyc_info_completed_email(kyc.user)
            SellerKYC.objects.filter(pk=kyc.pk).update(info_completed_notified=True)


@receiver(post_save, sender=SellerKYC)
def notify_kyc_status_change(sender, instance, **kwargs):
    if instance.status in ['verified', 'failed'] and not instance.status_notified:
        send_kyc_final_status_email(instance.user, instance.status)
        SellerKYC.objects.filter(pk=instance.pk).update(status_notified=True)

    


@receiver(post_delete, sender=SellerKYC)
def delete_kyc_related(sender, instance, **kwargs):
    # Safely delete related records
    if instance.socials:
        instance.socials.delete()
    if instance.address:
        instance.address.delete()
    if instance.cac:
        instance.cac.delete()
    if instance.nin:
        instance.nin.delete()

    # Reset is_seller flag on the user
    user_id = instance.user_id
    if user_id:
        try:
            user = CustomUser.objects.get(id=user_id)
            user.is_seller = False
            user.save(update_fields=["is_seller"])
        except CustomUser.DoesNotExist:
            pass
