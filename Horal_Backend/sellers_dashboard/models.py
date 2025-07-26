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

