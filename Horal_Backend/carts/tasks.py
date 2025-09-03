from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from .models import Cart
from .signals import cart_abandoned

@shared_task
def check_abandoned_carts():
    cutoff = timezone.now() - timedelta(minutes=5)  # 24 hours of inactivity
    abandoned_carts = Cart.objects.filter(updated_at__lt=cutoff)

    for cart in abandoned_carts:
        cart_abandoned.send(sender=Cart, cart=cart)
    
    