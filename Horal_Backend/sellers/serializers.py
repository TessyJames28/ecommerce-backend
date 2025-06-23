from rest_framework import serializers
from .models import SellerKYC, SellerSocials


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
    