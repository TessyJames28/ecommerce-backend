from rest_framework import serializers
from .models import SubCategory


class SubCategorySerializer(serializers.ModelSerializer):
    """Class that handles subcategory serialization"""
    category_name = serializers.SerializerMethodField()

    class Meta:
        model = SubCategory 
        fields = ['id', 'name', 'slug', 'category', 'category_name']

    
    def get_category_name(self, obj):
        return  f"{obj.category.name}"
    

class SubCategoryProductSerializer(serializers.ModelSerializer):
    """Class that handles subcategory serialization"""

    class Meta:
        model = SubCategory 
        fields = ['id', 'name', 'slug']