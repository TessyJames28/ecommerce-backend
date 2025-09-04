from django.db import models
import uuid

# Create your models here.

class Category(models.Model):
    """Model for product categories."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.name
    
    class Meta:
        indexes = [
            models.Index(fields=['name']),
        ]
    