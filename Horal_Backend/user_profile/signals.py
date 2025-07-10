from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.conf import settings
from .models import Profile
from users.models import CustomUser
from carts.models import Cart
from orders.models import Order
from favorites.models import Favorites
from django.db import transaction
from django.contrib.auth import get_user_model
import threading
import time

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_profile(sender, instance, created, **kwargs):

    if not created:
        return

    if instance.is_staff or instance.is_superuser:
        return

    Profile.objects.get_or_create(
        user=instance,
        defaults={
            "full_name": instance.full_name,
            "email": instance.email
        }
    )


@receiver(post_delete, sender=CustomUser)
def delete_user_related_data(sender, instance, **kwargs):
    """
    Deletes related data (profile, event roles, history) when a user is deleted.
    """
    # Delete profile if exists
    try:
        if hasattr(instance, 'user_profile'):
            instance.user_profile.delete()
    except Exception:
        pass

    # Delete Order history
    Order.objects.filter(user=instance).delete()

    # Delete Cart History
    Cart.objects.filter(user=instance).delete()

    # Delete favorite history
    Favorites.objects.filter(user=instance).delete()

    # Add deletion for other models if needed, e.g., tickets, checkin logs, etc.