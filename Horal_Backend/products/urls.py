from django.urls import path
from . import views


urlpatterns = [
    # Category endpoints
    path('categories/create/', views.CategoryCreateView.as_view(), name='category-create'),
    path('categories/', views.CategoryListView.as_view(), name='category-list'),
    path('categories/<uuid:pk>/', views.CategoryDetailView.as_view(), name='category-detail'),
    path('categories/<uuid:pk>/view/', views.SingleCategoryDetailView.as_view(), name='single_category-detail'),

    # Product variant endpoint
    path('variants/<uuid:variant_id>/', views.ProductVariantView.as_view(), name='product-variant'),

    # Sub categories endpoint
    path('subcategory/create/', views.SubCategoryCreateView.as_view(), name="create-subcategory"),

    # GET Endpoint
    path('subcategory/<uuid:category_id>/view/', views.SubCategoryListView.as_view(), name="get-subcategory"),

    # PUT and DELETE endpoints
    path('subcategory/<uuid:category_id>/', views.SubCategoryDetailView.as_view(), name="subcategory-endpoints"),

    # Product endpoints
    path('', views.ProductListView.as_view(), name='product-list'),
    path('<str:category_name>/create/', views.ProductCreateView.as_view(), name='product-create'),
    # Product endpoint to retrieve, update, and delete products
    path('<str:category_name>/<uuid:pk>/', views.ProductDetailView.as_view(), name='product-detail'),
    # Single product detail view
    path('<str:category_name>/<uuid:pk>/product/', views.SingleProductDetailView.as_view(), name="single_product_view"),
    
    # Shop products endpoints
    path('shop/<uuid:shop_id>/get-products/', views.ShopProductListView.as_view(), name='shop-products'),

]