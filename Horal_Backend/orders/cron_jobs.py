# In a periodic task
from django.utils.timezone import now
from datetime import timedelta
from .models import Order

expired_time = now() - timedelta(minutes=30)
expired_orders = Order.objects.filter(status='pending', created_at__lte=expired_time)


for order in expired_orders:
    for item in order.order_items.all():
        variant = item.variant
        variant.reserved_quantity -= item.quantity
        variant.save()

    order.status = Order.Status.CANCELLED
    order.save()