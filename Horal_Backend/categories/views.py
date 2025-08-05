from django.shortcuts import get_object_or_404
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from .models import Category
from categories.models import Category
from .serializers import CategorySerializer
from products.utils import (
    IsAdminOrSuperuser, BaseResponseMixin,
    StandardResultsSetPagination
)
from products.serializers import get_product_serializer

# Create your views here.

class CategoryListView(GenericAPIView, BaseResponseMixin):
    """
    API endpoint to list all categories
    """
    serializer_class = CategorySerializer
    authentication_classes = []  # Disable all authentication backends
    queryset = Category.objects.all()
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        """Get all categories"""
        categories = self.get_queryset()
        serializer = self.get_serializer(categories, many=True)
        return self.get_response(
            status.HTTP_200_OK,
            "Categories retrived successfully",
            serializer.data
        )
    

class CategoryCreateView(GenericAPIView, BaseResponseMixin):
    """
    API endpoint to list all categories or create a new one
    """
    serializer_class = CategorySerializer
    queryset = Category.objects.all()

    def get_permissions(self):
        if self.request.method =='POST':
            return [IsAdminOrSuperuser()]
        return []
    

    def post(self, request, *args, **kwargs):
        """Create a new category"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return self.get_response(
            status.HTTP_201_CREATED,
            "Category created successfully",
            serializer.data
        )
    


class CategoryDetailView(GenericAPIView, BaseResponseMixin):
    """
    API endpoint to update or delete a cetgory by ID
    and list all products in that category.
    """
    serializer_class = CategorySerializer
    queryset = Category.objects.all()

    def get_permissions(self):
        if self.request.method in ['PUT', 'PATCH', 'DELETE']:
            return [IsAdminOrSuperuser()]
        return[]
    

    def put(self, request, pk, *args, **kwargs):
        """update a category"""
        category = get_object_or_404(Category, pk=pk)
        serializer = self.get_serializer(category, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return self.get_response(
            status.HTTP_200_OK,
            "Category updated successfully",
            serializer.data
        )
    

    def patch(self, request, pk, *args, **kwargs):
        """partially update a category"""
        category = get_object_or_404(Category, pk=pk)
        serializer = self.get_serializer(category, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return self.get_response(
            status.HTTP_200_OK,
            "Category updated successfully",
            serializer.data
        )
    

    def delete(self, request, pk, *args,**kwargs):
        """Delete a category"""
        category = get_object_or_404(Category, pk=pk)
        category.delete()
        return Response({
            "status": "success",
            "status code": status.HTTP_204_NO_CONTENT,
            "message": "Category deleted successfully",
        })


class SingleCategoryDetailView(GenericAPIView, BaseResponseMixin):
    """
    API endpoint to retrieve a single category by ID
    and list all products in that category.
    """
    serializer_class = CategorySerializer
    queryset = Category.objects.all()  
    authentication_classes = []  # Disable all authentication backends  
    pagination_class = StandardResultsSetPagination

    def get(self, request, pk, *args, **kwargs):
        """Get a single category and all its products by ID"""
        category = get_object_or_404(Category, pk=pk)
        category_serializer = self.get_serializer(category)


        # Get the product model for this category
        product_model = self.get_product_model_by_category(category.name)
        products = product_model.published.filter(
            category=category) if product_model else []
        
        # Paginate the product queryset
        page = self.paginate_queryset(products)
        if page is not None:
            product_serializer = get_product_serializer(category.name)(page, many=True)
            paginated_response = self.get_paginated_response(product_serializer.data)
            paginated_response.data["category"] = category_serializer.data
            paginated_response.data["status"] = "success"
            paginated_response.data["status_code"] = status.HTTP_200_OK
            paginated_response.data["message"] = "Category and its products retrieved successfully"
        
            return paginated_response
    
        product_serializer = get_product_serializer(category.name)(products, many=True)
        
        response_data = {
            'category': category_serializer.data,
            'products': product_serializer.data
        }

        return self.get_response(
            status.HTTP_200_OK,
            "Category and its products retrieved successfully",
            response_data
        )
