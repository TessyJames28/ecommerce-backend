from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from .models import Cart
from .signals import cart_abandoned


@shared_task
def check_abandoned_carts():
    """
    Sends reminders for abandoned carts at 1h, 12h, and 48h.
    """
    now = timezone.now()

    reminder_windows = {
        "2h": (now - timedelta(hours=4), now - timedelta(hours=2)),
        "24h": (now - timedelta(hours=26), now - timedelta(hours=24)),
        "48h": (now - timedelta(hours=50), now - timedelta(hours=48)),
    }

    for label, (start, end) in reminder_windows.items():
        carts = Cart.objects.filter(
            updated_at__gte=start,
            updated_at__lt=end
        ).exclude(**{f"reminder_{label}_sent": True})

        for cart in carts:
            cart_abandoned.send(sender=Cart, cart=cart, reminder=label)
            setattr(cart, f"reminder_{label}_sent", True)
            cart.save(update_fields=[f"reminder_{label}_sent"])

    
    