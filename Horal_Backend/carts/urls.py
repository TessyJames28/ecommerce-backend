from django.urls import path
from .views import CartView, CartItemUpdateDeleteView, CartItemCreateView


urlpatterns = [
    path('', CartView.as_view(), name='cart'),
    path('create/', CartItemCreateView.as_view(), name='create_cart'),
    path('item/<uuid:item_id>/', CartItemUpdateDeleteView.as_view(), name='cart_update_delete'),

]