from celery import shared_task
from .utils import regenerate_product_cache_lists

@shared_task
def regenerate_product_cache_lists_task():
    """Background task to regenerate all product cache lists."""
    regenerate_product_cache_lists()
