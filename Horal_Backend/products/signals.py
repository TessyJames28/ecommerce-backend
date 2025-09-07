from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType
from .models import ProductIndex
from .utils import CATEGORY_MODEL_MAP, image_model_map


MODEL_CATEGORY_MAP = {v: k for k, v in CATEGORY_MODEL_MAP.items()}

@receiver(post_save)
def create_or_update_product_index(sender, instance, created, **kwargs):
    """
    Automatically create product index once a product is created
    
    NOTE:
    For ProductIndex, content_type_id is intentionally set to the UUID of the product itself
    to simplify joins with ProductVariant and avoid Django ContentType joins.
    """
    if sender not in MODEL_CATEGORY_MAP:
        return


    defaults = {
        "shop": instance.shop,
        "category": MODEL_CATEGORY_MAP[sender],
        "sub_category": instance.sub_category.name,
        "title": instance.title,
        "slug": instance.slug,
        "price": instance.price,
        "description": instance.description,
        "specifications": instance.specifications,
        "state": instance.state,
        "local_govt": instance.local_govt,
        "condition": instance.condition,
        "is_published": instance.is_published,
        "brand": getattr(instance, "brand", "") or "",
    }

    ProductIndex.objects.update_or_create(
        id=instance.id,
        content_type=ContentType.objects.get_for_model(sender),
        object_id=instance.id,
        defaults=defaults,
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


IMAGE_MAP = {v: k for k, v in image_model_map.items()}

@receiver(post_save)
def update_product_index_image(sender, instance, **kwargs):
    """
    Update ProductIndex.image when an image is saved for any product type.
    """
    # Check if the sender is a known image model
    if sender not in image_model_map.values():
        return
    
    # Get the related product instance from the image
    product = getattr(instance, 'product', None)  # assuming FK on image is named 'product'
    if not product:
        return

    first_image = product.images.first()
    if first_image:
        ProductIndex.objects.update_or_create(
            content_type=ContentType.objects.get_for_model(product.__class__),
            object_id=product.id,
            defaults={"image": first_image.url}
        )

