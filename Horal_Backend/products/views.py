from django.utils.timezone import now
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.core.exceptions import PermissionDenied
from sellers.models import SellerKYC
from sellers_dashboard.serializers import SellerProductProfileSerializer
from ratings.serializers import UserRatingSerializer
from ratings.models import UserRating
from django.http import Http404
from datetime import timedelta
from users.authentication import CookieTokenAuthentication
from rest_framework.exceptions import NotFound
from shops.models import Shop
from django.db.models import Q, Avg, Value, Case, When
from django.db.models.functions import Coalesce
from django.utils.dateparse import parse_date
from django.core.cache import cache
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from rest_framework.permissions import IsAuthenticated, AllowAny
from .utils import (
    BaseResponseMixin, product_models, IsAuthenticated,
    IsSellerAdminOrSuperuser, StandardResultsSetPagination,
    product_models_list, track_recently_viewed_product,
    topselling_product_sql, generate_list_for_category, 
    REDIS_KEY_NEW, REDIS_KEY_RANDOM, REDIS_KEY_TRENDING, REDIS_TTL
)
from .models import ProductIndex, RecentlyViewedProduct
from categories.models import Category
from subcategories.models import SubCategory
from .models import ProductVariant
from .serializers import get_product_serializer, ProductIndexSerializer, MixedProductSerializer
from carts.authentication import SessionOrAnonymousAuthentication
import random


class ProductBySubcategoryView(GenericAPIView, BaseResponseMixin):
    """Class that returns products linked to a specific subcategory"""
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, subcategory_id):
        """Get all products associated with the subcategory"""
        try:
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
        except Exception as e:
            return self.get_response(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                f"An error occurred while retrieving products under subcategory: {str(e)}"
            )


class ProductCreateView(GenericAPIView, BaseResponseMixin):
    """
    API endpoint to create a new product based on a selected category
    """
    permission_classes = [IsSellerAdminOrSuperuser]
    authentication_classes = [CookieTokenAuthentication]

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
        try:
            user = request.user
            # Check if user is a seller or admin/superadmin
            if not (request.user.is_seller or request.user.is_staff or request.user.is_superuser):
                return self.get_response(
                    status.HTTP_403_FORBIDDEN,
                    "You do not have permission to create products"
                )
            
            # Check total product seller has listed
            shop = Shop.objects.filter(owner__user=user).first()
            products_listed_count = ProductIndex.objects.filter(shop=shop).count()
            if products_listed_count >= 5:
                # Check if seller is KYC verified
                seller_kyc = SellerKYC.objects.filter(user=user, is_verified=True).first()
                if not seller_kyc:
                    return self.get_response(
                        status.HTTP_403_FORBIDDEN,
                        "You have reached the limit of 5 products. Please complete KYC verification to list more products."
                    )
            
            category_name = self.kwargs.get('category_name')
            category_name = category_name.replace("-", " ").replace("_", " ").strip().lower()
            
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
        except Exception as e:
            return self.get_response(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                f"An error occurred while creating products: {str(e)}"
            )
        

class SingleProductDetailView(GenericAPIView, BaseResponseMixin):
    """Class to retrieve a single product per id"""
    serializer_class = MixedProductSerializer
    permission_classes = [AllowAny]
    authentication_classes = []


    def get(self, request, slug, *args, **kwargs):
        """Get a product by slug"""
        try:
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
            category_name = index.category
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
            seller_profile_serializer = SellerProductProfileSerializer(seller.user_profile)
            
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
        except Exception as e:
            # Catch unexpected errors and return standardized API response
            return self.get_response(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                f"An error occurred while retrieving the product: {str(e)}"
            )  


class ProductDetailView(GenericAPIView, BaseResponseMixin):
    """
    API endpoint to retrieve, update or delete a product
    """
    permission_classes = [IsSellerAdminOrSuperuser]
    authentication_classes = [CookieTokenAuthentication]

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
        try:
            product, error_response = self.get_product_and_check_permissions(pk, category_name)
            if error_response:
                return error_response
            return self.update_product(request, product, category_name, partial=False)
        except Exception as e:
            # Catch all unexpected errors
            return self.get_response(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                f"An error occurred while updating the product: {str(e)}"
            )

    def patch(self, request, pk, category_name, *args, **kwargs):
        """Method for partial product update"""
        try:
            product, error_response = self.get_product_and_check_permissions(pk, category_name)
            if error_response:
                return error_response
            return self.update_product(request, product, category_name, partial=True)
        except Exception as e:
            # Catch all unexpected errors
            return self.get_response(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                f"An error occurred while partially updating the product: {str(e)}"
            )

    def delete(self, request, pk, category_name, *args, **kwargs):
        """Method to delete product perform by only staff and superuser"""
        if not request.user.is_staff and not request.user.is_superuser:
            raise PermissionDenied("Only staff or superusers can delete products")

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
    serializer_class = ProductIndexSerializer

    def get_queryset(self):
        return ProductIndex.objects.filter(is_published=True)
    

    def generate_global_lists(self):
        """
        Generate trending, new, and random product ID lists and cache in redis
        """
        qs = self.get_queryset()

        # Trending (Sorted by avg rating)
        trending = qs.annotate(
            avg_rating=Coalesce(Avg("product__rating"), Value(0.0))
        ).order_by("-avg_rating", "-created_at").values_list("id", flat=True)
        cache.set(REDIS_KEY_TRENDING, list(trending), REDIS_TTL)

        # New arrivals (Sorted by created_at)
        new_arrivals = qs.order_by("-created_at").values_list("id", flat=True)
        cache.set(REDIS_KEY_NEW, list(new_arrivals), REDIS_TTL)

        # Random fallback
        random_ids = list(qs.values_list("id", flat=True))
        random.shuffle(random_ids)
        cache.set(REDIS_KEY_RANDOM, random_ids, REDIS_TTL)


    def get_global_lists(self):
        """
        Return global lists, regenerate if not present
        """
        trending = cache.get(REDIS_KEY_TRENDING)
        new_arrivals = cache.get(REDIS_KEY_NEW)
        random_ids = cache.get(REDIS_KEY_RANDOM)

        if not trending or not new_arrivals or not random_ids:
            self.generate_global_lists()
            trending = cache.get(REDIS_KEY_TRENDING)
            new_arrivals = cache.get(REDIS_KEY_NEW)
            random_ids = cache.get(REDIS_KEY_RANDOM)

        return trending, new_arrivals, random_ids
    

    def get_mixed_products_for_user(self, request):
        """
        Build stable per-user feed slice from global lists.
        """

        trending_ids, new_ids, random_ids = self.get_global_lists()

        # Determine how many products to take from each list per page
        page_size = self.pagination_class.page_size if hasattr(self.pagination_class, "paze_size") else 36
        count_new = int(page_size * 0.4)
        count_trending = int(page_size * 0.4)
        count_random = page_size - (count_new + count_trending)

        # Pagination page number
        page_num = int(request.query_params.get('page', 1))
        start = (page_num - 1) * page_size

        # slice from each list
        new_slice = new_ids[start:start + count_new]
        trending_slice = trending_ids[start:start + count_trending]
        random_slice = random_ids[start:start + count_random]

        # Combine slices
        combined_ids = new_slice + trending_slice + random_slice

        # Avoid duplicates while preserving order
        seen = set()
        deduped_ids = []
        for pid in combined_ids:
            if pid not in seen:
                deduped_ids.append(pid)
                seen.add(pid)


        # Fetch products and preserve order
        products_qs = self.get_queryset().filter(id__in=deduped_ids)
        products_dict = {p.id: p for p in products_qs}
        ordered_products = [products_dict[pid] for pid in deduped_ids if pid in products_dict]

        return ordered_products


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
       
    def get(self, request, *args, **kwargs):
        """Get all products with optional filtering"""
        try:
            if request.query_params:
                try:
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
                    created_at = request.query_params.get('created_at')

                    queryset = self.get_queryset()

                    query = Q()

                    if category:
                        # query &= Q(category__iexact=category)
                        trending, new_items, random_items = self.get_category_lists(category)
                    else:
                        trending = cache.get(REDIS_KEY_TRENDING) or []
                        new_items = cache.get(REDIS_KEY_NEW) or []
                        random_items = cache.get(REDIS_KEY_RANDOM) or []

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

                    if created_at:
                        query &= Q(created_at__date=parse_date(created_at)) 

                    # Apply the filter only to the correct model manager
                    products = queryset.filter(query)

                    # If only category filter is applied, reorder using cached order
                    only_category = (
                        category
                        and not shop_id and not search_query and not brand
                        and not state and not local_govt and not price_min and not price_max
                        and not rating and not sub_category and not created_at
                    )

                    if only_category:
                        # Combine cached lists
                        # combined_ids = trending[:12] + new_items[:12] + random_items[:12]
                        combined_ids = trending + new_items + random_items


                        # Deduplicate while preserving order
                        seen = set()
                        ordered_ids = []
                        for pid in combined_ids:
                            if pid not in seen:
                                ordered_ids.append(pid)
                                seen.add(pid)

                        # Filter products using deduplicated IDs
                        # products = products.filter(id__in=ordered_ids) # Returned when company grows

                        # # Preserve order in queryset
                        # preserved_order = Case(
                        #     *[When(id=pid, then=pos) for pos, pid in enumerate(ordered_ids)]
                        # )
                        # products = products.order_by(preserved_order)

                        products = products.annotate(
                            order=Case(
                                *[When(id=pid, then=pos) for pos, pid in enumerate(ordered_ids)],
                                default=999999
                            )
                        ).order_by("order", "-created_at")

                    if rating:
                        rating = float(rating)
                        # Only include products with avg rating >= requested rating
                        products = products.annotate(
                            avg_rating=Coalesce(Avg("product__rating"), Value(0.0)) 
                        ).filter(avg_rating__gte=rating)


                    page = self.paginate_queryset(products)
                    if page is not None:
                        serializer = self.get_serializer(page, many=True)
                        paginated_response = self.get_paginated_response(serializer.data)
                        paginated_response.data["status"] = "success"
                        paginated_response.data["status_code"] = status.HTTP_200_OK
                        paginated_response.data["message"] = "Products retrieved successfully"
                        return paginated_response
                    
                    serializer = ProductIndexSerializer(products, many=True)
                    return self.get_response(
                        status.HTTP_200_OK,
                        "Products retrieved successfully",
                        serializer.data
                    )
                except Exception as e:
                    return self.get_response(
                        status.HTTP_500_INTERNAL_SERVER_ERROR,
                        f"An error occurred while retrieving products: {str(e)}"
                    )
                
            # No filters, use stable mixed feed
            products = self.get_mixed_products_for_user(request)

            serializer = self.get_serializer(products, many=True)
            return self.get_response(
                status.HTTP_200_OK,
                "Products retrieved successfully (mixed stable feed)",
                serializer.data
            )
        except Exception as e:
            return self.get_response(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                f"An error occurred while retrieving products: {str(e)}"
            )


class TopSellingProductListView(GenericAPIView, BaseResponseMixin):
    """
    API endpoint to list topselling products with optional filtering
    """
    authentication_classes = []  # Disable all authentication backends
    pagination_class = StandardResultsSetPagination
    serializer_class = ProductIndexSerializer


    def get_queryset(self):
        from_date = now() - timedelta(days=30)
        raw_data = topselling_product_sql(from_date)

        product_ids = [row['product_index_id'] for row in raw_data]

        # Get ProductIndex entries with their actual linked product
        product_index = ProductIndex.objects.filter(id__in=product_ids, is_published=True)

        return product_index


    def get(self, request, *args, **kwargs):
        """Return top selling products"""
        try:
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

            queryset = self.get_queryset()

            query = Q()

            if shop_id:
                query &= Q(shop__id=shop_id)

            if category:
                query &= Q(category__iexact=category)

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

            products = queryset.filter(query)

            if rating:
                rating = float(rating)
                # Only include products with avg rating >= requested rating
                products = products.annotate(
                    avg_rating=Coalesce(Avg("product__rating"), Value(0.0)) 
                ).filter(avg_rating__gte=rating)

            page = self.paginate_queryset(products)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                paginated_response = self.get_paginated_response(serializer.data)
                paginated_response.data["status"] = "success"
                paginated_response.data["status_code"] = status.HTTP_200_OK
                paginated_response.data["message"] = "Top selling products retrieved successfully"
                return paginated_response

            serializer = self.get_serializer(products, many=True)
            return self.get_response(
                status.HTTP_200_OK,
                "top selling products retrieved successfully",
                products_data
            )
        except Exception as e:
            return self.get_response(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                f"An error occurred while retrieving topselling products: {str(e)}"
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
    serializer_class = ProductIndexSerializer

    def get(self, request, *args, **kwargs):
        """Retrieve users recently viewed products"""
        try:
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

            # Create mapping: product_index_id -> position in views
            position_map = {v.product_index.id: i for i, v in enumerate(views)}

            product_indexes = [v.product_index for v in views]

            # Sort safely, fallback to large number if not found
            product_sorted = sorted(
                product_indexes,
                key=lambda p: position_map.get(p.id, 9999)
            )
            serializer = self.get_serializer(product_sorted, many=True)

            return self.get_response(
                status.HTTP_200_OK,
                "Recently viewd products retrieved successfully",
                serializer.data
            )
        except Exception as e:
            return self.get_response(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                f"An error occurred while retrieving recently viewed products: {str(e)}"
            )
