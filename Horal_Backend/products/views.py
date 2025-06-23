from django.shortcuts import render
from rest_framework import status, permissions
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db.models import Q, Avg
from django.core.exceptions import PermissionDenied
from sellers.models import SellerKYC
from django.http import Http404
from rest_framework.exceptions import NotFound
from shops.models import Shop
from rest_framework.permissions import IsAuthenticated, AllowAny
from itertools import chain
from .utility import (
    BaseResponseMixin, product_models, IsAuthenticated,
    IsSellerAdminOrSuperuser, StandardResultsSetPagination,
    get_product_queryset
)
from .models import ProductIndex
from categories.models import Category
from subcategories.models import SubCategory
from .models import ProductVariant
from .serializers import get_product_serializer, MixedProductSerializer
  

class ProductBySubcategoryView(GenericAPIView, BaseResponseMixin):
    """Class that returns products linked to a specific subcategory"""
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, subcategory_id):
        """Get all products associated with the subcategory"""
        subcategory = get_object_or_404(SubCategory, id=subcategory_id)

        # Dynamically search all product models
        product_data = []
        for model, serializer_class, _ in product_models:
            if 'sub_category' in [f.name for f in model._meta.fields]:
                products = model.published.filter(sub_category=subcategory)
                serializer = serializer_class(products, many=True)
                product_data.extend(serializer.data)

        return self.get_response(
            status.HTTP_200_OK,
            f"Products under subcategory {subcategory.name} retrieved successfully",
            product_data
        )


class ProductCreateView(GenericAPIView, BaseResponseMixin):
    """
    API endpoint to create a new product based on a selected category
    """
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        category_name = self.kwargs.get('category_name')
        category_name = category_name.replace("-", " ").replace("_", " ").strip().lower()
        # category = Category.objects.get(name__iexact=normalized_name)
        serializer_class = get_product_serializer(category_name)
        if not serializer_class:
            raise ValueError(f"Invalid category: {category_name}")
        return serializer_class
    

    def post(self, request, category_name, *args, **kwargs):
        """Create a new product"""
        user = request.user
        # Check if user is a seller or admin/superadmin
        if not (request.user.is_seller or request.user.is_staff or request.user.is_superuser):
            return self.get_response(
                status.HTTP_403_FORBIDDEN,
                "You do not have permission to create products"
            )
        
        # Get the category
        category = get_object_or_404(Category, name__iexact=category_name)

        # Get seller's shop internally (skip request.data.get('shop'))
        if user.is_seller:
            seller_kyc = get_object_or_404(SellerKYC, user=user)
            shop = get_object_or_404(Shop, owner=seller_kyc)
        else:
            shop_id = request.data.get('shop')
            if not shop_id:
                return self.get_response(
                    status.HTTP_400_BAD_REQUEST,
                    "Admin must specify a shop ID"
                )
            shop = get_object_or_404(Shop, id=shop_id)

        # Add data value internally
        data = request.data.copy()
        data['category'] = str(category.id)
        data['shop'] = str(shop.id)

        # Serialize and save
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return self.get_response(
            status.HTTP_201_CREATED,
            f"{category_name} product created successfully",
            serializer.data
        )
    

class SingleProductDetailView(GenericAPIView, BaseResponseMixin):
    """Class to retrieve a single product per id"""
    serializer_class = MixedProductSerializer
    permission_classes = [AllowAny]
    authentication_classes = []


    def get(self, request, pk, *args, **kwargs):
        """Get a product by ID"""
        try:
            index = get_object_or_404(ProductIndex, object_id=pk)
        except Http404:
           raise NotFound({
                "status": "error",
                "status_code": 404,
                "message": "Product not found",
            })
        
        # get the product model based on category
        category_name = index.category_name
        product_model = self.get_product_model_by_category(category_name)
        if not product_model:
            return None, self.get_response(
                status.HTTP_400_BAD_REQUEST,
                f"Invalid category: {category_name}"
            )
        
        # Get the product
        try:
            product = get_object_or_404(product_model, pk=pk)
        except Http404:
           raise NotFound({
                "status": "error",
                "status_code": 404,
                "message": "Product not found",
            })
        
        serializer = self.get_serializer(product)
        return self.get_response(
            status.HTTP_200_OK,
            "Product retrieved successfully",
            serializer.data
        )    


class ProductDetailView(GenericAPIView, BaseResponseMixin):
    """
    API endpoint to retrieve, update or delete a product
    """
    permission_classes = [IsSellerAdminOrSuperuser]
    # authentication_classes = []  # Disable all authentication backends

    def get_product_and_check_permissions(self, pk, category_name):
        """Get the product and check permissions"""

        # get the product model based on category
        product_model = self.get_product_model_by_category(category_name)
        if not product_model:
            return None, self.get_response(
                status.HTTP_400_BAD_REQUEST,
                f"Invalid category: {category_name}"
            )
        
        # Get the product
        try:
            product = get_object_or_404(product_model, pk=pk)
        except Http404:
           raise NotFound({
                "status": "error",
                "status_code": 404,
                "message": "Product not found",
            })


        # Check if the user is the shop owner or an admin/superadmin
        if self.request.user.is_seller and product.shop.owner.user != self.request.user:
            return product, self.get_response(
                status.HTTP_403_FORBIDDEN,
                "You do not have permission to access this product"
            )
        
        return product, None
    

    def get_serializer_class(self):
        category_name = self.kwargs.get('category_name')
        serializer_class = get_product_serializer(category_name)
        if not serializer_class:
            raise ValueError(f"Invalid category: {category_name}")
        return serializer_class
    

    def update_product(self, request, product, category_name, partial=False):
        user = request.user
        data = request.data.copy()

        # Auto inject shop
        if user.is_seller:
            seller_kyc = get_object_or_404(SellerKYC, user=user)
            shop = get_object_or_404(Shop, owner=seller_kyc)
            data['shop'] = str(shop.id)
        else:
            shop_id = request.data.get('shop')
            if not shop_id:
                return self.get_response(
                    status.HTTP_400_BAD_REQUEST,
                    "Admin must specify a shop ID"
                )
            data['shop'] = shop_id

        # Auto inject category
        try:
            category = Category.objects.get(name__iexact=category_name)
            data['category'] = str(category.id)
        except Category.DoesNotExist:
            return self.get_response(
                status.HTTP_400_BAD_REQUEST,
                "Invalid category provided"
            )

        serializer = self.get_serializer(product, data=data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return self.get_response(
            status.HTTP_200_OK,
            "Product updated successfully",
            serializer.data
        )

    def put(self, request, pk, category_name, *args, **kwargs):
        """Method for product update"""

        product, error_response = self.get_product_and_check_permissions(pk, category_name)
        if error_response:
            return error_response
        return self.update_product(request, product, category_name, partial=False)

    def patch(self, request, pk, category_name, *args, **kwargs):
        """Method for partial product update"""

        product, error_response = self.get_product_and_check_permissions(pk, category_name)
        if error_response:
            return error_response
        return self.update_product(request, product, category_name, partial=True)

    def delete(self, request, pk, category_name, *args, **kwargs):
        """Method to delete product perform by only staff and superuser"""
        if not request.user.is_staff and not request.user.is_superuser:
            raise PermissionDenied("Only staff or superusers can delete user locations")

        product, error_response = self.get_product_and_check_permissions(pk, category_name)
        if error_response:
            return error_response
        product.delete()
        return self.get_response(status.HTTP_204_NO_CONTENT, "Product deleted successfully")
    

class ProductListView(GenericAPIView, BaseResponseMixin):
    """
    API endpoint to list all products with optional filtering
    """
    authentication_classes = []  # Disable all authentication backends
    pagination_class = StandardResultsSetPagination
    serializer_class = MixedProductSerializer


    def get_queryset(self):
        return ProductIndex.objects.select_related('content_type')

    def get(self, request, *args, **kwargs):
        """Get all products with optional filtering"""
        # Get query parameters
        category = request.query_params.get('category')
        shop_id = request.query_params.get('shop')
        search_query = request.query_params.get('search')

        # Advanced filters
        brand = request.query_params.get('brand')
        state = request.query_params.get('state')
        local_govt = request.query_params.get('local_govt')
        price_min = request.query_params.get('price_min')
        price_max = request.query_params.get('price_max')
        rating = request.query_params.get('rating')
        sub_category = request.query_params.get('sub_category')

        products_data = []

        queryset = self.get_queryset()

        if category:
            queryset = queryset.filter(category_name__iexact=category)
    
        for index in queryset:
            product = index.product
            if product is None:
                continue  # Skip if GenericForeignKey couldn't resolve
            
            model = product.__class__
            query = Q(id=product.id)
        

            if shop_id:
                query &= Q(shop__id=shop_id)

            if search_query:
                query &= (
                    Q(title__icontains=search_query) |
                    Q(description__icontains=search_query) |
                    Q(brand__icontains=search_query)
                )

            if brand:
                query &= Q(brand__icontains=brand)

            if state:
                query &= Q(state__iexact=state)

            if local_govt:
                query &= Q(local_govt__icontains=local_govt)

            if price_min:
                query &= Q(price__gte=price_min)

            if price_max:
                query &= Q(price__lte=price_max)

            if sub_category:
                query &= Q(sub_category__iexact=sub_category)

            # Apply the filter only to the correct model manager
            products = model.published.filter(query)

            if rating:
                products = products.annotate(avg_rating=Avg(
                    'reviews__rating'
                )).filter(avg_rating__gte=rating)

            if products.exists():
                serializer = MixedProductSerializer(product)
                data = serializer.data
                data['category_name'] = index.category_name
                products_data.append(data)

        page = self.paginate_queryset(products_data)
        if page is not None:
            paginated_response = self.get_paginated_response(products_data)
            paginated_response.data["status"] = "success"
            paginated_response.data["status_code"] = status.HTTP_200_OK
            paginated_response.data["message"] = "Products retrieved successfully"
            return paginated_response
        
        return self.get_response(
            status.HTTP_200_OK,
            "Products retrieved successfully",
            products_data
        )
    


class ProductVariantView(GenericAPIView, BaseResponseMixin):
    """
    API endpoint to manage product variants
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def get_permissions(self):
        if self.request.method == 'GET':
            return [IsAuthenticated()]  # Requiring auth for GET
        return [AllowAny()]  # Allowing anonymous for other methods

    def get_product_by_variant(self, variant_id):
        """Get the product associated with a variant"""
        variant = get_object_or_404(ProductVariant, pk=variant_id)
        product = variant.product
        model = variant.content_type.model_class()
        category_name = model.__name__.replace('Product', '').lower()

        return product, variant, category_name
    

    def get(self, request, variant_id, *args, **kwargs):
        """Get a product variant"""
        product, variant, category_name = self.get_product_by_variant(variant_id)

        if not product:
            return self.get_response(
                status.HTTP_404_NOT_FOUND,
                "Product variant not found"
            )
        
        related_variants = ProductVariant.objects.filter(
            content_type=variant.content_type,
            object_id=variant.object_id
        )

        # Get available sizes for the selected color
        standard_sizes_for_color = related_variants.filter(
            color=variant.color,
            standard_size__isnull=False,
        ).values_list(
            "standard_size", flat=True).distinct()
        
        # Get available custom size values and units for the selected color
        custom_sizes_for_color = related_variants.filter(
            color=variant.color,
            custom_size_value__isnull=False
        ).values_list(
            "custom_size_value", "custom_size_unit").distinct()
        
        # Available colors for the selected standard size
        color_for_standard_size = related_variants.filter(
            standard_size=variant.standard_size
        ).values_list(
            "color", flat=True).distinct()
        
        # Available colors for the selected custom size
        colors_for_custom_size = related_variants.filter(
            custom_size_value=variant.custom_size_value,
            custom_size_unit=variant.custom_size_unit
        ).values_list("color", flat=True).distinct()

        # Serialize product
        serializer_class = get_product_serializer(category_name)
        product_serializer = serializer_class(product)

        return self.get_response(
            status.HTTP_200_OK,
            "Product variant retrieved successfully",
            {
                "product": product_serializer.data,
                "variant": {
                    "id": str(variant.id),
                    "color": variant.color,
                    "standard_size": variant.standard_size,
                    "custom_size_unit": variant.custom_size_unit,
                    "custom_size_value": variant.custom_size_value,
                    "stock_quantity": variant.stock_quantity,
                    "price_override": variant.price_override
                },
                "available_options": {
                    "standard_sizes_for_color": list(standard_sizes_for_color),
                    "custom_sizzes_for_color": list(custom_sizes_for_color),
                    "colors_for_standard_size": list(color_for_standard_size),
                    "colors_for_custom_size": list(colors_for_custom_size)
                }
            }
        )
