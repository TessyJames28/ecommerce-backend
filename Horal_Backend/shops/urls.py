from django.urls import path
from .views import (
   ShopManagementView, CreateShop, ShopProductListView,
   ShopDeleteView
)

urlpatterns = [
    # Shop management (superadmin only)
    path('', ShopManagementView.as_view(), name='shop-list'),
    path('create/', CreateShop.as_view(), name="create-shop"),
    # superadmin can delete the shop
    path('<uuid:pk>/', ShopDeleteView.as_view(), name='shop-detail'),
    # Shop products endpoints
    path('<uuid:shop_id>/products/', ShopProductListView.as_view(), name='shop-products'),
]