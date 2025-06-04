from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from users.models import CustomUser
import uuid

# Create your models here.
class Favorites(models.Model):
    """
    Model to store favorites products for both authenticated
    and anonymous users
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, blank=True, null=True)
    session_key = models.CharField(max_length=40, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=models.Q(user__isnull=False) | models.Q(session_key__isnull=False),
                name="favorites_user_or_session_key_required"
            )
        ]
        verbose_name_plural = "Favorites"


    def __str__(self):
        if self.user:
            return f"{self.user.full_name}'s favorites"
        return f"Anonymous favorites ({self.session_key})"
    

class FavoriteItem(models.Model):
    """
    Individual product items saved as favorites
    Uses ContentTypes to support different product types
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    favorites = models.ForeignKey(Favorites, on_delete=models.CASCADE, related_name='items')

    # Generic relation to product
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.UUIDField()
    product = GenericForeignKey('content_type', 'object_id')
    
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['favorites', 'content_type', 'object_id']
        ordering = ['-added_at']


    def __str__(self):
        product_name = getattr(self.product, 'title', 'Unknown Product')
        return f"{product_name} in favorites"
