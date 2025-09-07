from celery import shared_task
from django.utils import timezone
from django.core.cache import cache
from datetime import timedelta
from .models import TopSellingProduct
from .utils import (
    get_topselling_product_sql,
    attach_category_and_first_image,
    populate_time_series_sales,
    aggregate_sales_for_period,
    reconcile_raw_sales,
)
from products.models import ProductIndex
from django.db import connection
from shops.models import Shop
from products.utils import CATEGORY_MODEL_MAP
from dateutil.relativedelta import relativedelta
from .decorators import redis_lock
import logging


logger = logging.getLogger(__name__)


@shared_task
def compute_monthly_top_selling():
    """
    Task to compute sellers monthly top-selling products
    per shop for the current month
    """
    now = timezone.now()
    first_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    for shop in Shop.objects.all():
        raw_data = get_topselling_product_sql(shop.id, from_date=first_of_month)

        enriched_data = attach_category_and_first_image(raw_data)

        # Save to DB and cache
        for row in enriched_data:
            TopSellingProduct.objects.update(
                shop=shop.id,
                product=row["product_id"],
                month=first_of_month.date(),
                defaults={
                    "category_name": row["category_name"],
                    "title": row["title"],
                    "price": row["price"],
                    "total_quantity_sold": row["total_quantity_sold"],
                    "lastest_order_date": row["latest_order_date"],
                    "image_url": row["product_image"],
                }
            )

        # Cache in Redis for quick dashboard access
        cache.set(
            f"topselling:{shop.id}:{first_of_month.strftime('%Y-%m')}",
            enriched_data,
            timeout=60 * 60 * 24 * 90 # cache or 90 days
        )

@shared_task
def populate_daily_shop_sales():
    populate_time_series_sales("daily")

@shared_task
def populate_weekly_shop_sales():
    populate_time_series_sales("weekly")

@shared_task
def populate_monthly_shop_sales():
    populate_time_series_sales("monthly")

@shared_task
def populate_yearly_shop_sales():
    populate_time_series_sales("yearly")

@shared_task
def populate_all_time_series_sales():
    """
    Runs all periods in sequence.
    """
    for period in ['daily', 'weekly', 'monthly', 'yearly']:
        populate_time_series_sales(period)


@shared_task
def aggregate_daily_sales():
    aggregate_sales_for_period("daily")


@shared_task
def aggregate_weekly_sales():
    aggregate_sales_for_period("weekly")


@shared_task
def aggregate_monthly_sales():
    aggregate_sales_for_period("monthly")


@shared_task
def aggregate_yearly_sales():
    aggregate_sales_for_period("yearly")


@shared_task
def aggregate_all_sales():
    for period in ['daily', 'weekly', 'monthly', 'yearly']:
        aggregate_sales_for_period(period)


@shared_task
def invalidate_orders():
    reconcile_raw_sales()
