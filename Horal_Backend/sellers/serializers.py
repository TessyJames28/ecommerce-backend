from rest_framework import serializers
from .models import (
    SellerKYC, SellerSocials, SellerKYCNIN,
    SellerKYCCAC, SellerKYCAddress
)


class SellerKYCCACSerializer(serializers.ModelSerializer):
    """Serializer for CAC data"""
    class Meta:
        model = SellerKYCCAC
        fields = ['rc_number', 'company_type', 'status', 'cac_verified']


    def create(self, validated_data):
        cac = SellerKYCCAC.objects.create(**validated_data)

        # Attach it to the current seller
        user = self.context['user']
        seller_kyc, _ = SellerKYC.objects.get_or_create(user=user)
        seller_kyc.cac = cac
        seller_kyc.save(update_fields=['cac'])

        return cac


class SellerKYCAddressSerializer(serializers.ModelSerializer):
    """Serializer for Address image data"""
    class Meta:
        model = SellerKYCAddress
        fields = [
            'first_name', 'last_name', 'middle_name', 'dob', 'gender',
            'mobile', 'street', 'landmark', 'lga', 'state'
        ]

    
    def create(self, validated_data):
        """Create address and associate it with a seller"""
        address = SellerKYCAddress.objects.create(**validated_data)

        # Attach it to the current seller
        user = self.context['request'].user
        seller_kyc, _ = SellerKYC.objects.get_or_create(user=user)
        seller_kyc.address = address
        seller_kyc.save(update_fields=['address'])

        return address


class SellerKYCNINSerializer(serializers.ModelSerializer):
    """Serializer for NIN detail provided by sellers"""
    class Meta:
        model = SellerKYCNIN
        fields = ['nin', 'selfie', 'status', 'nin_verified']

    
    def create(self, validated_data):
        """Create address and associate it with a seller"""
        nin = SellerKYCNIN.objects.create(**validated_data)

        # Attach it to the current seller
        user = self.context['user']
        seller_kyc, _ = SellerKYC.objects.get_or_create(user=user)
        seller_kyc.nin = nin
        seller_kyc.save(update_fields=['nin'])

        return nin
    

class SellerSocialsSerializer(serializers.ModelSerializer):
    """Serializer for the seller's social media links"""
    class Meta:
        model = SellerSocials
        fields = ['facebook', 'instagram', 'tiktok']


    def create(self, validated_data):
        """Create a new SellerSocials instance"""
        socials = SellerSocials.objects.create(**validated_data)

        # Attach it to the current seller
        user = self.context['request'].user
        seller_kyc, _ = SellerKYC.objects.get_or_create(user=user)
        seller_kyc.socials = socials
        seller_kyc.save(update_fields=['socials'])

        return socials
        

    def update(self, instance, validated_data):
        """Update an existing SellerSocials instance"""
        instance.facebook = validated_data.get('facebook', instance.facebook)
        instance.instagram = validated_data.get('instagram', instance.instagram)
        instance.tiktok = validated_data.get('tiktok', instance.tiktok)
        instance.save()
        return instance
    

class SellerSerializer(serializers.ModelSerializer):
    """Basic serializer for seller profile"""
    nin = SellerKYCNINSerializer()
    cac = SellerKYCCACSerializer()
    address = SellerKYCAddressSerializer()
    socials = SellerSocialsSerializer()

    class Meta:
        model = SellerKYC
        fields = ['user', 'country', 'cac', 'nin', 'address', 'socials', 'status', 'is_verified']
