from django.urls import path
from .views import (
    AllUserProfileView, GetUserProfileView,
)


urlpatterns = [
    path("", GetUserProfileView.as_view(), name="user-profile-detail"),
    path("all/", AllUserProfileView.as_view(), name="All-user-profile"),
]