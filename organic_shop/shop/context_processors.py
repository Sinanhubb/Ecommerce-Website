# shop/context_processors.py

from accounts.models import Wishlist

def wishlist_context(request):
    """
    Makes the wishlist item count available globally in all templates.
    """
    wishlist_count = 0
    if request.user.is_authenticated:
        wishlist_count = Wishlist.objects.filter(user=request.user).count()
    return {'wishlist_items_count': wishlist_count}