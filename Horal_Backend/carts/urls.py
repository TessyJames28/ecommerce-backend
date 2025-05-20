from django.urls import path
from .views import (
    CartView, CartItemUpdateDeleteView, 
    CartItemCreateView, MergeCartView,
    CartDeleteView
)


urlpatterns = [
    path('', CartView.as_view(), name='cart'),
    path('add/', CartItemCreateView.as_view(), name='add-to-cart'),
    path('item/<uuid:item_id>/', CartItemUpdateDeleteView.as_view(), name='cart-item-update-delete'),
    path('merge/', MergeCartView.as_view(), name='merge-cart'),
    path('<uuid:cart_id>/', CartDeleteView.as_view(), name="delete-cart"),

]