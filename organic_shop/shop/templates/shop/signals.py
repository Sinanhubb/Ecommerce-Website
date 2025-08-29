# shop/signals.py
from django.db.models.signals import post_save
from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from .models import Category, Cart

@receiver(post_save, sender=Category)
def update_products_on_category_change(sender, instance, **kwargs):
    """
    When a Category is activated/deactivated,
    update all its products accordingly.
    """
    if instance.is_active:
        instance.products.update(is_active=True)
    else:
        instance.products.update(is_active=False)


@receiver(user_logged_in)
def merge_session_cart_on_login(sender, request, user, **kwargs):
    """
    Listens for the user_logged_in signal and merges the anonymous
    session cart with the user's permanent cart.
    """
    try:
        # Find the anonymous cart associated with the user's session
        anon_cart = Cart.objects.get(session_key=request.session.session_key, user__isnull=True)
    except Cart.DoesNotExist:
        # If no anonymous cart exists, there's nothing to do.
        return

    try:
        # Find the user's permanent cart
        user_cart = Cart.objects.get(user=user)
    except Cart.DoesNotExist:
        # If the user doesn't have a cart, simply assign the anonymous one to them.
        anon_cart.user = user
        anon_cart.session_key = None # Clear the session key
        anon_cart.save()
        return

    # If both carts exist, merge the items
    for item in anon_cart.items.all():
        existing_item, created = user_cart.items.get_or_create(
            product=item.product,
            variant=item.variant,
            defaults={'quantity': item.quantity}
        )
        if not created:
            # If it already exists, add the quantities together
            existing_item.quantity += item.quantity
            existing_item.save()
    
    # After merging, delete the now-empty anonymous cart
    anon_cart.delete()