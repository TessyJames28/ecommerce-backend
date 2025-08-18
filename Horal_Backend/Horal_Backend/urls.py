"""
URL configuration for Horal_Backend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include, re_path
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from django.shortcuts import redirect

# Swagger API configuration
schema_view = get_schema_view(
    openapi.Info(
        title="Horal Backend API",
        default_version="v1",
        description="API documentation for Horal backend with django framework",
        terms_of_service="http://127.0.0.1:8000/terms/",
        contact=openapi.Contact(email="tessyjames28@gmail.com"),
        license=openapi.License(name="BSD License"),
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
    url="https://api.horal.ng/api/v1",
    # url="https://horal-backend.up.railway.app/api/v1",
)


urlpatterns = [
    path('admin/', admin.site.urls),

    #swagger
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),

    # Add this for JSON schema (OpenAPI spec)
    path('swagger.json', schema_view.without_ui(cache_timeout=0), name='schema-json'),

    #App URL
    path('api/v1/user/', include('users.urls')),
    path('api/v1/seller/', include('sellers.urls')),
    path('api/v1/product/', include('products.urls')),
    path('api/v1/cart/', include('carts.urls')),
    path('api/v1/order/', include('orders.urls')),
    path('api/v1/favorite/', include('favorites.urls')),
    path('api/v1/category/', include('categories.urls')),
    path('api/v1/shop/', include('shops.urls')),
    path('api/v1/subcategory/', include('subcategories.urls')),
    path('api/v1/rating/', include('ratings.urls')),
    path('api/v1/profile/', include('user_profile.urls')),
    path('api/v1/payment/', include('payment.urls')),
    path('api/v1/dashboard/seller/', include('sellers_dashboard.urls')),
    path('api/v1/dashboard/seller/wallet/', include('wallet.urls')),
    # Optional: Redirect from root to Swagger UI
]