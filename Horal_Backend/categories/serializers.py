from rest_framework import serializers
from .models import Category


class CategorySerializer(serializers.ModelSerializer):
    """Serializer for category creation"""
    class Meta:
        model = Category
        fields = '__all__'
        read_only_fields = ['id']