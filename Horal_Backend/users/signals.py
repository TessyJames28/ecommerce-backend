from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from .models import CustomUser
from django.conf import settings
from notifications.tasks import send_email_task
from django.contrib.auth.signals import user_logged_in
from carts.utils import merge_user_cart
from products.utils import merge_recently_viewed_products
from favorites.utils import merge_favorites_from_session_to_user


@receiver(post_save, sender=CustomUser)
def welcome_new_user(sender, instance, created, **kwargs):
    """Signal to welcome new user after successful registration"""
    if not created:
        return

    recipient = instance.email
    subject = "Welcome to Horal"
    body = f"Hello {instance.full_name}\n\n" \
            f"Welcome to Horal!!!"
    from_email = f"Horal <{settings.DEFAULT_FROM_EMAIL}>"

    send_email_task.delay(recipient, subject, body, from_email)


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
    body = f"Hello {instance.full_name}\n\n" \
            f"Welcome to Horal Seller Team!\n" \
            f"Your new seller account is ready for you to start listing!\n\n" \
            f"Happy Selling"
    from_email = f"Horal <{settings.DEFAULT_FROM_EMAIL}>"

    send_email_task.delay(recipient, subject, body, from_email)


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
    print("signal for email change called")
    old_password = getattr(instance, "_old_password", None)
    if old_password and old_password != instance.password:
        print("Entered the condition")
        # Password changed
        subject = "Your account password was changed"
        message = "We noticed your password was changed. If this wasn't you, please reset your password immediately."
        from_email = f"Horal <{settings.DEFAULT_FROM_EMAIL}>"
        recipient = instance.email

        send_email_task.delay(recipient, subject, message, from_email)


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
        print(f"Cart merge failed: {e}")

    # merge recently viewed product
    try:
        merge_recently_viewed_products(session_key, user)
    except Exception as e:
        print(f"Recently viewed product merge failed: {e}")

    # merge favorites
    try:
        merge_favorites_from_session_to_user(session_key, user)
    except Exception as e:
        print(f"Favorites merge failed: {e}")

    
