from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.utils.timezone import now
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
    HealthAndBeautyProductSerializer, AccessoryProductSerializer
) 
from django.db import connection
from django.utils.timezone import now


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
                o.status IN ('paid', 'shipped', 'delivered')
                AND o.created_at >= %s
            GROUP BY
                pi.id
            ORDER BY
                total_quantity_sold DESC
            LIMIT 90;

        """, [from_date])
        
        # Get column names for dictionary output
        # print(f"db data: {cursor.fetchall()}")
        rows = cursor.fetchall()  # ✅ fetch once
        columns = [col[0] for col in cursor.description]
        raw_data = [dict(zip(columns, row)) for row in rows]

    return raw_data