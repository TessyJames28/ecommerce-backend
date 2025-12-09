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
    email = serializers.CharField(source='user.email')
    new_password = serializers.CharField(write_only=True, required=False)
    confirm_password = serializers.CharField(write_only=True, required=False)
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

        # Check is "user" key in validated data
        if "user" in validated_data:
            user_data = validated_data.pop("user", None)
            phone_number = user_data.pop("phone_number", None)
            email = user_data.pop("email", None)
        else:
            phone_number = validated_data.pop("phone_number", None)
            # email = validated_data.pop("email", None)

        full_name = validated_data.get("full_name", None)

        user = instance.user

        # if email:               
        #     user.email = email

        if full_name:
            user.full_name = full_name

        if phone_number:
            user.phone_number = phone_number

        if phone_number or full_name:
            user.save(update_fields=["phone_number", "full_name"])
        

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
    