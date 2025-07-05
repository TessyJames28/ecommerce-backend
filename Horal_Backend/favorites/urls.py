from django.urls import path
from .views import (
    FavoritesView, AddToFavoritesView,
    RemoveFromFavoritesView,
    CheckFavoriteStatusView
)

app_name = 'favorites'


urlpatterns = [
    path('', FavoritesView.as_view(), name="favorite-list"),
    path('add/', AddToFavoritesView.as_view(), name="add-to-favorites"),
    path('<uuid:item_id>/', RemoveFromFavoritesView.as_view(), name='remove-from-favorites'),
    path('check/', CheckFavoriteStatusView.as_view(), name="check-favorite-status"),

]