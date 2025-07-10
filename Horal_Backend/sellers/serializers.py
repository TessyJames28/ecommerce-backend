from rest_framework import serializers
from .models import SellerKYC, SellerSocials
from shops.serializers import ShopSerializer
from users.serializers import LocationSerializer
from users.models import CustomUser, Location


class SellerKYCFirstScreenSerializer(serializers.ModelSerializer):
    """Serializer for the first screen of KYC"""

    def validate_nin(self, value):
        if not value.startswith("https://"):
            raise serializers.ValidationError("NIN must be a valid HTTPS URL.")
        return value
    

    def validate_cac(self, value):
        if not value.startswith("https://"):
            raise serializers.ValidationError("CAC must be a valid HTTPS URL.")
        return value


    class Meta:
        model = SellerKYC
        fields = ['country', 'nin', 'cac']


    def create(self, validated_data):
        """Create a new KYC instance"""
        user = self.context['request'].user
        # validated_data['user'] = user
        return SellerKYC.objects.create(user=user, **validated_data)
    

    def update(self, instance, validated_data):
        """Update an existing KYC instance"""
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance
    

class SellerKYCProofOfAddressSerializer(serializers.ModelSerializer):
    """Serializer for the proof of address screen of KYC"""

    def validate_utility_bill(self, value):
        if not value.startswith("https://"):
            raise serializers.ValidationError("Utility bill must be a valid HTTPS URL.")
        return value


    class Meta:
        model = SellerKYC
        fields = ['utility_bill']

    
    def update(self, instance, validated_data):
        """Update an existing KYC instance"""
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class SellerSocialsSerializer(serializers.ModelSerializer):
    """Serializer for the seller's social media links"""
    class Meta:
        model = SellerSocials
        fields = ['facebook', 'instagram', 'tiktok']


    def create(self, validated_data):
        """Create a new SellerSocials instance"""
        user = self.context['request'].user
        return SellerSocials.objects.create(user=user, **validated_data)
    

    def update(self, instance, validated_data):
        """Update an existing SellerSocials instance"""
        instance.facebook = validated_data.get('facebook', instance.facebook)
        instance.instagram = validated_data.get('instagram', instance.instagram)
        instance.tiktok = validated_data.get('tiktok', instance.tiktok)
        instance.save()
        return instance
    

class SellerSerializer(serializers.ModelSerializer):
    """Basic serializer for seller profile"""
    class Meta:
        model = SellerKYC
        fields = ['user', 'is_verified']


class SellerProfileSerializer(serializers.ModelSerializer):
    location = LocationSerializer()
    kyc = SellerSerializer()
    socials = SellerSocialsSerializer()
    shop = serializers.SerializerMethodField()
    profile_image = serializers.SerializerMethodField()

    class Meta:
        model = CustomUser
        fields = [
            'id', 'full_name', 'email', 'phone_number', 'is_seller', 'profile_image',
            'location', 'kyc', 'socials','shop'
        ]
        read_only_fields = ['id', 'is_seller', 'shop', 'kyc']

    def get_shop(self, obj):
        try:
            return ShopSerializer(obj.kyc.owner.first()).data
        except Exception:
            return None


    def get_profile_image(self, obj):
        return obj.user_profile.image.url if obj.user_profile and obj.user_profile.image else None
    

    def update(self, instance, validated_data):
        # Extract nested data
        location_data = validated_data.pop('location', None)
        kyc_data = validated_data.pop('kyc', None)
        socials_data = validated_data.pop('socials', None)

        # Update base CustomUser fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Update location
        if location_data:
            location, _ = Location.objects.get_or_create(user=instance)
            for attr, value in location_data.items():
                setattr(location, attr, value)
            location.save()

        # Update KYC
        if kyc_data:
            kyc, _ = SellerKYC.objects.get_or_create(user=instance)
            for attr, value in kyc_data.items():
                setattr(kyc, attr, value)
            kyc.save()

        # Update socials
        if socials_data:
            socials, _ = SellerSocials.objects.get_or_create(user=instance)
            for attr, value in socials_data.items():
                setattr(socials, attr, value)
            socials.save()

        return instance
 
    
    def to_internal_value(self, data):
        """Flatten nested serializers to accept flat keys in request"""
        # First let DRF validate top-level fields
        internal = super().to_internal_value(data)

        # Manually group flat fields into nested structure
        location_fields = ['street_address', 'local_govt', 'landmark', 'country', 'state']
        socials_fields = ['facebook', 'instagram', 'tiktok']

        location_data = {field: data.get(field) for field in location_fields if field in data}
        socials_data = {field: data.get(field) for field in socials_fields if field in data}

        if location_data:
            internal['location'] = location_data
        if socials_data:
            internal['socials'] = socials_data

        return internal
