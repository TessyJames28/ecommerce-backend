from django.shortcuts import get_object_or_404
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from .models import Category
from categories.models import Category
from .serializers import CategorySerializer
from django.db.models import Case, When
from django.core.cache import cache
from products.utils import (
    IsAdminOrSuperuser, BaseResponseMixin,
    StandardResultsSetPagination, CATEGORY_MODEL_MAP,
    generate_list_for_category
)
from products.models import ProductIndex
from products.serializers import ProductIndexSerializer
from users.authentication import CookieTokenAuthentication
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
    authentication_classes = [CookieTokenAuthentication]
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
    authentication_classes = [CookieTokenAuthentication]
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


    def get_category_lists(self, category):
        """Get cached category specific lists"""
        trending = cache.get(f"products_trending_{category}")
        new_items = cache.get(f"products_new_{category}")
        random_items = cache.get(f"products_random_{category}")

        if not trending or not new_items or not random_items:

            generate_list_for_category(category)
            trending = cache.get(f"products_trending_{category}") or []
            new_items = cache.get(f"products_new_{category}") or []
            random_items = cache.get(f"products_random_{category}") or []

        return trending, new_items, random_items

    def get(self, request, pk, *args, **kwargs):
        """Get a single category and all its products by ID"""
        try:
            category = get_object_or_404(Category, pk=pk)
            category_serializer = self.get_serializer(category)

            # Fetch cached category product lists
            trending, new_items, random_items = self.get_category_lists(category.name)

            # Choose the list to drive ordering 
            combined_ids = trending[:12] + new_items[:12] + random_items[:12]

            # Deduplicate while preserving order
            seen = set()
            ordered_ids = []
            for pid in combined_ids:
                if pid not in seen:
                    ordered_ids.append(pid)
                    seen.add(pid)

            # Filter products
            products = ProductIndex.objects.filter(category=category.name, is_published=True, id__in=ordered_ids)

            # Preserve order
            preserved_qs = Case(
                *[When(id=pid, then=pos) for pos, pid in enumerate(ordered_ids)]
            )
            products = products.order_by(preserved_qs)

            # Paginate the product queryset
            page = self.paginate_queryset(products)
            if page is not None:
                product_serializer = ProductIndexSerializer(page, many=True)
                paginated_response = self.get_paginated_response(product_serializer.data)
                paginated_response.data["category"] = category_serializer.data
                paginated_response.data["status"] = "success"
                paginated_response.data["status_code"] = status.HTTP_200_OK
                paginated_response.data["message"] = "Category and its products retrieved successfully"
            
                return paginated_response
        
            product_serializer = ProductIndexSerializer(products, many=True)
            
            response_data = {
                'category': category_serializer.data,
                'products': product_serializer.data
            }

            return self.get_response(
                status.HTTP_200_OK,
                "Category and its products retrieved successfully",
                response_data
            )

        except Exception as e:
                return self.get_response(
                    status.HTTP_500_INTERNAL_SERVER_ERROR,
                    f"An error occurred: {str(e)}",
                    None
                )