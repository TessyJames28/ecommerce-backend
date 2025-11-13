from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.utils.timezone import now
from rest_framework import serializers
from .models import (
    ChildrenProduct, VehicleProduct, GadgetProduct,
    FashionProduct, ElectronicsProduct, AccessoryProduct,
    HealthAndBeautyProduct, FoodProduct, RecentlyViewedProduct,
    VehicleImage, FashionImage, ElectronicsImage, FoodImage,
    HealthAndBeautyImage, AccessoryImage, ChildrenImage, GadgetImage
)

from .serializers import (
    ChildrenProductSerializer, VehicleProductSerializer, GadgetProductSerializer,
    FashionProductSerializer, ElectronicsProductSerializer, FoodProductSerializer,
    HealthAndBeautyProductSerializer, AccessoryProductSerializer, normalize_choice
) 
from django.db import connection
from django.utils.timezone import now
from django.core.cache import cache
from products.models import ProductIndex
from django.db.models import Avg, Value
from django.db.models.functions import Coalesce
import random

REDIS_KEY_TRENDING = "products_trending_ids"
REDIS_KEY_NEW = "products_new_ids"
REDIS_KEY_RANDOM = "products_random_ids"
REDIS_TTL = 43200  # 12 hours


# List of all product models and their serializers
product_models = [
    (ChildrenProduct, ChildrenProductSerializer, 'children'),
    (VehicleProduct, VehicleProductSerializer, 'vehicles'),
    (GadgetProduct, GadgetProductSerializer, 'gadget'),
    (FashionProduct, FashionProductSerializer, 'fashion'),
    (ElectronicsProduct, ElectronicsProductSerializer, 'electronics'),
    (AccessoryProduct, AccessoryProductSerializer, 'accessories'),
    (HealthAndBeautyProduct, HealthAndBeautyProductSerializer, 'health and beauty'),
    (FoodProduct, FoodProductSerializer, 'foods')
]

product_models_list = [
    ChildrenProduct,
    VehicleProduct,
    FashionProduct,
    GadgetProduct,
    ElectronicsProduct,
    AccessoryProduct,
    FoodProduct,
    HealthAndBeautyProduct
]

# Product image mapping
IMAGE_MAP = {
    "fashion": FashionImage,
    "foods": FoodImage,
    "gadget": GadgetImage,
    "electronics": ElectronicsImage,
    "accessories": AccessoryImage,
    "health and beauty": HealthAndBeautyImage,
    "vehicles": VehicleImage,
    "children": ChildrenImage,
}

# Dynamically determine the right image model based on product model
image_model_map = {
    "VehicleProduct": VehicleImage,
    "FashionProduct": FashionImage,
    "ElectronicsProduct": ElectronicsImage,
    "FoodProduct": FoodImage,
    "HealthAndBeautyProduct": HealthAndBeautyImage,
    "AccessoryProduct": AccessoryImage,
    "ChildrenProduct": ChildrenImage,
    "GadgetProduct": GadgetImage,
}

class BaseResponseMixin:
    """
    Mixin that provides standard response formatting
    """

    def get_response(self, status_code, message, data=None):
        """Format the API response"""
        response_data = {
            "status": "success" if status_code < 400 else "error",
            "status_code": status_code,
            "message": message
        }

        if data is not None:
            response_data["data"] = data
        return Response(response_data, status=status_code)
    

    def get_product_model_by_category(self, category_name):
        """Get the product model based on category name"""
        mapping = {
            'children': ChildrenProduct,
            'vehicles': VehicleProduct,
            'gadget': GadgetProduct,
            'fashion': FashionProduct,
            'electronics': ElectronicsProduct,
            'accessories': AccessoryProduct,
            'health and beauty': HealthAndBeautyProduct,
            'foods': FoodProduct
        }

        return mapping.get(category_name.lower())
    

# Product category mapping
CATEGORY_MODEL_MAP = {
    "fashion": FashionProduct,
    "foods": FoodProduct,
    "gadget": GadgetProduct,
    "electronics": ElectronicsProduct,
    "accessories": AccessoryProduct,
    "health and beauty": HealthAndBeautyProduct,
    "vehicles": VehicleProduct,
    "children": ChildrenProduct,
}
    

# Permissions
class IsSuperAdminPermission(IsAdminUser):
    """Permission class for super admin users"""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_superuser)
    

class IsAdminPermission(IsAdminUser):
    """Permission class for admin users"""
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_staff)
    

class IsSellerPermission(IsAuthenticated):
    """Permission class for sellers"""
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_seller)
    

# For admin and superuser permission
class IsAdminOrSuperuser(IsAuthenticated):
    """Permission class for both admin and superuser"""
    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated and
            (request.user.is_staff or request.user.is_superuser)
        )
    

class IsSellerAdminOrSuperuser(IsAuthenticated):
    """Permission class for both admin and superuser"""
    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated and
            (request.user.is_staff or request.user.is_superuser or request.user.is_seller)
        )      
    

# helper function to update total stock for products after purchases
def update_quantity(product):
    total = sum(v.stock_quantity + v.reserved_quantity for v in product.get_variants())
    product.quantity = total
    product.save(update_fields=['quantity'])


class StandardResultsSetPagination(PageNumberPagination):
    """Class for product page pagination"""
    page_size = 30 # default per page
    page_size_query_param = 'limit'
    max_page_size = 100


def get_product_queryset():
    """Get all product queryset from different categories"""
    from itertools import chain
    return list(chain(
        FashionProduct.objects.all(),
        FoodProduct.objects.all(),
        GadgetProduct.objects.all(),
        ElectronicsProduct.objects.all(),
        AccessoryProduct.objects.all(),
        HealthAndBeautyProduct.objects.all(),
        VehicleProduct.objects.all(),
        ChildrenProduct.objects.all(),
    ))

def track_recently_viewed_product(request, index):
    """Function to track recently viewed products"""
    if request.user.is_authenticated:
        RecentlyViewedProduct.objects.update_or_create(
            user=request.user,
            product_index=index,
            defaults={'viewed_at': now()}
        )
    else:
        session_key = request.session.session_key
        if not session_key:
            request.session.save()
            session_key = request.session.session_key

        RecentlyViewedProduct.objects.update_or_create(
            session_key=session_key,
            product_index=index,
            defaults={'viewed_at': now()}
        )


def merge_recently_viewed_products(session_key, user):
    if not session_key or not user:
        return
    
    anon_views = RecentlyViewedProduct.objects.filter(session_key=session_key)

    for view in anon_views:
        # if already exists under the user, update timestamp if newer
        obj, created = RecentlyViewedProduct.objects.update_or_create(
            user=user,
            product_index=view.product_index,
            defaults={
                'viewed_at': max(view.viewed_at, now())
            }
        )

    # Clean up anon views after merge
    anon_views.delete()



def topselling_product_sql(from_date):
    """Raw sql to get top selling product per seller"""
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT
                pi.id AS product_index_id,
                SUM(oi.quantity) AS total_quantity_sold,
                MAX(o.created_at) AS latest_order_date
            FROM
                orders_orderitem oi
            JOIN
                "orders_order" o ON oi.order_id = o.id
            JOIN
                products_productvariant pv ON oi.variant_id = pv.id
            JOIN
                products_productindex pi ON pi.id = pv.object_id
                       
            WHERE
                o.status = 'paid'
                AND o.created_at >= %s
            GROUP BY
                pi.id
            ORDER BY
                total_quantity_sold DESC
            LIMIT 90;

        """, [from_date])
        
        # Get column names for dictionary output
        rows = cursor.fetchall()  # ✅ fetch once
        columns = [col[0] for col in cursor.description]
        raw_data = [dict(zip(columns, row)) for row in rows]

    return raw_data



def normalize_weight(value: float | None, unit: str) -> float | None:
    """
    Convert weight into kilograms.
    Returns None if no weight is provided or if the unit is not a weight unit.
    """
    if value is None:
        return None

    unit = (unit or "KG").upper()

    # Weight conversions to KG
    if unit == "KG":
        return float(value)
    elif unit == "G":
        return float(value) / 1000
    elif unit == "LB":
        return float(value) * 0.453592
    elif unit == "OZ":
        return float(value) * 0.0283495

    # If it's not a weight unit, return None
    return None




def validate_logistics_vs_variants(logistics_data, variants_data):
    """
    Ensure logistics weight >= product/variant weight.
    Variants and logistics must be compared in kg.
    """
    # Case 1: Product-level logistics
    if logistics_data:
        logistics_weight = normalize_weight(
            logistics_data.get("total_weight"),
            logistics_data.get("weight_measurement", "KG")
        )

        for variant in variants_data:
            variant_weight = normalize_weight(
                variant.get("custom_size_value"),
                variant.get("custom_size_unit", "KG")
            )
            if variant_weight is not None and logistics_weight is not None:
                if variant_weight > logistics_weight:
                    raise serializers.ValidationError(
                        f"Variant '{variant.get('custom_size_unit')}' weight of ({variant_weight:.2f}kg) "
                        f"cannot exceed product logistics weight of ({logistics_weight:.2f}kg)."
                    )

    # Case 2: Variant-level logistics
    else:
        for variant in variants_data:
            logistics = variant.get("logistics")
            if not logistics:
                continue

            logistics_weight = normalize_weight(
                logistics.get("total_weight"),
                logistics.get("weight_measurement", "KG")
            )
            variant_weight = normalize_weight(
                variant.get("custom_size_value"),
                variant.get("custom_size_unit", "KG")
            )
            if variant_weight is not None and logistics_weight is not None:
                if variant_weight > logistics_weight:
                    raise serializers.ValidationError(
                        f"Variant '{variant.get('custom_size_unit')}' weight of ({variant_weight:.2f}kg) "
                        f"cannot exceed its logistics weight of ({logistics_weight:.2f}kg)."
                    )


def generate_list_for_category(category):
    """
    Generate a list of product Ids for a given category
    """
    qs = ProductIndex.objects.filter(is_published=True, category__iexact=category)

    trending = qs.annotate(
        avg_rating = Coalesce(Avg("product__rating"), Value(0.0))
    ).order_by("-avg_rating", "-created_at").values_list("id", flat=True)
    cache.set(f"products_trending_{category}", list(trending), REDIS_TTL)

    new_items = qs.order_by("-created_at").values_list("id", flat=True)
    cache.set(f"products_new_{category}", list(new_items), REDIS_TTL)

    random_ids = list(qs.values_list("id", flat=True))
    random.shuffle(random_ids)
    cache.set(f"products_random_{category}", random_ids, REDIS_TTL)


def regenerate_product_cache_lists():
    """
    Regenerate cacched product ID lists for trending, new, and random products
    """
    qs = ProductIndex.objects.filter(is_published=True)

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

    # category lists
    from django.conf import settings
    categories = list(settings.CATEGORIES.keys())
    for category in categories:
        generate_list_for_category(category)
