from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType
from .models import ProductIndex
from .utility import CATEGORY_MODEL_MAP


MODEL_CATEGORY_MAP = {v: k for k, v in CATEGORY_MODEL_MAP.items()}

# Automatically index new product
@receiver(post_save)
def create_product_index(sender, instance, created, **kwargs):
    """Automatically create product index once a product is created"""
    if not created:
        return
    
    category_name = MODEL_CATEGORY_MAP.get(sender)
    if not category_name:
        return
    
    ProductIndex.objects.get_or_create(
        id=instance.id,
        content_type=ContentType.objects.get_for_model(sender),
        object_id=instance.id,
        defaults={"category_name": category_name}
    )


@receiver(post_delete)
def delete_product_index(sender, instance, **kwargs):
    """Automatically delete product index when product is deleted"""
    if sender not in MODEL_CATEGORY_MAP:
        return

    ProductIndex.objects.filter(
        content_type=ContentType.objects.get_for_model(sender),
        object_id=instance.id
    ).delete()
