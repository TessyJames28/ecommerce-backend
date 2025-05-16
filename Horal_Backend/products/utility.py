from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response

from .models import (
    ChildrenProduct, VehicleProduct, GadgetProduct,
    FashionProduct, ElectronicsProduct, AccessoryProduct,
    HealthAndBeautyProduct, FoodProduct
)
from .serializers import (
    ChildrenProductSerializer, VehicleProductSerializer, GadgetProductSerializer,
    FashionProductSerializer, ElectronicsProductSerializer, FoodProductSerializer,
    HealthAndBeautyProductSerializer, AccessoryProductSerializer
) 


# List of all product models and their serializers
product_models = [
    (ChildrenProduct, ChildrenProductSerializer, 'babies'),
    (VehicleProduct, VehicleProductSerializer, 'vehicles'),
    (GadgetProduct, GadgetProductSerializer, 'gadget'),
    (FashionProduct, FashionProductSerializer, 'fashion'),
    (ElectronicsProduct, ElectronicsProductSerializer, 'electronics'),
    (AccessoryProduct, AccessoryProductSerializer, 'accessories'),
    (HealthAndBeautyProduct, HealthAndBeautyProductSerializer, 'health and beauty'),
    (FoodProduct, FoodProductSerializer, 'foods')
]

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
