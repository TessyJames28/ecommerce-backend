from rest_framework import serializers
from .models import SellerKYC, SellerSocials


class SellerKYCFirstScreenSerializer(serializers.ModelSerializer):
    """Serializer for the first screen of KYC"""
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
        instance.country = validated_data.get('country', instance.country)
        instance.nin = validated_data.get('nin', instance.nin)
        instance.cac = validated_data.get('cac', instance.cac)
        instance.save()
        return instance
    

class SellerKYCProofOfAddressSerializer(serializers.Serializer):
    """Serializer for the proof of address screen of KYC"""
    utility_bill = serializers.FileField(required=True, allow_empty_file=False)

    class Meta:
        model = SellerKYC
        fields = ['utility_bill']

    
    def update(self, instance, validated_data):
        """Update an existing KYC instance"""
        instance.utility_bill = validated_data.get('utility_bill', instance.utility_bill)
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