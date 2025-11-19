from celery import shared_task
from .utils import regenerate_product_cache_lists
from .image_scan import scan_all_product_images


@shared_task
def regenerate_product_cache_lists_task():
    """Background task to regenerate all product cache lists."""
    regenerate_product_cache_lists()


@shared_task
def task_scan_and_clean_images():
    """Background task to scan product images and clean broken ones."""
    scan_all_product_images()
