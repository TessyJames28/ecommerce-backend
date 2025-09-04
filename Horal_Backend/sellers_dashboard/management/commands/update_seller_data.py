from django.core.management.base import BaseCommand
from django.db.models import Sum, F, Count, Max, Q
from django.db.models.functions import TruncDay, TruncWeek, TruncMonth, TruncYear
from django.utils.timezone import now
from datetime import datetime
from collections import defaultdict
from products.utils import CATEGORY_MODEL_MAP
from django.db.models import ExpressionWrapper, FloatField
from orders.models import OrderItem
from products.models import ProductVariant
from sellers_dashboard.models import (
    RawSale, TopSellingProduct, DailySales,
    MonthlySales, WeeklySales, YearlySales,
    DailyShopSales, WeeklyShopSales,
    MonthlyShopSales, YearlyShopSales
)
from products.models import ProductIndex
from shops.models import Shop
from sellers_dashboard.helper import get_day_start, get_month_start, get_week_start, get_year_start

# RawSale.objects.all().delete()
TopSellingProduct.objects.all().delete()
periods = ['daily', 'weekly', 'monthly', 'yearly']

class Command(BaseCommand):
    help = "Populate RawSale and TopSellingProduct from existing order data."

    def handle(self, *args, **kwargs):
        self.update_raw_sales()
        self.update_top_selling()
        for period in periods:
            self.aggregate_sales_for_period(period)
            self.populate_time_series_sales(period)
        self.stdout.write(self.style.SUCCESS("✅ RawSale and TopSellingProduct tables updated successfully."))


    def update_raw_sales(self):
        print("🔄 Updating RawSales...")

        order_items = OrderItem.objects.all()
        for item in order_items:
            order = item.order
            if order.status not in ["paid", "shipped", "at_pick_up", "delivered"]:
                pass
        
            # Avoid duplicating entries if already populated
            if RawSale.objects.filter(order_item=item, variant=item.variant).exists():
                return
            
            variant = item.variant
            product_index = ProductIndex.objects.get(id=variant.object_id)
            product = product_index.get_real_product()

            if item.order.status in ["paid", "shipped", "delivered"]:
                RawSale.objects.create(
                    shop=variant.shop,
                    order_item=item,
                    category=product.category,
                    product=product_index,
                    variant=variant,
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                    total_price=item.quantity * float(item.unit_price),
                    created_at=order.created_at
                )
                # print(f"created_at: {RawSale.created_at}")
        print("✅ RawSales updated.")


    def update_top_selling(self):
        print("🔄 Updating TopSellingProduct ...")

        # Group sales by product within the current month
        current_month = datetime.today().replace(day=1)

        # Fetch all variants involved in orders this month
        sales_data = (
            OrderItem.objects
            .filter(order__created_at__lte=current_month)
            .values('variant')
            .annotate(
                total_quantity=Sum('quantity'),
                latest_order_date=Max('order__created_at')
            )
        )

        # Group data by product (object_id), via variant
        product_sales = {}

        for row in sales_data:
            try:
                variant = ProductVariant.objects.select_related('shop').get(id=row['variant'])
                shop = variant.shop
                product_id = variant.object_id
            except ProductVariant.DoesNotExist:
                continue

            key = (shop.id, product_id)

            if key not in product_sales:
                product_sales[key] = {
                    'shop': shop,
                    'product_id': product_id,
                    'total_quantity': 0,
                    'latest_order_date': row['latest_order_date'],
                }

            product_sales[key]['total_quantity'] += row['total_quantity']
            
            if row['latest_order_date'] > product_sales[key]['latest_order_date']:
                product_sales[key]['latest_order_date'] = row['latest_order_date']

        # print(f"Product sales: {product_sales}")
        # save to DB (Top 20 only)
        sorted_sales = sorted(product_sales.values(), key=lambda x: x['total_quantity'], reverse=True)[:20]
        # print(f"Sorted sales: {sorted_sales}")

        for record in sorted_sales:
            shop = record['shop']
            product_id = record['product_id']
            total_quantity = record['total_quantity']
            latest_order_date = record['latest_order_date']

            try:
                product_index = ProductIndex.objects.get(id=product_id)
                product = product_index.get_real_product()
            except ProductIndex.DoesNotExist:
                continue

            category = getattr(product, "category", None)
            category_name = category.name if category else ""

            TopSellingProduct.objects.update_or_create(
                shop=shop,
                product=product.id,
                month=current_month,
                defaults={
                    'category_name': category_name,
                    'title': getattr(product, 'title', ''),
                    'price': getattr(product, 'price', 0),
                    'total_quantity_sold': total_quantity,
                    'latest_order_date': latest_order_date,
                    'image_url': getattr(product, 'get_main_image_url', lambda: '')(),
                }
            )

    print("✅ TopSellingProduct updated.")

    def aggregate_sales_for_period(self, period: str):
        """
        Function to aggaregate and compute the period sales table
        period: 'daily', 'weekly', 'monthly', 'yearly'
        """
        print("Aggregating Sales Table")

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
        if period != "yearly":
            sales = RawSale.objects.filter(
                is_valid=True
            ).filter(
                Q(**{f"processed_flags__{flag_key}__isnull": True}) | ~Q(**{f"processed_flags__{flag_key}": True})
            )
        else:
            sales = RawSale.objects.filter(is_valid=True)

        aggregates = {}

        for sale in sales:
            period_start = period_start_fn(sale.created_at.date())
            key = (sale.shop, sale.category, period_start)
            print(f"Sales data for aggregate: {sale.created_at}")

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

    print(f"Aggregated shop sales")  


    def populate_time_series_sales(self, period: str):
        """
        Function to populate the corresponding shop sales
        for the given period.
        period: 'daily', 'weekly', 'monthly', 'yearly'
        """
        print("Populating time series table")

        period_fn_map = {
            'daily': (DailyShopSales, get_day_start),
            'weekly': (WeeklyShopSales, get_week_start),
            'monthly': (MonthlyShopSales, get_month_start),
            'yearly': (YearlyShopSales, get_year_start),
        }
        print("First print statement")
        if period not in period_fn_map:
            raise ValueError(f"Invalid period: {period}")
        
        ModelClass, start_fn = period_fn_map[period]

        flag_key = ModelClass.__name__
        print("Second print statement")
        if period != "yearly":
            sales = RawSale.objects.filter(
                is_valid=True
            ).filter(
                Q(**{f"processed_flags__{flag_key}__isnull": True}) | ~Q(**{f"processed_flags__{flag_key}": True})
            )
        else:
            sales = RawSale.objects.filter(is_valid=True)
            
        print(f"Sales data for populate: {sales}")

        aggregates = {}

        for sale in sales:
            period_start = start_fn(sale.created_at.date())
            key = (sale.shop, period_start)
            print(f"Sales data for populate: {sale.created_at}")

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

    print("Populated time series chart feature")

