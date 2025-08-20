from django.urls import path
from .views import MediaUploadView, MediaDeleteView, MediaListView, VendorMediaListView

urlpatterns = [
    path("upload/", MediaUploadView.as_view(), name="media-upload"),
    path("delete/<int:pk>/", MediaDeleteView.as_view(), name="media-delete"),
    path("list/", MediaListView.as_view(), name="media-list"),
    path("vendor/<str:vendor_id>/list/", VendorMediaListView.as_view(), name="vendor-media-list"),
]
