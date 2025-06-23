from django.core.management.base import BaseCommand
from django.utils.timezone import now
from datetime import timedelta
from django.db import transaction
from collections import defaultdict

from orders.models import Order, Variant  # Make sure paths are correct

class Command(BaseCommand):
    help = "Cancel pending orders older than 30 minutes and update reserved quantities"

    def handle(self, *args, **kwargs):
        expired_time = now() - timedelta(minutes=30)
        expired_orders = Order.objects.filter(
            status='pending',
            created_at__lte=expired_time
        ).prefetch_related('order_items__variant')

        variants_to_update = {}
        orders_to_update = []

        with transaction.atomic():
            for order in expired_orders:
                for item in order.order_items.all():
                    variant = item.variant
                    if variant.id not in variants_to_update:
                        variants_to_update[variant.id] = variant
                    variant.reserved_quantity = max(variant.reserved_quantity - item.quantity, 0)

                order.status = Order.Status.CANCELLED
                orders_to_update.append(order)

            if variants_to_update:
                Variant.objects.bulk_update(variants_to_update.values(), ['reserved_quantity'])
            if orders_to_update:
                Order.objects.bulk_update(orders_to_update, ['status'])

        self.stdout.write(self.style.SUCCESS(f"{len(orders_to_update)} expired orders processed."))
