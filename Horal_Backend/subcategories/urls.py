from django.urls import path
from .views import (
    SubCategoryCreateView, SubCategoryListView,
    SubCategoryDetailView, SingleSubcategoryListView
)

urlpatterns = [
     # Sub categories endpoint
    path('create/', SubCategoryCreateView.as_view(), name="create-subcategory"),

    # GET Endpoint
    path('<uuid:category_id>/view/', SubCategoryListView.as_view(), name="get_subcategory"),

    # PUT and DELETE endpoints
    path('<uuid:subcategory_id>/', SubCategoryDetailView.as_view(), name="subcategory_endpoints"),

    # View single subcategory
    path('view/<uuid:subcategory_id>/', SingleSubcategoryListView.as_view(), name="single_subcategory"),
]