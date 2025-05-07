from django.shortcuts import render
from rest_framework import status, permissions
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db.models import Q
from sellers.models import SellerKYC
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from sellers.serializers import ShopSerializer
from .utility import (
    BaseResponseMixin, product_models,IsAdminOrSuperuser,
    IsAdminPermission, IsAuthenticated, IsSellerPermission,
    IsSuperAdminPermission, IsSellerAdminOrSuperuser, IsAdminUser
)

from .models import (
    Category, Shop, BabyProduct, VehicleProduct, GadgetProduct,
    FashionProduct, ElectronicsProduct, AccessoryProduct,
    HealthAndBeautyProduct, FoodProduct, ProductVariant
)
from .serializers import (
    CategorySerializer, get_product_serializer,
    BabyProductSerializer, VehicleProductSerializer, GadgetProductSerializer,
    FashionProductSerializer, ElectronicsProductSerializer, FoodProductSerializer,
    HealthAndBeautyProductSerializer, AccessoryProductSerializer
) 


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
        return self.get_response(
            status.HTTP_204_NO_CONTENT,
            "Category deleted successfully",
        )


class SingleCategoryDetailView(GenericAPIView, BaseResponseMixin):
    """
    API endpoint to retrieve a single category by ID
    and list all products in that category.
    """
    serializer_class = CategorySerializer
    queryset = Category.objects.all()  
    authentication_classes = []  # Disable all authentication backends  
    

    def get(self, request, pk, *args, **kwargs):
        """Get a single category and all its products by ID"""
        category = get_object_or_404(Category, pk=pk)
        category_serializer = self.get_serializer(category)


        # Get the product model for this category
        product_model = self.get_product_model_by_category(category.name)
        if product_model:
            products = product_model.objects.filter(category=category)
            product_serializer = get_product_serializer(category.name)(products, many=True)

            response_data = {
                'category': category_serializer.data,
                'products': product_serializer.data
            }
        else:
            response_data = {
                'category': category_serializer.data,
                'products': []
            }

        return self.get_response(
            status.HTTP_200_OK,
            "Category and its products retrieved successfully",
            response_data
        )


class ProductCreateView(GenericAPIView, BaseResponseMixin):
    """
    API endpoint to create a new product based on a selected category
    """
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        category_name = self.kwargs.get('category_name')
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
    


class ProductDetailView(GenericAPIView, BaseResponseMixin):
    """
    API endpoint to retrieve, update or delete a product
    """
    # permission_classes = [IsAuthenticated]
    authentication_classes = []  # Disable all authentication backends

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
        product = get_object_or_404(product_model, pk=pk)


        # Check if the user is the shop owner or an admin/superadmin
        if self.request.user.is_seller and not product.shop.owner.user == self.request.user:
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
    

    def get(self, request, pk, category_name, *args, **kwargs):
        """Get a product by ID"""
        # get the product model based on category
        product_model = self.get_product_model_by_category(category_name)
        if not product_model:
            return None, self.get_response(
                status.HTTP_400_BAD_REQUEST,
                f"Invalid category: {category_name}"
            )
        
        # Get the product
        product = get_object_or_404(product_model, pk=pk)
        
        serializer = self.get_serializer(product)
        return self.get_response(
            status.HTTP_200_OK,
            "Product retrieved successfully",
            serializer.data
        )
    

    def put(self, request, pk, category_name, *args, **kwargs):
        """Update a product"""
        product, error_response = self.get_product_and_check_permissions(pk, category_name)
        if error_response:
            return error_response
        
        serializer = self.get_serializer(product, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return self.get_response(
            status.HTTP_200_OK,
            "Product updated successfully",
            serializer.data
        )
    

    def patch(self, request, pk, category_name, *args, **kwargs):
        """Partially update a product"""
        product, error_response = self.get_product_and_check_permissions(pk, category_name)
        if error_response:
            return error_response
        
        serializer = self.get_serializer(product, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return self.get_response(
            status.HTTP_200_OK,
            "Product updated successfully",
            serializer.data
        )
    

    def delete(self, request, pk, category_name, *args, **kwargs):
        """Delete a product"""
        product, error_response = self.get_product_and_check_permissions(pk, category_name)
        if error_response:
            return error_response
        
        product.delete()
        return self.get_response(
            status.HTTP_204_NO_CONTENT,
            "Product deleted successfully"
        )
    

class ShopProductListView(GenericAPIView, BaseResponseMixin):
    """
    API endpoint to list all products of a shop
    """ 
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, shop_id, *args, **kwargs):
        """Get all products of a shop"""
        shop = get_object_or_404(Shop, pk=shop_id)

        products_data = []

        for model, serializer_class, category_name in product_models:
            products = model.objects.filter(shop=shop)
            if products.exists():
                serializer = serializer_class(products, many=True)
                for product_data in serializer.data:
                    product_data['category_name'] = category_name
                    products_data.append(product_data)
                    print(products_data)

        return self.get_response(
            status.HTTP_200_OK,
            "Shop products retrieved successfully",
            {
                "shop": ShopSerializer(shop).data,
                "products": products_data
            }
        )
    

class ProductListView(GenericAPIView, BaseResponseMixin):
    """
    API endpoint to list all products with optional filtering
    """
    authentication_classes = []  # Disable all authentication backends

    def get(self, request, *args, **kwargs):
        """Get all products with optional filtering"""
        # Get query parameters
        category_name = request.query_params.get('category')
        shop_id = request.query_params.get('shop')
        search_query = request.query_params.get('search')

        products_data = []
    
        for model, serializer_class, model_category_name in product_models:
            # Apply filters
            query = Q()

            if category_name and category_name.lower() != model_category_name.lower():
                continue

            if shop_id:
                query &= Q(shop__id=shop_id)

            if search_query:
                query &= (
                    Q(title__icontains=search_query) |
                    Q(description__icontains=search_query) |
                    Q(brand_name__icontains=search_query)
                )

            products = model.objects.filter(query)

            if products.exists():
                serializer = serializer_class(products, many=True)
                for product_data in serializer.data:
                    product_data['category_name'] = model_category_name
                    products_data.append(product_data)

        return self.get_response(
            status.HTTP_200_OK,
            "Products retrieved successfully",
            products_data
        )
    


class ProductVariantView(GenericAPIView, BaseResponseMixin):
    """
    API endpoint to manage product variants
    """
    permission_classes = [IsAuthenticated]

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
        
        # Check permissions
        is_seller_not_owner = request.user.is_seller and product.shop.owner.user != request.user
        not_staff = not request.user.is_staff

        if is_seller_not_owner or not_staff:
            return self.get_response(
                status.HTTP_403_FORBIDDEN,
                "You do not have permission to access this variant"
            )
        
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
                }
            }
        )
