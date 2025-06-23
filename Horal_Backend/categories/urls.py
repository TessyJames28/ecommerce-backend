from django.urls import path
from .views import (
    CategoryCreateView, CategoryDetailView,
    CategoryListView, SingleCategoryDetailView
)

urlpatterns = [
     # Category endpoints
    path('create/', CategoryCreateView.as_view(), name='category-create'),
    path('', CategoryListView.as_view(), name='category-list'),
    path('<uuid:pk>/', CategoryDetailView.as_view(), name='category-detail'),
    path('<uuid:pk>/view/', SingleCategoryDetailView.as_view(), name='single_category-detail'),
]