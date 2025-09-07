from .models import Cart, CartItem


def merge_user_cart(session_key, user):
    """
    Function to merge anon user with auth user cart after login
    """
    if not session_key:
        return

    anonymous_cart = Cart.objects.filter(session_key=session_key).first()
    if not anonymous_cart:
        return
    user_cart, _ = Cart.objects.get_or_create(user=user)

    # avoid self merge
    if anonymous_cart.id  == user_cart.id:
        return
    for item in anonymous_cart.cart_item.all():
        existing_item = CartItem.objects.filter(
            cart=user_cart, variant=item.variant
        ).first()

        if existing_item:
            existing_item.quantity += item.quantity
            if existing_item.quantity > existing_item.variant.stock_quantity:
                existing_item.quantity = existing_item.variant.stock_quantity
            existing_item.save()
        else:
           item.cart = user_cart
           item.save()

    # clean up cart after merge
    anonymous_cart.delete() 
