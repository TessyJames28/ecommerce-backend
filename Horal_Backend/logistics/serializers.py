from rest_framework import serializers
from .models import Logistics


class LogisticsSerializer(serializers.ModelSerializer):
    """Serializer for Logistics model for handling logistics."""
    weight_measurement = serializers.CharField(required=False)

    class Meta:
        model = Logistics
        fields = ['id', 'product_variant', 'object_id', 'weight_measurement', 'total_weight']
        read_only_fields = ['id']


    # def validate(self, data):
    #     # Check for variant instance passed via context
    #     variant_instance = self.context.get('variant_instance')

    #     # For standalone logistics attached to product, use GFK
    #     content_type = data.get('content_type')
    #     object_id = data.get('object_id')

    #     if not variant_instance and not (content_type and object_id):
    #         raise serializers.ValidationError(
    #             "Logistics must be linked to either a product variant or a product."
    #         )

    #     if not data.get('weight_measurement'):
    #         raise serializers.ValidationError("Weight measurement is required.")

    #     if data.get('total_weight') is None:
    #         raise serializers.ValidationError("Total weight is required.")

    #     return data
    

    def validate_weight_measurement(self, value):
        from products.textchoices import SizeOption
        from products.serializers import normalize_choice

        return normalize_choice(value, SizeOption.SizeUnit)