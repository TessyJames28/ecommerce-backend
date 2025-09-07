from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from .models import CustomUser
from django.conf import settings
from notifications.tasks import send_email_task
from django.contrib.auth.signals import user_logged_in
from carts.utils import merge_user_cart
from products.utils import merge_recently_viewed_products
from favorites.utils import merge_favorites_from_session_to_user
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=CustomUser)
def welcome_new_user(sender, instance, created, **kwargs):
    if not created or instance.is_temporary:
        return

    send_email_task.delay(
        recipient=instance.email,
        subject="Welcome to Horal",
        from_email=f"Horal <{settings.DEFAULT_FROM_EMAIL}>",
        template_name="notifications/emails/welcome_email_generic.html",
        context={
            "user": instance.full_name,
            "title": "Welcome to Horal Nigeria!",
            "body_paragraphs": [
                "We're thrilled to have you join our community. Horal is the secure and easy way to buy and sell products, with every transaction protected by our escrow system.",
                "Whether you're here to find amazing deals or to start your own business, we've got you covered.",
                "Your journey to buying and selling made easy starts now. Explore amazing deals, secure payments, and a seamless shopping experience."
            ],
            "cta_text": "Start Shopping Now",
            "cta_url": "https://www.horal.ng/",
            "secondary_text_before_link": "Interested in selling?",
            "secondary_link_text": "Become a seller",
            "secondary_link_url": "https://www.horal.ng/kyc-verification"
        }
    )



@receiver(pre_save, sender=CustomUser)
def cache_old_is_seller(sender, instance, **kwargs):
    if instance.pk:
        try:
            instance._old_is_seller = sender.objects.get(pk=instance.pk).is_seller
        except sender.DoesNotExist:
            instance._old_is_seller = None
    else:
        instance._old_is_seller = None


@receiver(post_save, sender=CustomUser)
def welcome_new_sellers(sender, instance, created, **kwargs):
    """Signal to monitor and welcome newly registered sellers"""
    if created or not instance.is_seller:
        return
    
    # Check if is_seller just changed
    old_value = getattr(instance, "_old_is_seller", None)

    if old_value is True:  # Already a seller, skip
        return
    
    recipient = instance.email
    subject = "Welcome to Horal Seller Team"

    send_email_task.delay(
        recipient=recipient,
        subject=subject,
        from_email=f"Horal <{settings.DEFAULT_FROM_EMAIL}>",
        template_name="notifications/emails/welcome_email_generic.html",
        context={
            "user": instance.full_name,
            "title": "Welcome to Horal Sellers Community!",
            "body_paragraphs": [
                "Welcome aboard! You’re now part of the Horal marketplace.",
                "We're thrilled to have you join our community of sellers. Horal is the secure and easy way to sell products, with every transaction protected by our escrow system.",
                "Your new seller account is ready for you to start listing! Start uploading your products today and reach thousands of buyers"
            ],
            "cta_text": "Start Listing Now",
            "cta_url": "https://www.horal.ng/"
        }
    )



@receiver(pre_save, sender=CustomUser)
def track_old_password(sender, instance, **kwargs):
    if not instance.pk:  # New user, skip
        return
    try:
        old = sender.objects.get(pk=instance.pk)
        instance._old_password = old.password
    except sender.DoesNotExist:
        instance._old_password = None

@receiver(post_save, sender=CustomUser)
def password_change_alert(sender, instance, **kwargs):
    old_password = getattr(instance, "_old_password", None)
    if old_password and old_password != instance.password:

        subject = "Password Reset"
        user = instance.full_name
        body_paragraphs = [
            "Password reset successful! You can now log in to your Horal account with your new password.",
            "If this wasn't you, please reset your password immediately."
        ]
        cta = {
            "text": "Reset Password",
            "url": "https://www.horal.ng/forgot-password/"
        }

        send_email_task.delay(
            recipient=instance.email,
            subject=subject,
            from_email=f"Horal <{settings.DEFAULT_FROM_EMAIL}>",
            template_name="notifications/emails/general_email.html",
            context={
                "user": user,
                "title": subject,
                "body_paragraphs": body_paragraphs,
                "cta": cta
            }
        )


@receiver(user_logged_in)
def merge_user_data(sender, request, user, **kwargs):
    session_key = request.session.session_key
    if not session_key:
        request.session.save()
        session_key = request.session.session_key

    # merge cart
    try:
        merge_user_cart(session_key, user)
    except Exception as e:
        logger.error(f"Cart merge failed for user {user.id}: {e}")

    # merge recently viewed product
    try:
        merge_recently_viewed_products(session_key, user)
    except Exception as e:
        logger.error(f"Recently viewed products merge failed for user {user.id}: {e}")

    # merge favorites
    try:
        merge_favorites_from_session_to_user(session_key, user)
    except Exception as e:
        logger.error(f"Favorites merge failed for user {user.id}: {e}")
