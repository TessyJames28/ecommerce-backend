from favorites.models import Favorites, FavoriteItem

def merge_favorites_from_session_to_user(session_key, user):
    """
    Merge anonymous session-based favorite with
    auth user favorites. This will be called from product signal.py
    """
    if not session_key:
        return
    
    try:
        anon_favorites = Favorites.objects.filter(session_key=session_key).first()
    except Favorites.DoesNotExist:
        return
    
    user_favorites, _ = Favorites.objects.get_or_create(user=user)

    for item in anon_favorites.items.all():
        exists = FavoriteItem.objects.filter(
            favorites=user_favorites,
            product_index=item.product_index
        ).exists()
        
        if not exists:
            FavoriteItem.objects.create(
                favorites=user_favorites,
                product_index=item.product_index
            )


    # Clean merged data
    anon_favorites.delete()