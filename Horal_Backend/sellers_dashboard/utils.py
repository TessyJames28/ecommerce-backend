from orders.models import OrderItem
from django.db.models import Sum, F, ExpressionWrapper, DecimalField, Q
from products.models import ProductIndex
from django.db import connection
from django.utils.timezone import now
from datetime import timedelta
from django.conf import settings
from orders.models import Order, OrderItem
from .models import (
    TopSellingProduct, RawSale,
    DailySales, WeeklySales,
    MonthlySales, YearlySales,
    DailyShopSales, WeeklyShopSales,
    MonthlyShopSales, YearlyShopSales,
)
from notifications.utils import safe_cache_get, safe_cache_set
from products.utils import CATEGORY_MODEL_MAP
from django.core.cache import cache
from .helper import (
    get_day_start, get_month_start,
    get_week_start, get_year_start
)
from shops.models import Shop
from users.models import CustomUser
import logging

logger = logging.getLogger(__name__)


def get_total_revenue(shop):
    """
    Function to retrieve each seller total revenue
    On Horal
    """

    qs = OrderItem.objects.filter(
        variant__shop=shop,
        order__status=Order.Status.PAID,
        is_returned=False
    ).annotate(
        line_total=ExpressionWrapper(
            F("quantity") * F("unit_price"), output_field=DecimalField()
        )
    )

    return qs.aggregate(total=Sum("line_total"))["total"] or 0


def get_withdrawable_revenue(shop_id):
    """
    Function to retrieve each seller total revenue on Horal
    This is calculated by total completed order revenue
    minus total successful withdrawal
    """
    from wallet.models import Payout

    try:
        shop = Shop.objects.get(id=shop_id)
        user = shop.owner.user
        if not user.is_seller:
            raise Exception("User is not a seller")
    except (Shop.DoesNotExist, AttributeError) as e:
        logger.warning(f"Error occurred: {e}")
        raise Exception(f"seller does not exists")

    cr = OrderItem.objects.filter(
        variant__shop=shop_id,
        is_completed=True
    ).annotate(
        line_total=ExpressionWrapper(
            F("quantity") * F("unit_price"), output_field=DecimalField()
        )
    )

    completed_revenue = cr.aggregate(total=Sum("line_total"))["total"] or 0

    wr = Payout.objects.filter(
        seller=user,
        status__in=[
            Payout.StatusChoices.SUCCESS,
            Payout.StatusChoices.PROCESSING
        ]
    ).aggregate(withdrawn_amount=Sum("total_withdrawable")) # correct code for prod

    withdrawn_amount = wr.get("withdrawn_amount") or 0

    return completed_revenue - withdrawn_amount



def get_total_order(shop):
    """
    Function that compute the total order of a specific seller
    Per the provided seller shop
    """

    total = OrderItem.objects.filter(
        variant__shop=shop,
        order__status=Order.Status.PAID,
        is_returned=False,
        # is_return_requested=False
    ).aggregate(total=Sum("quantity"))

    for val in total.values():
        return val



def get_return_order(shop):
    """
    Function that compute the total returned order of a specific seller
    Per the provided seller shop
    """

    return OrderItem.objects.filter(
        variant__shop=shop,
        is_returned=True,
        is_return_requested=True
    ).aggregate(total=Sum("quantity"))["total"] or 0


def get_order_in_dispute(shop):
    """
    Function that compute the total returned order of a specific seller
    Per the provided seller shop
    """

    return OrderItem.objects.filter(
        variant__shop=shop,
        is_returned=False,
        is_return_requested=True
    ).aggregate(total=Sum("quantity"))["total"] or 0



def aggregate_sales_for_period(period: str):
    """
    Function to aggaregate and compute the period sales table
    period: 'daily', 'weekly', 'monthly', 'yearly'
    """

    period_fn_map = {
        'daily': get_day_start,
        'weekly': get_week_start,
        'monthly': get_month_start,
        'yearly': get_year_start,
    }

    model_map = {
        'daily': DailySales,
        'weekly': WeeklySales,
        'monthly': MonthlySales,
        'yearly': YearlySales,
    }

    if period not in period_fn_map:
        raise ValueError(f"Invalid period: {period}")

    period_start_fn = period_fn_map[period]
    Model = model_map[period]
    flag_key = Model.__name__

    # Choose appropriate period function
    cutoff_time = now() - timedelta(minutes=5)

    sales = RawSale.objects.filter(
        is_valid=True, created_at__lt=cutoff_time
    ).filter(
        Q(**{f"processed_flags__{flag_key}__isnull": True}) | ~Q(**{f"processed_flags__{flag_key}": False})
    )

    aggregates = {}

    for sale in sales:
        period_start = period_start_fn(sale.created_at.date())
        key = (sale.shop, sale.category, period_start)

        if key not in aggregates:
            aggregates[key] = {
                'shop': sale.shop,
                'category': sale.category,
                'period_start': period_start,
                'total_quantity': 0,
                'total_sales': 0,
                'total_units': 0,
                'sales': [] # track sales processed for this group
            }

        aggr = aggregates[key]
        aggr['total_quantity'] += sale.quantity # count total item sold
        aggr['total_sales'] += float(sale.total_price)
        aggr['total_units'] += sale.quantity
        aggr['sales'].append(sale)

    for data in aggregates.values():
        Model.objects.update_or_create(
            shop=data['shop'],
            category=data['category'],
            period_start=data['period_start'],
            defaults={
                'total_quantity': data['total_quantity'],
                'total_sales': data['total_sales'],
                'total_units': data['total_units'],
            }
        )

        # Mark associated raw sales as processed for this period
        for sale in data['sales']:
            sale.processed_flags[flag_key] = True
            sale.save(update_fields=['processed_flags'])



def get_sales_by_category(shop):
    """
    Retrieves sales by category for the current day, week, month, and year.
    """

    today = now().date()
    start_of_week = today - timedelta(days=today.weekday())  # Monday
    start_of_month = today.replace(day=1)
    start_of_year = today.replace(month=1, day=1)

    period_model_map = {
        'daily': (DailySales, 'period_start', today),
        'weekly': (WeeklySales, 'period_start', start_of_week),
        'monthly': (MonthlySales, 'period_start', start_of_month),
        'yearly': (YearlySales, 'period_start', start_of_year),
    }

    results = {}

    for period, (Model, start_field, period_start_value) in period_model_map.items():
        summary_qs = (
            Model.objects.filter(shop=shop)
            .filter(**{start_field: period_start_value})  # Filter to current period only
            .values('category__name', start_field)
            .annotate(
                total_sales=Sum('total_sales'),
                total_quantity=Sum('total_quantity')
            ).order_by('-total_sales')
        )

        results[period] = [
            {
                "category": row['category__name'],
                "period_start": row['period_start'],
                "total_sales": float(row['total_sales']),
                "total_quantity": row['total_quantity']
            }
            for row in summary_qs
        ]

    return results



def populate_time_series_sales(period: str):
    """
    Function to populate the corresponding shop sales
    for the given period.
    period: 'daily', 'weekly', 'monthly', 'yearly'
    """

    period_fn_map = {
        'daily': (DailyShopSales, get_day_start),
        'weekly': (WeeklyShopSales, get_week_start),
        'monthly': (MonthlyShopSales, get_month_start),
        'yearly': (YearlyShopSales, get_year_start),
    }

    if period not in period_fn_map:
        raise ValueError(f"Invalid period: {period}")
    
    ModelClass, start_fn = period_fn_map[period]

    flag_key = ModelClass.__name__

    cutoff_time = now() - timedelta(minutes=5)
    sales = RawSale.objects.filter(
        is_valid=True, created_at__lt=cutoff_time
    ).filter(
        Q(**{f"processed_flags__{flag_key}__isnull": True}) | ~Q(**{f"processed_flags__{flag_key}": False})
    )

    aggregates = {}

    for sale in sales:
        period_start = start_fn(sale.created_at.date())
        key = (sale.shop, period_start)

        if key not in aggregates:
            aggregates[key] = {
                "total_sales": 0,
                "order_item_count": 0,
                "sales": []
            }
        
        aggr = aggregates[key]
        aggr['total_sales'] += float(sale.total_price)
        aggr['order_item_count'] += sale.quantity
        aggr["sales"].append(sale)

    for (shop, period_start), data in aggregates.items():
        ModelClass.objects.update_or_create(
            shop=shop,
            period_start=period_start,
            defaults={
                'total_sales': data['total_sales'],
                'order_count': data['order_item_count']
            }
        )

        # Mark associated raw sales as processed for this period
        for sale in data['sales']:
            sale.processed_flags[flag_key] = True
            sale.save(update_fields=['processed_flags'])



def get_sales_and_order_overview(shop):
    """
    Function that returns grouped sales and order overview
    from precomputed time-series tables
    Suitable for charting daily, weekly, monthly, yearly trends
    """
    def format_queryset(qs):
        return list(
            qs.order_by("period_start")
            .values("period_start", "total_sales", "order_count")
        )
    
    sales_order = {}
    models = {
        'daily': DailyShopSales,
        'weekly': WeeklyShopSales,
        'monthly': MonthlyShopSales,
        'yearly': YearlyShopSales,
    }

    for period, model in models.items():
        data = format_queryset(model.objects.filter(shop=shop))
        sales_order[period] = sorted(data, key=lambda x: x["period_start"], reverse=True)

    return sales_order


def get_topselling_product_sql(shop, from_date):
    """Raw sql to get top selling product per seller"""
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT
                pi.id AS product_index_id,
                SUM(oi.quantity) AS total_quantity_sold,
                MAX(o.created_at) AS latest_order_date
            FROM
                orders_orderitem oi
            JOIN
                "orders_order" o ON oi.order_id = o.id
            JOIN
                products_productvariant pv ON oi.variant_id = pv.id
            JOIN
                products_productindex pi ON pi.id = pv.object_id
                       
            WHERE
                pv.shop_id = %s
                AND o.status IN ('paid', 'shipped', 'at_pick_up', 'delivered')
                AND oi.is_returned = false
                AND oi.is_return_requested = false
                AND o.created_at >= %s
            GROUP BY
                pi.id
            ORDER BY
                total_quantity_sold DESC
            LIMIT 20;

        """, [str(shop), from_date])
        
        # Get column names for dictionary output
        rows = cursor.fetchall()  # ✅ fetch once
        columns = [col[0] for col in cursor.description]
        raw_data = [dict(zip(columns, row)) for row in rows]

    # Attach real product info
    enriched = []
    for row in raw_data:
        try:
            product_index = ProductIndex.objects.get(id=row['product_index_id'])
            product_id = product_index.object_id

            model_class = CATEGORY_MODEL_MAP.get(product_index.category_name)
            if model_class:
                product = model_class.objects.get(id=product_id)
                row['title'] = getattr(product, 'title', None)
                row['price'] = getattr(product, 'price', None)
                row['product_id'] = product.id
                enriched.append(row)
        except ProductIndex.DoesNotExist as e:
            logger.warning(f"Error occurred when reading topselling prod sql: {e}")
            continue

    return enriched

    

def attach_category_and_first_image(products_data):
    """Use normal python to retrieve image for each product"""
    results = []
    seen = {}

    for row in products_data:
        product_id = row['product_id']

        if product_id in seen:
            row["product_image"] = seen[product_id]["image_url"]
            row["category_name"] = seen[product_id]["category_name"]
            results.append(row)
            continue

        # Fetch the category from ProductIndex
        try:
            product_index = ProductIndex.objects.only("category_name").get(id=product_id)
        except ProductIndex.DoesNotExist as e:
            logger.warning(f"Error occurred when attaching cat and first img: {e}")
            continue

        category_name = product_index.category.lower()
        
        # Get image from appropriate model using mapping
        model_class = CATEGORY_MODEL_MAP.get(category_name)
        
        image_url = None
        if model_class:
            product = model_class.objects.filter(
                id=product_id).prefetch_related("images").first()
            if product and product.images.exists():
                image_url = product.images.first().url

        row["product_image"] = image_url
        row["category_name"] = category_name

        seen[product_id] = {
            "image_url": image_url,
            "category_name": category_name
        }

        results.append(row)

    return results


def get_sellers_topselling_products(shop):
    """Retrieve sellers top selling products"""
    now = now()
    key = "topselling:{shop.id}:{first_of_month.strftime('%Y-%m')}"
    data = cache.get(key)

    if not data:
        # fallback to DB
        month = now.replace(day=1).date()
        products = TopSellingProduct.objects.filter(shop_id=shop, month=month)
        data = [
            {
                "product_id": p.product_id,
                "title": p.title,
                "price": float(p.price),
                "image_url": p.image_url,
                "total_quantity_sold": p.total_quantity_sold,
                "latest_order_date": p.latest_order_date,
                "category_name": p.category_name,
            }
            for p in products
        ]

    # raw_data = get_topselling_product_sql(shop)
    # enriched_data = attach_category_and_first_image(raw_data)

    return data


def get_clean_shop_id(shop):
    """
    Return shop.id in appropriate format depending on the DB backend.
    For SQLite (used in testing), return it without dashes.
    For production (Postgres), return it normally.
    """
    if settings.DATABASES['default']['ENGINE'] == 'django.db.backends.sqlite3':
        return str(shop).replace('-', '')
    return str(shop)


def get_rolling_topselling_products(shop):
    """
    Get seller's top-selling products for the past 30 days (rolling window).
    This is computed on-the-fly without caching or DB persistence
    """
    from_date = now() - timedelta(days=30)
    shop_id = get_clean_shop_id(shop)
    raw_data = get_topselling_product_sql(shop_id, from_date)
    enriched_data = attach_category_and_first_image(raw_data)


    return enriched_data


from datetime import datetime

def parse_date_safe(date_str):
    if date_str is None:
        return datetime.min  # or datetime.max depending on your intent
    if isinstance(date_str, datetime):
        return date_str
    try:
        return datetime.fromisoformat(date_str)
    except Exception:
        return datetime.min


def reconcile_raw_sales():
    """Function to reconcile rawsale"""
    RawSale.objects.filter(
        order_item__is_returned=True,
        is_valid=True
    ).update(is_valid=False, invalidated_at=now(), processed_flags={})

