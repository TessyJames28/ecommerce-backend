from rest_framework import serializers
from .models import Logistics


class LogisticsSerializer(serializers.ModelSerializer):
    """Serializer for Logistics model for handling logistics."""
    weight_measurement = serializers.CharField(required=False)

    class Meta:
        model = Logistics
        fields = ['id', 'product_variant', 'object_id', 'weight_measurement', 'total_weight']
        read_only_fields = ['id']
    

    def validate_weight_measurement(self, value):
        from products.textchoices import SizeOption
        from products.serializers import normalize_choice

        return normalize_choice(value, SizeOption.SizeUnit)