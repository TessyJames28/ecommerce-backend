from django.shortcuts import get_object_or_404
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from .models import Shop
from .serializers import ShopSerializer
from products.utils import (
    IsSuperAdminPermission, BaseResponseMixin,
    product_models, StandardResultsSetPagination,
    get_product_queryset
)
from users.authentication import CookieTokenAuthentication
from products.serializers import ProductIndexSerializer
from products.models import ProductIndex
# Create your views here.

class CreateShop(GenericAPIView):
    """
    API endpoints for the superadmins to create shop
    To use and create platform base products for sale.
    """
    serializer_class = ShopSerializer
    queryset = Shop.objects.all()
    permission_classes = [IsSuperAdminPermission]
    authentication_classes = [CookieTokenAuthentication]

    def post(self, request, *args, **kwargs):
        """
        A post method to create a shop by the superuser
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        response_data = {
            "status": "success",
            "status_code": status.HTTP_201_CREATED,
            "message": "Successfully created shop",
            "data": {
                "id": str(user.id),
                "owner_type": user.owner_type,
                "owner": user.owner,
                "name": user.name,
                "created_by_admin": user.created_by_admin,
                "location": user.location
            }
        }

        return Response(response_data, status=status.HTTP_201_CREATED)


class ShopManagementView(GenericAPIView, BaseResponseMixin):
    """
    API endpoints for superadmins to manage shops
    """
    serializer_class = ShopSerializer
    queryset = Shop.objects.all()
    permission_classes = [IsSuperAdminPermission]
    authentication_classes = [CookieTokenAuthentication]


    def get(self, request, *args, **kwargs):
        """Get all shops"""
        shops = self.get_queryset()
        serializer = self.get_serializer(shops, many=True)
        return self.get_response(
            status.HTTP_200_OK,
            "ALL shops retrieved successfully",
            serializer.data
        )
    

class ShopDeleteView(GenericAPIView, BaseResponseMixin):
    """
    API endpoints for superadmins to manage shops deletion
    """
    serializer_class = ShopSerializer
    queryset = Shop.objects.all()
    permission_classes = [IsSuperAdminPermission]
    authentication_classes = [CookieTokenAuthentication]

    def delete(self, request, pk, *args,**kwargs):
        """Delete a shop and all its products"""
        shop = get_object_or_404(Shop, pk=pk)
        shop.delete() # This will cascade delete all products belonging to the shop
        return Response({
            "status": "success",
            "status_code": status.HTTP_204_NO_CONTENT,
            "message": "Shop deleted successfully with all its products"
        })
    

class ShopProductListView(GenericAPIView, BaseResponseMixin):
    """
    API endpoint to list all products of a shop
    """ 
    permission_classes = [AllowAny]
    authentication_classes = []
    pagination_class = StandardResultsSetPagination
    serializer_class = ProductIndexSerializer

    def get_queryset(self):
        """Get all indexed products of a shop"""
        shop_id = self.kwargs.get("shop_id")
        return ProductIndex.objects.filter(shop_id=shop_id)

    def get(self, request, shop_id, *args, **kwargs):
        """Get all products of a shop"""
        queryset = self.get_queryset()
        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page, many=True)

        if page is not None:
            paginated_response = self.get_paginated_response(serializer.data)
            paginated_response.data["status"] = "success"
            paginated_response.data["status_code"] = status.HTTP_200_OK
            paginated_response.data["message"] = "Shop products retrieved successfully"
        
        return paginated_response