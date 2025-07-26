from .models import ProductRatingSummary
from django.dispatch import receiver
from django.db.models.signals import post_save
from django.db.models import Count, Avg
from ratings.models import UserRating


@receiver(post_save, sender=UserRating)
def update_rating_summary(sender, instance, **kwargs):
    product = instance.product
    seller = product.shop.owner.user

    agg = UserRating.objects.filter(product=product).aggregate(
        avg=Avg('rating'),
        total=Count('id')
    )

    summary, created = ProductRatingSummary.objects.get_or_create(product=product, defaults={"seller": seller})
    summary.average_rating = agg['avg'] or 0.0
    summary.total_ratings = agg['total']
    summary.seller = seller  # ensure update even if reassigned
    summary.save()
