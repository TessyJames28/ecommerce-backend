from django.db.models.signals import post_save, post_delete
from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType
from .models import ProductIndex
from .utils import CATEGORY_MODEL_MAP
from carts.utils import merge_user_cart
from products.utils import merge_recently_viewed_products
from favorites.utils import merge_favorites_from_session_to_user


MODEL_CATEGORY_MAP = {v: k for k, v in CATEGORY_MODEL_MAP.items()}

# Automatically index new product
@receiver(post_save)
def create_product_index(sender, instance, created, **kwargs):
    """
    Automatically create product index once a product is created
    
    NOTE:
    For ProductIndex, content_type_id is intentionally set to the UUID of the product itself
    to simplify joins with ProductVariant and avoid Django ContentType joins.
    """
    if not created:
        return
    
    # Ensure only models in MODEL_CATEGORY_MAP are indexed
    if sender not in MODEL_CATEGORY_MAP:
        return
    
    category_name = MODEL_CATEGORY_MAP[sender]
    
    ProductIndex.objects.get_or_create(
        id=instance.id,
        content_type=ContentType.objects.get_for_model(sender),
        object_id=instance.id,
        defaults={
            "category_name": category_name,
            "shop": instance.shop
        }
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
