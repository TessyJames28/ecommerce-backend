from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response

from .models import (
    Category, Shop, BabyProduct, VehicleProduct, GadgetProduct,
    FashionProduct, ElectronicsProduct, AccessoryProduct,
    HealthAndBeautyProduct, FoodProduct
)
from .serializers import (
    BabyProductSerializer, VehicleProductSerializer, GadgetProductSerializer,
    FashionProductSerializer, ElectronicsProductSerializer, FoodProductSerializer,
    HealthAndBeautyProductSerializer, AccessoryProductSerializer
) 


# List of all product models and their serializers
product_models = [
    (BabyProduct, BabyProductSerializer, 'babies'),
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
        print("get response called")
        response_data = {
            "status": "success" if status_code < 400 else "error",
            "status_code": status_code,
            "message": message
        }

        if data is not None:
            response_data["data"] = data
        print("get response 2nd call")
        return Response(response_data, status=status_code)
    

    def get_product_model_by_category(self, category_name):
        """Get the product model based on category name"""
        mapping = {
            'babies': BabyProduct,
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