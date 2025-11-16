from rest_framework import serializers
from .models import (
    SellerKYC, SellerSocials, SellerKYCNIN,
    SellerKYCCAC, SellerKYCAddress, KYCStatus
)
from django.db.models.signals import post_save
from users.serializers import CustomUserSerializer
from .tasks import create_seller_partial_kyc_handler


class SellerKYCCACSerializer(serializers.ModelSerializer):
    """Serializer for CAC data"""
    class Meta:
        model = SellerKYCCAC
        fields = ['rc_number', 'company_type', 'company_name', 'status', 'cac_verified']


    def create_or_update(self, validated_data):
        """
        Method to create or update CAC record depending
        on customer kyc status
        """
        user = self.context['user']
        seller_kyc, _ = SellerKYC.objects.get_or_create(user=user)

        # Block users from reverifying
        if (seller_kyc.cac and seller_kyc.cac.cac_verified) and \
            (seller_kyc.status == KYCStatus.VERIFIED or seller_kyc.is_verified):
            raise serializers.ValidationError(
                {"detail": "KYC is already verified. Address cannot be changed."}
            )
        
        # Update existing record if any
        if seller_kyc.cac:
            for attr, value in validated_data.items():
                setattr(seller_kyc.cac, attr, value)
            seller_kyc.cac.save()
            seller_kyc.save(update_fields=['cac'])
            return seller_kyc.cac
        
        # Create a new CAC data if none exists
        cac = SellerKYCCAC.objects.create(**validated_data)        
        seller_kyc.cac = cac
        seller_kyc.save(update_fields=['cac'])

        return cac


class SellerKYCAddressSerializer(serializers.ModelSerializer):
    """Serializer for Address image data"""
    class Meta:
        model = SellerKYCAddress
        fields = [
            'first_name', 'last_name', 'middle_name', 'dob', 'gender',
            'mobile', 'street', 'landmark', 'lga', 'state', 'business_name'
        ]

        
    def create_or_update(self, validated_data):
        """
        Create or update address and associate it with a seller
        Based on kyc status
        """
        user = self.context['request'].user
        seller_kyc, _ = SellerKYC.objects.get_or_create(user=user)

        # Block users from reverifying
        if seller_kyc.status == KYCStatus.VERIFIED or seller_kyc.is_verified:
            raise serializers.ValidationError(
                {"detail": "KYC is already verified. Address cannot be changed."}
            )
        
        # Update existing address for re-verification
        if seller_kyc.address:
            for attr, value in validated_data.items():
                setattr(seller_kyc.address, attr, value)
            seller_kyc.address.save()
            seller_kyc.save(update_fields=['address'])
            return seller_kyc.address
            
        # Create a new address if none exists
        address = SellerKYCAddress.objects.create(**validated_data)
        seller_kyc.address = address
        seller_kyc.save(update_fields=['address'])

        # Trigger creation of SellerKYC record task
        create_seller_partial_kyc_handler.delay(user.id)

        return address
     


class SellerKYCNINSerializer(serializers.ModelSerializer):
    """Serializer for NIN detail provided by sellers"""
    class Meta:
        model = SellerKYCNIN
        fields = ['nin', 'selfie', 'status', 'nin_verified']

    
    def create_or_update(self, validated_data):
        """Create or update nin data based seller kyc status"""
        from .signals import notify_kyc_info_completed, notify_kyc_status_change, trigger_related_kyc_verification
        user = self.context['user']
        seller_kyc, _ = SellerKYC.objects.get_or_create(user=user)
        
        # Block users from reverifying
        if seller_kyc.status == KYCStatus.VERIFIED or seller_kyc.is_verified:
            raise serializers.ValidationError(
                {"detail": "KYC is already verified. Address cannot be changed."}
            )
        elif seller_kyc.status == KYCStatus.FAILED or not seller_kyc.is_verified:
            post_save.disconnect(receiver=notify_kyc_info_completed, sender=SellerKYC)
            post_save.disconnect(receiver=notify_kyc_status_change, sender=SellerKYC)
            seller_kyc.info_completed_notified = False
            seller_kyc.status_notified = False
            seller_kyc.save(update_fields=["info_completed_notified", "status_notified"])
        
        # Update existing nin data if any
        post_save.disconnect(receiver=trigger_related_kyc_verification, sender=SellerKYCNIN)
        if seller_kyc.nin:
            for attr, value in validated_data.items():
                setattr(seller_kyc.nin, attr, value)
            seller_kyc.nin.status = KYCStatus.PENDING
            seller_kyc.nin.save()
            seller_kyc.save(update_fields=['nin'])
            return seller_kyc.nin
        
        # Create a new nin if none exists
        post_save.disconnect(receiver=trigger_related_kyc_verification, sender=SellerKYCNIN)
        nin = SellerKYCNIN.objects.create(**validated_data)
        seller_kyc.nin = nin
        seller_kyc.save(update_fields=['nin'])

        return nin
    

class SellerSocialsSerializer(serializers.ModelSerializer):
    """Serializer for the seller's social media links"""
    class Meta:
        model = SellerSocials
        fields = ['facebook', 'instagram', 'tiktok', 'linkedin']


    def create_or_update(self, validated_data):
        """Create or update SellerSocials instance"""
        user = self.context['request'].user
        seller_kyc, _ = SellerKYC.objects.get_or_create(user=user)

        # Update seller social links if exists
        if seller_kyc.socials:
            for attr, value in validated_data.items():
                setattr(seller_kyc.socials, attr, value)
            seller_kyc.socials.save()
            seller_kyc.save(update_fields=['socials'])
            return seller_kyc.socials

        # create new social link if None
        socials = SellerSocials.objects.create(**validated_data)
        seller_kyc.socials = socials
        seller_kyc.save(update_fields=['socials'])

        return socials
        

    def update(self, instance, validated_data):
        """Update an existing SellerSocials instance"""
        instance.facebook = validated_data.get('facebook', instance.facebook)
        instance.instagram = validated_data.get('instagram', instance.instagram)
        instance.tiktok = validated_data.get('tiktok', instance.tiktok)
        instance.linkedin = validated_data.get('linkedin', instance.linkedin)
        instance.save()
        return instance
    

class SellerSerializer(serializers.ModelSerializer):
    """Basic serializer for seller profile"""
    nin = SellerKYCNINSerializer()
    cac = SellerKYCCACSerializer()
    address = SellerKYCAddressSerializer()
    socials = SellerSocialsSerializer()
    user = CustomUserSerializer()

    class Meta:
        model = SellerKYC
        fields = [
            'user', 'country', 'cac', 'nin', 'address', 'socials', 'status', 'is_verified',
            'partial_verified'
        ]
