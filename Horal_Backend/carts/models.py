from django.db import models
from users.models import CustomUser
from products.models import ProductVariant
import uuid


class Cart(models.Model):
    """Model to create a shopping cart per user"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, blank=True, null=True, related_name='cart')
    session_key = models.CharField(max_length=40, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


    class Meta:
        constraints = [
            models.CheckConstraint(
                check=models.Q(user__isnull=False) | models.Q(session_key__isnull=False),
                name="cart_user_or_session_key_required"
            )
        ]


    @property
    def total_price(self):
        return sum(item.item_total_price for item in self.cart_item.all())
    

    @property
    def total_item(self):
        return len(self.cart_item.all())

    def __str__(self):
        return f"{self.user.full_name}'s cart"
    

class CartItem(models.Model):
    """Eachitem added to the cart will point to a variant"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='cart_item')
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, null=True, blank=True)
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        unique_together = ['cart', 'variant']


    @property
    def item_total_price(self):
        price = self.variant.price_override or self.variant.product.price
        return price * self.quantity
    

    def __str__(self):
        return f"{self.variant} x {self.quantity}"
