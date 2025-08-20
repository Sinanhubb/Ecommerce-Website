# shop/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Category

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
