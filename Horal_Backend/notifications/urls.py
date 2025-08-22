from django.urls import path
from .views import (
    NotificationDetailView,
    NotificationListView,
    SupportCreateView,
    MarkAsReadView
)


urlpatterns = [
    path("notifications/", NotificationListView.as_view(), name="list-create-notification"),
    path("notifications/<uuid:pk>/", NotificationDetailView.as_view(), name="notification-detail"),
    path("support/create/", SupportCreateView.as_view(), name="support-create"),
    path("mark-as-read/<uuid:pk>/", MarkAsReadView.as_view(), name="mark_as_read"),

]