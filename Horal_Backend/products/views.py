from django.shortcuts import render
from rest_framework import status, permissions
from rest_framework.generics import GenericAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db.models import Q, Avg
from django.core.exceptions import PermissionDenied
from sellers.models import SellerKYC, Shop
from rest_framework.permissions import IsAuthenticated, AllowAny
from .utility import (
    BaseResponseMixin, product_models,
    IsAdminOrSuperuser, IsAuthenticated,
    IsSellerAdminOrSuperuser, update_quantity
)

from carts.authentication import SessionOrAnonymousAuthentication

from .models import Category, ProductVariant, SubCategory
from .serializers import (
    CategorySerializer, get_product_serializer,
    SubCategorySerializer
    )


class StandardResultsSetPagination(PageNumberPagination):
    """Class for product page pagination"""
    page_size = 30 # default per page
    page_size_query_param = 'page_size'
    max_page_size = 100


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


    def put(self, request, category_id):
        """Method that updates the subcategory"""
        subcategory_id = request.data.get("id")
        if not subcategory_id:
            return self.get_response(
                status.HTTP_400_BAD_REQUEST,
                "Subcategory ID is required"
            )
        
        subcategory = get_object_or_404(SubCategory, id=subcategory_id, category_id=category_id)
        
        serializer = self.get_serializer(subcategory, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return self.get_response(
            status.HTTP_200_OK,
            "Subcategory updated successfully",
            serializer.data
        )
    

    def delete(self, request, category_id, *args, **kwargs):
        """Method to delete the subcategory"""
        subcategory_id = request.data.get('id')

        if not subcategory_id:
            return self.get_response(
                status.HTTP_400_BAD_REQUEST,
                "Subcategory ID is required"
            )
        
        subcategory = get_object_or_404(SubCategory, id=subcategory_id, category_id=category_id)
        
        subcategory.delete()
        return Response({
            "status": "success",
            "status code": status.HTTP_204_NO_CONTENT,
            "message": "Subcategory successfully deleted"
        })
    


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
    permission_classes = [AllowAny]
    authentication_classes = []


    def get_serializer_class(self):
        category_name = self.kwargs.get("category_name")
        serializer_class = get_product_serializer(category_name)

        if not serializer_class:
            raise AssertionError(f"No serializer found for category: {category_name}")
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
        product = get_object_or_404(product_model, pk=pk)


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


class ShopProductListView(GenericAPIView, BaseResponseMixin):
    """
    API endpoint to list all products of a shop
    """ 
    permission_classes = [AllowAny]
    authentication_classes = []
    pagination_class = StandardResultsSetPagination

    def get(self, request, shop_id, *args, **kwargs):
        """Get all products of a shop"""
        shop = get_object_or_404(Shop, pk=shop_id)

        products_data = []

        for model, serializer_class, category_name in product_models:
            products = model.published.filter(shop=shop)
            if products.exists():
                serializer = serializer_class(products, many=True)
                for product_data in serializer.data:
                    product_data['category_name'] = category_name
                    products_data.append(product_data)
                    print(products_data)

        page = self.paginate_queryset(products_data)
        if page is not None:
            paginated_response = self.get_paginated_response(products_data)
            paginated_response.data["status"] = "success"
            paginated_response.data["status_code"] = status.HTTP_200_OK
            paginated_response.data["message"] = "Shop products retrieved successfully"
        
        return paginated_response
    

class ProductListView(GenericAPIView, BaseResponseMixin):
    """
    API endpoint to list all products with optional filtering
    """
    authentication_classes = []  # Disable all authentication backends
    pagination_class = StandardResultsSetPagination

    def get(self, request, *args, **kwargs):
        """Get all products with optional filtering"""
        # Get query parameters
        category_name = request.query_params.get('category')
        shop_id = request.query_params.get('shop')
        search_query = request.query_params.get('search')

        # Advanced filters
        brand = request.query_params.get('brand')
        state = request.query_params.get('state')
        local_govt = request.query_params.get('local_govt')
        price_min = request.query_params.get('price_min')
        price_max = request.query_params.get('price_max')
        # rating = request.query_params.get('rating')
        sub_category = request.query_params.get('sub_category')

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

            products = model.published.filter(query)

            # Future support for rating
            # if rating:
            #     products = products.annotate(avg_rating=Avg(
            #         'reviews_-rating'
            #     )).filter(avg_rating__gte=rating)

            if products.exists():
                serializer = serializer_class(products, many=True)
                for product_data in serializer.data:
                    product_data['category_name'] = model_category_name
                    products_data.append(product_data)

        page = self.paginate_queryset(products_data)
        if page is not None:
            paginated_response = self.get_paginated_response(products_data)
            paginated_response.data["status"] = "success"
            paginated_response.data["status_code"] = status.HTTP_200_OK
            paginated_response.data["message"] = "Products retrieved successfully"
        
        return paginated_response
    


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
