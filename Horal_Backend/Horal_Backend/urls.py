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
    permission_classes=[permissions.AllowAny],
    authentication_classes=[],
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/user/', include('users.urls')),
    path('api/v1/seller/', include('sellers.urls')),
    path('api/v1/product/', include('products.urls')),
    path('api/v1/cart/', include('carts.urls')),
    path('api/v1/order/', include('orders.urls')),

    # Optional: Redirect root to Swagger
    path('', lambda request: redirect('schema-swagger-ui')),
]

# Swagger + Redoc views: FORCE no auth
urlpatterns += [
    re_path(
        r'^swagger(?P<format>\.json|\.yaml)$',
        schema_view.without_ui(cache_timeout=0),
        {'permission_classes': [permissions.AllowAny], 'authentication_classes': []},
        name='schema-json'
    ),
    path(
        'swagger/',
        schema_view.with_ui('swagger', cache_timeout=0),
        {'permission_classes': [permissions.AllowAny], 'authentication_classes': []},
        name='schema-swagger-ui'
    ),
    path(
        'redoc/',
        schema_view.with_ui('redoc', cache_timeout=0),
        {'permission_classes': [permissions.AllowAny], 'authentication_classes': []},
        name='schema-redoc'
    ),
]
