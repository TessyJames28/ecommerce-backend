from django.db import models
from django.utils import timezone
from users.models import CustomUser
from dateutil.relativedelta import relativedelta
from products.models import ProductIndex
import uuid

# Create your models here.

class UserRating(models.Model):
    """
    Model to represent product ratings by user
    after valid purchases
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="user_review")
    order_item = models.OneToOneField("orders.OrderItem", on_delete=models.CASCADE, related_name="order_item")
    product = models.ForeignKey(ProductIndex, on_delete=models.CASCADE, related_name="product")
    rating = models.PositiveIntegerField(choices=[(i, str(i)) for i in range(1, 6)])
    comment = models.TextField(blank=True, null=True)
    date_of_review = models.DateTimeField(default=timezone.now)


    def __str__(self):
        return f"Rating by {self.user.full_name} for {self.order_item.variant}"
    

    def time_since_review(self):
        """Return a human readable time difference"""
        now = timezone.now()
        diff = relativedelta(now, self.date_of_review)

        if diff.years >= 1:
            return f"{diff.years} year{'s' if diff.years > 1 else ''} ago"
        elif diff.months >= 1:
            return f"{diff.months} month{'s' if diff.months > 1 else ''} ago"
        elif diff.days >= 1:
            return f"{diff.days} day{'s' if diff.days > 1 else ''} ago"
        elif diff.hours >= 1:
            return f"{diff.hours} hour{'s' if diff.hours > 1 else ''} ago"
        elif diff.minutes >= 1:
            return f"{diff.minutes} minute{'s' if diff.minutes > 1 else ''} ago"
        else:
            return "Just now"
        
    class Meta:
        verbose_name = "User Rating"
        verbose_name_plural = "User Ratings"
        unique_together = ['user', 'order_item', 'product']