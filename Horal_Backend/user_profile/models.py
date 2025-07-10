from django.db import models
from users.models import CustomUser
from products.models import ImageLink

# Create your models here.

class Profile(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, primary_key=True, related_name="user_profile")
    full_name = models.CharField(max_length=255)
    email = models.EmailField()
    image = models.ForeignKey(ImageLink, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"Profile of {self.user.full_name}"

