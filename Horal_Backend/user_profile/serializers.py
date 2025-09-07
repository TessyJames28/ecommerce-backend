from rest_framework import serializers
from .models import Profile, Image
from django.contrib.auth.password_validation import validate_password
from users.serializers import LocationSerializer, ShippingAddressSerializer
from users.models import Location, CustomUser


class ImageLinkSerializer(serializers.ModelSerializer):
    """Image serializer to handle adding image link to the db"""
    class Meta:
        model = Image
        fields = ['id', 'url', 'alt_text']
        read_only_fields = ['id']



class ProfileSerializer(serializers.ModelSerializer):
    """Serializer for users profile"""
    image = serializers.CharField(required=False)
    current_password = serializers.CharField(write_only=True, required=False)
    phone_number = serializers.CharField(source='user.phone_number')
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
        phone_number = validated_data.pop("user", None).get("phone_number")

        user = instance.user

        if phone_number:
            user.phone_number = phone_number
            user.save(update_fields=["phone_number"])
        

        if image_url:
            image_obj, _ = Image.objects.update_or_create(
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
            user.save(update_fields=['password'])
            user.refresh_from_db()

        return instance
    

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
    