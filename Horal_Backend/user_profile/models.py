from django.db import models
from users.models import CustomUser
import uuid

# Create your models here.

class Image(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    url = models.URLField()
    alt_text = models.CharField(max_length=255, null=True, blank=True)
    
    def __str__(self):
        return self.url or self.alt_text

class Profile(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, primary_key=True, related_name="user_profile")
    full_name = models.CharField(max_length=255)
    email = models.EmailField()
    image = models.ForeignKey(Image, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"Profile of {self.user.full_name}"

