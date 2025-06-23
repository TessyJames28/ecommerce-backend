from django.urls import path
from . import views


urlpatterns = [
    # Product variant endpoint
    path('variants/<uuid:variant_id>/', views.ProductVariantView.as_view(), name='product-variant'),
    # Product endpoints
    path('', views.ProductListView.as_view(), name='product-list'),
    path('<str:category_name>/create/', views.ProductCreateView.as_view(), name='product-create'),
    # Product endpoint to retrieve, update, and delete products
    path('<str:category_name>/<uuid:pk>/', views.ProductDetailView.as_view(), name='product-detail'),
    # Single product detail view
    path('<uuid:pk>/', views.SingleProductDetailView.as_view(), name="single_product_view"),

]