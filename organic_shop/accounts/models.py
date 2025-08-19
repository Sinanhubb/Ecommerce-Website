from django.db import models
from django.contrib.auth.models import User
from shop.models import Product,ProductVariant
from django.utils import timezone

class Wishlist(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    variant = models.ForeignKey(ProductVariant, null=True, blank=True, on_delete=models.CASCADE)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'product', 'variant')  

    def __str__(self):
        if self.variant:
            return f"{self.user.username} - {self.variant}"
        return f"{self.user.username} - {self.product}"

    @property
    def display_price(self):
        """Returns the correct price depending on variant or product"""
        if self.variant:
            return self.variant.discount_price or self.variant.price
        return self.product.discount_price or self.product.price

    @property
    def original_price(self):
        """Returns the original price before discount"""
        if self.variant:
            return self.variant.price
        return self.product.price

    @property
    def has_discount(self):
        if self.variant:
            return bool(self.variant.discount_price)
        return bool(self.product.discount_price)

    @property
    def discount_percentage(self):
        if self.variant and self.variant.discount_price:
            return int(100 - (self.variant.discount_price / self.variant.price * 100))
        elif self.product and self.product.discount_price:
            return int(100 - (self.product.discount_price / self.product.price * 100))
        return 0


class Address(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='addresses')
    full_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20)
    address_line = models.TextField()
    city = models.CharField(max_length=50)
    postal_code = models.CharField(max_length=10)
    state=models.CharField(max_length=50)
    country = models.CharField(max_length=50)
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.full_name}, {self.city}, {self.country}"



class PromoCode(models.Model):
    code = models.CharField(max_length=20, unique=True)
    discount_percentage = models.PositiveIntegerField(default=0)
    active = models.BooleanField(default=True)
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField(null=True, blank=True)
    usage_limit = models.PositiveIntegerField(default=1)  # max number of users

    def __str__(self):
        return self.code



class Order(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('shipped', 'Shipped'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
    ]
    PAYMENT_CHOICES = [
        ('COD', 'Cash on Delivery'),
        ('ONLINE', 'Online Payment'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    address = models.ForeignKey(Address, on_delete=models.SET_NULL, null=True)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    promo_code = models.ForeignKey(PromoCode, on_delete=models.SET_NULL, null=True, blank=True)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_CHOICES, default='COD')
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    is_paid = models.BooleanField(default=False)

    def __str__(self):
        return f"Order #{self.id} - {self.user.username}"


# Order Item
class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
    variant = models.ForeignKey(ProductVariant, on_delete=models.SET_NULL, null=True, blank=True)
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.quantity} x {self.product.name if self.product else 'Deleted Product'}"

    @property
    def total(self):
        return self.price * self.quantity
