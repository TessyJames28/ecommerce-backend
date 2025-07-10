from rest_framework import serializers
from .models import Shop


class ShopSerializer(serializers.ModelSerializer):
    """Serializer to handle seller's shops"""
    class Meta:
        model = Shop
        fields = '__all__'
        read_only_fields = ['id']


    def create(self, validated_data):
        """Create a Shop instance"""
        self.context['request'].user
        self.validated_data["created_by_admin"] = True
        return super().create(validated_data)
    

    def validate(self, attrs):
        """Validate shop if for third party sellers"""
        owner_type = attrs.get("owner_type")
        owner = attrs.get("owner")

        if owner_type == Shop.OwnerType.SELLER and not owner:
            raise serializers.ValidationError({
                "seller": "Seller must be set for seller-owned shop."
            })
        
        return attrs
