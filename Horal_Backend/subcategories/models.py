from django.db import models
from categories.models import Category
import uuid

# Create your models here.
class SubCategory(models.Model):
    """Model for the different sucategory"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="subcategories")
    name = models.CharField(max_length=100)
    slug = models.CharField(max_length=100, null=True, blank=True)


    def __str__(self):
        return f"{self.name} ({self.category.name})"

