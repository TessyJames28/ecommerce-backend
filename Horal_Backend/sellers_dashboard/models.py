from django.db import models
from products.models import ProductIndex
from users.models import CustomUser
import uuid

# Create your models here.
class ProductRatingSummary(models.Model):
    """Model to aggregate rating across sellers listed products"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.OneToOneField(ProductIndex, on_delete=models.CASCADE, related_name="rating_summary")
    seller = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="product_rating_summaries")
    shop = models.ForeignKey("shops.Shop", on_delete=models.CASCADE, related_name="product_rating_summaries", null=True, blank=True)
    average_rating = models.FloatField(default=0.0)
    total_ratings = models.PositiveIntegerField(default=0)
    last_updated = models.DateTimeField(auto_now=True)


    class Meta:
        indexes = [
            models.Index(fields=["shop"]),
        ]


    def save(self, *args, **kwargs):
        if not self.shop and self.product:
            self.shop = self.product.shop
        super().save(*args, **kwargs)


    def __str__(self):
        return f"{self.product.title} → {self.average_rating} ({self.total_ratings})"


class RawSale(models.Model):
    """
    Table to collect raw sales data from
    order item table
    """
    id = models.UUIDField(primary_key=True, editable=False, default=uuid.uuid4)
    shop = models.ForeignKey('shops.Shop', on_delete=models.CASCADE)
    category = models.ForeignKey('categories.Category', on_delete=models.SET_NULL, null=True)
    product = models.ForeignKey('products.ProductIndex', on_delete=models.SET_NULL, null=True)
    variant = models.ForeignKey('products.ProductVariant', on_delete=models.SET_NULL, null=True)
    
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    total_price = models.DecimalField(max_digits=12, decimal_places=2)
    
    # For tracking order validity - when an order is cancelled or returned
    is_valid = models.BooleanField(default=True)
    invalidated_at = models.DateTimeField(null=True, blank=True)

    order = models.ForeignKey('orders.Order', on_delete=models.CASCADE)
    created_at = models.DateTimeField()
    
    processed_flags = models.JSONField(default=dict, blank=True)


class SalesAdjustment(models.Model):
    id = models.UUIDField(primary_key=True, editable=False, default=uuid.uuid4)
    raw_sales = models.ForeignKey(RawSale, on_delete=models.CASCADE, related_name="raw_sales")
    adjusted_at = models.DateTimeField(auto_now_add=True)



class BaseAggregateSales(models.Model):
    """
    Model to aggregate and cache sales data by category
    Allow for easier and fast querying over time as data grew
    """
    period_start = models.DateField() # date of the day
    total_quantity = models.PositiveBigIntegerField(default=0)
    total_sales = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_units = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)


    class Meta:
        abstract = True

    def __strt__(self):
        period = self.__class__.__name__.replace("Sales", "").lower()
        return f"{self.shop.name} - {self.category.name} - {period} - {self.period_start}"


class DailySales(BaseAggregateSales):
    """Calculate daily sales"""
    shop = models.ForeignKey(
        'shops.Shop', on_delete=models.CASCADE,
        related_name="daily_sales")
    category = models.ForeignKey(
        'categories.Category', on_delete=models.CASCADE,
        related_name="daily_sales_category")

    class Meta:
        unique_together = ('shop', 'category', 'period_start')
        indexes = [
            models.Index(fields=['shop', 'category', 'period_start']),
        ]


class WeeklySales(BaseAggregateSales):
    """Calculate daily sales"""
    shop = models.ForeignKey(
        'shops.Shop', on_delete=models.CASCADE,
        related_name="weekly_sales")
    category = models.ForeignKey(
        'categories.Category', on_delete=models.CASCADE,
        related_name="weekly_sales_category")
    
    class Meta:
        unique_together = ('shop', 'category', 'period_start')
        indexes = [
            models.Index(fields=['shop', 'category', 'period_start']),
        ]


class MonthlySales(BaseAggregateSales):
    """Calculate daily sales"""
    shop = models.ForeignKey(
        'shops.Shop', on_delete=models.CASCADE,
        related_name="monthly_sales")
    category = models.ForeignKey(
        'categories.Category', on_delete=models.CASCADE,
        related_name="monthly_sales_category")
   
    class Meta:
        unique_together = ('shop', 'category', 'period_start')
        indexes = [
            models.Index(fields=['shop', 'category', 'period_start']),
        ]

class YearlySales(BaseAggregateSales):
    """Calculate daily sales"""
    shop = models.ForeignKey(
        'shops.Shop', on_delete=models.CASCADE,
        related_name="yearly_sales")
    category = models.ForeignKey(
        'categories.Category', on_delete=models.CASCADE,
        related_name="yearly_sales_category")
    
    class Meta:
        unique_together = ('shop', 'category', 'period_start')
        indexes = [
            models.Index(fields=['shop', 'category', 'period_start']),
        ]



class BaseTimeSeriesOrderAndSales(models.Model):
    """
    Base class to populate time based series
    for sales and order charting
    """
    total_sales = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    order_count = models.PositiveIntegerField(default=0)
    period_start = models.DateField()
    updated_at = models.DateTimeField(auto_now=True)


    class Meta:
        abstract = True

    def __str__(self):
        period = self.__class__.__name__.replace("ShopSales", "").lower()
        return f"{self.shop.name} - {period} - {self.period_start}"



class DailyShopSales(BaseTimeSeriesOrderAndSales):
    """Calculate daily sales and order chart"""
    shop = models.ForeignKey(
        'shops.Shop', on_delete=models.CASCADE,
        related_name="daily_time_series"
    )

    class Meta:
        unique_together = ('shop', 'period_start')
        indexes = [
            models.Index(fields=['shop', 'period_start']),
        ]


class WeeklyShopSales(BaseTimeSeriesOrderAndSales):
    """Calculate weekly sales and order chart"""
    shop = models.ForeignKey(
        'shops.Shop', on_delete=models.CASCADE,
        related_name="weekly_time_series"
    )

    class Meta:
        unique_together = ('shop', 'period_start')
        indexes = [
            models.Index(fields=['shop', 'period_start']),
        ]


class MonthlyShopSales(BaseTimeSeriesOrderAndSales):
    """Calculate monthly sales and order chart"""
    shop = models.ForeignKey(
        'shops.Shop', on_delete=models.CASCADE,
        related_name="monthly_time_series"
    )

    class Meta:
        unique_together = ('shop', 'period_start')
        indexes = [
            models.Index(fields=['shop', 'period_start']),
        ]


class YearlyShopSales(BaseTimeSeriesOrderAndSales):
    """Calculate yearly sales and order chart"""
    shop = models.ForeignKey(
        'shops.Shop', on_delete=models.CASCADE,
        related_name="yearly_time_series"
    )

    class Meta:
        unique_together = ('shop', 'period_start')
        indexes = [
            models.Index(fields=['shop', 'period_start']),
        ]


class TopSellingProduct(models.Model):
    """
    Model to store monthly data on sellers
    top selling products
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    shop = models.ForeignKey('shops.Shop', on_delete=models.CASCADE, related_name="top_selling")
    product = models.UUIDField()
    category_name = models.CharField(max_length=100)
    title = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    total_quantity_sold = models.PositiveIntegerField()
    latest_order_date = models.DateTimeField()
    image_url = models.URLField()
    month = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('shop', 'product', 'month')
        indexes = [
            models.Index(fields=['shop', 'month'])
        ]

    def __str__(self):
        return f"{self.title} - {self.total_quantity_sold} units"
