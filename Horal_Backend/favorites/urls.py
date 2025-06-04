from django.urls import path
from .views import (
    FavoritesView, AddToFavoritesView,
    MergeFavoritesView, RemoveFromFavoritesView,
    CheckFavoriteStatusView
)

app_name = 'favorites'


urlpatterns = [
    path('', FavoritesView.as_view(), name="favorite-list"),
    path('add/', AddToFavoritesView.as_view(), name="add-to-favorites"),
    path('remove/<uuid:item_id>/', RemoveFromFavoritesView.as_view(), name='remove-from-favorites'),
    path('check/', CheckFavoriteStatusView.as_view(), name="check-favorite-status"),
    path('merge/', MergeFavoritesView.as_view(), name="merge-favorites"),

]