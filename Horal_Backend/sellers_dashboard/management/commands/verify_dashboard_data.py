from django.core.management.base import BaseCommand
from django.db.models import Sum, F, ExpressionWrapper, DecimalField
from orders.models import OrderItem
from sellers_dashboard.models import DailyShopSales, RawSale
from shops.models import Shop

class Command(BaseCommand):
    help = "Verify that dashboard analytics match sales data"

    def handle(self, *args, **kwargs):
        self.stdout.write("🚀 Verifying dashboard data consistency...")

        raw_total = RawSale.objects.filter(is_valid=True).aggregate(
            revenue=Sum("total_price"),
            quantity=Sum("quantity")
        )

        order_items = OrderItem.objects.filter(
            order__status__in=["paid", "shipped", "delivered"]
        )

        order_total = order_items.annotate(
            line_total=ExpressionWrapper(F("quantity") * F("unit_price"), output_field=DecimalField())
        ).aggregate(
            revenue=Sum("line_total")
        )

        order_quantity = order_items.aggregate(quantity=Sum("quantity"))

        time_series_total = DailyShopSales.objects.aggregate(
            revenue=Sum("total_sales"),
            quantity=Sum("order_count")
        )

        def show(label, a, b):
            match = a == b
            status = "✅" if match else "❌"
            self.stdout.write(f"{label}: {a} vs {b} → {status}")
            return match

        r1 = show("Total Revenue (RawSale vs OrderItem)", raw_total["revenue"], order_total["revenue"])
        r2 = show("Total Quantity (RawSale vs OrderItem)", raw_total["quantity"], order_quantity["quantity"])
        r3 = show("Total Revenue (RawSale vs Time Series)", raw_total["revenue"], time_series_total["revenue"])
        r4 = show("Total Quantity (RawSale vs Time Series)", raw_total["quantity"], time_series_total["quantity"])

        if all([r1, r2, r3, r4]):
            self.stdout.write(self.style.SUCCESS("\n🎉 All metrics match! Dashboard is consistent."))
        else:
            self.stdout.write(self.style.WARNING("\n⚠️ Mismatch detected. Investigate further."))
