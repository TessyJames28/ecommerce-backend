from rest_framework import serializers
from .models import Profile
from products.models import ImageLink
from django.contrib.auth.password_validation import validate_password
from users.serializers import LocationSerializer, ShippingAddressSerializer
from users.models import Location


class ProfileSerializer(serializers.ModelSerializer):
    """Serializer for users profile"""
    image = serializers.CharField(required=False)
    current_password = serializers.CharField(write_only=True, required=False)
    phone_number = serializers.CharField(source='user.phone_number', read_only=True)
    new_password = serializers.CharField(write_only=True, required=False)
    confirm_password = serializers.CharField(write_only=True, required=False)
    email = serializers.EmailField(read_only=True)
    location = LocationSerializer(source='user.location', read_only=True)
    shipping_address = ShippingAddressSerializer(source='user.shipping_address', read_only=True)

    class Meta:
        model = Profile
        fields = [
            'user', 'full_name', 'email', 'image', 'current_password', 'new_password',
            'confirm_password', 'shipping_address', 'location', 'phone_number',
        ]
        extra_kwargs = {
            'user': {'read_only': True}
        }

    def update(self, instance, validated_data):
        password = validated_data.pop('new_password', None)
        validated_data.pop('confirm_password', None)
        image_url = validated_data.pop("image", None)
        location = self.initial_data.get("location")

        user = instance.user

        if image_url:
            image_obj, _ = ImageLink.objects.get_or_create(
                url=image_url,
            )
            instance.image = image_obj

        # Update profile fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Update location if provided
        if location:
            location = Location.objects.update_or_create(user=user, defaults=location)


        # Update password on the associated CustomUser
        if password:
            user = instance.user
            user.set_password(password)
            user.save()
            user.refresh_from_db()

        return super().update(instance, validated_data)
    

    def validate(self, attrs):
        user = self.instance.user
        current_password = attrs.get('current_password')
        new_password = attrs.get('new_password')
        confirm_password = attrs.get('confirm_password')

        if new_password or confirm_password:
            if not current_password:
                raise serializers.ValidationError({"current_password": "Current password is required to change password."})
            if not user.check_password(current_password):
                raise serializers.ValidationError({"current_password": "Current password is incorrect."})
            if new_password != confirm_password:
                raise serializers.ValidationError({"password": "New passwords do not match."})
            validate_password(new_password)

        return attrs

    

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Replace UUID with image url for frontend
        if instance.image:
            data["image"] = instance.image.url
        return data
    