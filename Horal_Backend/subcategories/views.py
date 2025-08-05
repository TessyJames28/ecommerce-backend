from django.shortcuts import get_object_or_404
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from .models import SubCategory
from categories.models import Category
from .serializers import SubCategorySerializer
from products.utils import (
    IsAdminOrSuperuser, BaseResponseMixin,
    StandardResultsSetPagination
)
from products.serializers import get_product_serializer

# Create your views here.

class SubCategoryCreateView(GenericAPIView, BaseResponseMixin):
    """
    API endpoint to create sub categories
    """
    serializer_class = SubCategorySerializer
    queryset = SubCategory.objects.all()

    def get_permissions(self):
        if self.request.method =='POST':
            return [IsAdminOrSuperuser()]
        return []
    

    def post(self, request, *args, **kwargs):
        """Create a new sub category"""
        serializer = self.get_serializer(data=request.data)
        print(serializer)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return self.get_response(
            status.HTTP_201_CREATED,
            "Sub category created successfully",
            serializer.data
        )
    

class SubCategoryListView(GenericAPIView, BaseResponseMixin):
    """Handle the retrival subcategories"""
    serializer_class = SubCategorySerializer
    queryset = SubCategory.objects.all()
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, category_id, *args, **kwargs):
        """Handle the retrieval of sub categories"""
        category = get_object_or_404(Category, id=category_id)
        subcategories = SubCategory.objects.filter(category=category)
        serializer = self.get_serializer(subcategories, many=True)
        return self.get_response(
            status.HTTP_200_OK,
            f"Subcategories for {category.name} retrieved successfully",
            serializer.data
        )
    

class SubCategoryDetailView(GenericAPIView, BaseResponseMixin):
    """Handle the retrival, update, and deletion of subcategories"""
    serializer_class = SubCategorySerializer
    queryset = SubCategory.objects.all()
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.request.method in ['PUT', 'DELETE']:
            return [IsAdminOrSuperuser()]
        return[]


    def put(self, request, subcategory_id):
        """Method that updates the subcategory"""
        if not subcategory_id:
            return self.get_response(
                status.HTTP_400_BAD_REQUEST,
                "Subcategory ID is required"
            )
        
        subcategory = get_object_or_404(SubCategory, id=subcategory_id)
        
        serializer = self.get_serializer(subcategory, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return self.get_response(
            status.HTTP_200_OK,
            "Subcategory updated successfully",
            serializer.data
        )
    

    def delete(self, request, subcategory_id, *args, **kwargs):
        """Method to delete the subcategory"""
        if not subcategory_id:
            return self.get_response(
                status.HTTP_400_BAD_REQUEST,
                "Subcategory ID is required"
            )
        
        subcategory = get_object_or_404(SubCategory, id=subcategory_id)
        
        subcategory.delete()
        return Response({
            "status": "success",
            "status code": status.HTTP_204_NO_CONTENT,
            "message": "Subcategory successfully deleted"
        })
    

class SingleSubcategoryListView(GenericAPIView, BaseResponseMixin):
    """Retrieve details for a single subcategory"""
    serializer_class = SubCategorySerializer
    queryset = SubCategory.objects.all()
    permission_classes = [AllowAny]
    authentication_classes = []
    pagination_class = StandardResultsSetPagination

    def get(self, request, subcategory_id, *args, **kwargs):
        """Method that updates the subcategory"""
        try:
            subcategory = get_object_or_404(SubCategory, id=subcategory_id)
        except SubCategory.DoesNotExist:
            return self.get_response(
                status.HTTP_404_NOT_FOUND,
                "Subcategory not found"
            )
        subcategory_serializer = self.get_serializer(subcategory)

        # get the category for the subcategory
        category = subcategory.category
        print(category)

        # Get the product model for this subcategory
        product_model = self.get_product_model_by_category(category.name)
        products = product_model.published.filter(
            category=category, sub_category=subcategory) if product_model else []
        
        # paginate response
        page = self.paginate_queryset(products)
        if page is not None:
            product_serializer = get_product_serializer(category.name)(page, many=True)
            paginated_response = self.get_paginated_response(product_serializer.data)
            # paginated_response.data["category"] = category_serializer.data
            paginated_response.data['subcategory'] = subcategory_serializer.data
            paginated_response.data["status"] = "success"
            paginated_response.data["status_code"] = status.HTTP_200_OK
            paginated_response.data["message"] = "Subcategory and its products retrieved successfully"
        
            return paginated_response
    
        product_serializer = get_product_serializer(category.name)(products, many=True)
        
        response_data = {
            # 'category': category_serializer.data,
            'subcategory': subcategory_serializer.data,
            'products': product_serializer.data
        }

        return self.get_response(
            status.HTTP_200_OK,
            "Subcategory retrieved successfully",
            response_data
        )
