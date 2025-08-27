from django.utils.timezone import now
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db.models import Q, Avg
from django.core.exceptions import PermissionDenied
from sellers.models import SellerKYC
from sellers_dashboard.serializers import SellerProfileSerializer
from ratings.serializers import UserRatingSerializer
from ratings.models import UserRating
from django.http import Http404
from datetime import timedelta
from rest_framework.exceptions import NotFound
from shops.models import Shop
from rest_framework.permissions import IsAuthenticated, AllowAny
from .utils import (
    BaseResponseMixin, product_models, IsAuthenticated,
    IsSellerAdminOrSuperuser, StandardResultsSetPagination,
    product_models_list, track_recently_viewed_product,
    topselling_product_sql
)
from .models import ProductIndex, RecentlyViewedProduct
from categories.models import Category
from subcategories.models import SubCategory
from .models import ProductVariant
from .serializers import get_product_serializer, MixedProductSerializer
from carts.authentication import SessionOrAnonymousAuthentication


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
        
        category_name = self.kwargs.get('category_name')
        category_name = category_name.replace("-", " ").replace("_", " ").strip().lower()
        
        # Get the category
        category = get_object_or_404(Category, name__iexact=category_name)
        print("I haven't gotten here")

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


    def get(self, request, slug, *args, **kwargs):
        """Get a product by slug"""
        product = None

        for model in product_models_list:
            product = model.objects.filter(slug=slug).first()
            if product:
                break
        
        if not product:
            raise NotFound({
                "status": "error",
                "status_code": status.HTTP_404_NOT_FOUND,
                "message": "Product not found"
            })
        
        # Get index to resolve category and model
        try:
            index = ProductIndex.objects.get(object_id=product.id)
        except ProductIndex.DoesNotExist:
            raise NotFound({
                "status": "error",
                "status_code": status.HTTP_404_NOT_FOUND,
                "message": "Product index not found"
            })
        
        # get the product model based on category
        category_name = index.category_name
        product_model = self.get_product_model_by_category(category_name)
        if not product_model:
            return None, self.get_response(
                status.HTTP_400_BAD_REQUEST,
                f"Invalid category: {category_name}"
            )
        
        # Serialize product
        serializer = self.get_serializer(product)

        # Serialize seller profile
        seller = product.shop.owner.user
        seller_profile_serializer = SellerProfileSerializer(seller.user_profile)
        
        # serialize product review
        reviews = UserRating.objects.filter(product=product.id)
        product_rating = UserRatingSerializer(reviews, many=True)
        
        # Track recently viewed product
        track_recently_viewed_product(request, index)

        return Response({
            "status": "success",
            "status_codes": status.HTTP_200_OK,
            "message": "Product retrieved successfully",
            "product": serializer.data,
            "seller_data": seller_profile_serializer.data,
            "product_review": product_rating.data
        }, status=status.HTTP_200_OK)    


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
            product = index.linked_product
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
                    Q(brand__icontains=search_query) |
                    Q(specifications__icontains=search_query)
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
                for matched_product in products:
                    serializer = MixedProductSerializer(matched_product)
                    data = serializer.data
                    products_data.append(data)

        page = self.paginate_queryset(products_data)
        if page is not None:
            paginated_response = self.get_paginated_response(page)
            paginated_response.data["status"] = "success"
            paginated_response.data["status_code"] = status.HTTP_200_OK
            paginated_response.data["message"] = "Products retrieved successfully"
            return paginated_response
        
        return self.get_response(
            status.HTTP_200_OK,
            "Products retrieved successfully",
            products_data
        )
    


class TopSellingProductListView(GenericAPIView, BaseResponseMixin):
    """
    API endpoint to list topselling products with optional filtering
    """
    authentication_classes = []  # Disable all authentication backends
    pagination_class = StandardResultsSetPagination
    serializer_class = MixedProductSerializer


    def get_queryset(self):
        from_date = now() - timedelta(days=30)
        raw_data = topselling_product_sql(from_date)

        product_ids = [row['product_index_id'] for row in raw_data]

        # Get ProductIndex entries with their actual linked product
        indices = ProductIndex.objects.filter(id__in=product_ids).select_related('content_type')

        # Extract real product instances (GenericForeignKey)
        linked_products = []
        for index in indices:
            product = index.linked_product
            if product is not None:
                linked_products.append(product)

        return linked_products


    def get(self, request, *args, **kwargs):
        category = request.query_params.get('category')
        shop_id = request.query_params.get('shop')
        search_query = request.query_params.get('search')
        brand = request.query_params.get('brand')
        state = request.query_params.get('state')
        local_govt = request.query_params.get('local_govt')
        price_min = request.query_params.get('price_min')
        price_max = request.query_params.get('price_max')
        rating = request.query_params.get('rating')
        sub_category = request.query_params.get('sub_category')

        products_data = []

        linked_products = self.get_queryset()

        for product in linked_products:
            model = product.__class__
            try:
                query = Q(id=product.id)

                if shop_id:
                    query &= Q(shop__id=shop_id)

                if category:
                    query &= Q(category_name__iexact=category)

                if search_query:
                    query &= (
                        Q(title__icontains=search_query) |
                        Q(description__icontains=search_query) |
                        Q(brand__icontains=search_query) |
                        Q(specifications__icontains=search_query)
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

                if rating:
                    products = products.annotate(
                        avg_rating=Avg('reviews__rating')
                    ).filter(avg_rating__gte=rating)

                for p in products:
                    serializer = MixedProductSerializer(p)
                    products_data.append(serializer.data)

            except Exception:
                continue  # In case model manager is missing, etc.

        page = self.paginate_queryset(products_data)
        if page is not None:
            paginated_response = self.get_paginated_response(page)
            paginated_response.data["status"] = "success"
            paginated_response.data["status_code"] = status.HTTP_200_OK
            paginated_response.data["message"] = "Top selling products retrieved successfully"
            return paginated_response

        return self.get_response(
            status.HTTP_200_OK,
            "top selling products retrieved successfully",
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
    

class RecentlyViewedProductView(GenericAPIView, BaseResponseMixin):
    """Class to retrieve recently viewed products"""
    permission_classes = [AllowAny]
    authentication_classes = [SessionOrAnonymousAuthentication]
    serializer_class = MixedProductSerializer

    def get(self, request, *args, **kwargs):
        """Retrieve users recently viewed products"""
        user = request.user
        session_key = request.session.session_key
        

        if not session_key:
            request.session['init'] = True
            request.session.save()
            session_key = request.session.session_key
            

        # fetched viewed items for user or anonymous users
        if user.is_authenticated:
            views = RecentlyViewedProduct.objects.filter(user=user)
        else:
            views = RecentlyViewedProduct.objects.filter(session_key=session_key)

        
        views = views.select_related('product_index')[:20]
        product_ids = [v.product_index.object_id for v in views]
        
        # Match across product models
        products = []
        for model in product_models_list:
            matched = model.objects.filter(id__in=product_ids)
            products.extend(matched)

        # preserve original view order
        product_sorted = sorted(products, key=lambda x: product_ids.index(x.id))
        serializer = self.get_serializer(product_sorted, many=True)

        return self.get_response(
            status.HTTP_200_OK,
            "Recently viewd products retrieved successfully",
            serializer.data
        )
