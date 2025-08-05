from rest_framework import serializers
from .models import UserRating


class UserRatingSerializer(serializers.ModelSerializer):
    """Serializer for user rating"""
    user_full_name =serializers.SerializerMethodField()
    time_since_review = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()

    class Meta:
        model = UserRating
        fields = [
            'id', 'user_full_name', 'rating', 'comment',
            'time_since_review', 'image'
        ]

    def get_user_full_name(self, obj):
        return f"{obj.user.full_name}"
    
  
    def get_time_since_review(self, obj):
        return obj.time_since_review() # calls the method on the model


    def get_image(self, obj):
        """Retrieve product image"""
        linked_product = obj.product.linked_product
        if hasattr(linked_product, 'images'):
            first_image = linked_product.images.first()
            if first_image and hasattr(first_image, 'url'):
                return first_image.url
        return None
