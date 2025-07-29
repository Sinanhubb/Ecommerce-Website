from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse


from django.db import models

class Category(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    image = models.ImageField(upload_to='categories/')

    class Meta:
        verbose_name_plural = "Categories"


    def __str__(self):
        return self.name

class Product(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products')
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    discount_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    image = models.ImageField(upload_to='products/')
    is_featured = models.BooleanField(default=False)  
    sold_count = models.PositiveIntegerField(default=0)  
    created_at = models.DateTimeField(auto_now_add=True)  
    views = models.PositiveIntegerField(default=0)  
    available = models.BooleanField(default=True)

    def __str__(self):
        return self.name

   
    def get_absolute_url(self):
        return reverse('shop:product_detail', kwargs={'slug': self.slug})

   
    @property
    def get_discount_percentage(self):
        if self.discount_price:
            return int(100 - (self.discount_price / self.price * 100))
        return 0


class ProductImage(models.Model):
    product = models.ForeignKey(Product, related_name='images', on_delete=models.CASCADE)
    image = models.ImageField(upload_to='products/')


class Cart(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    session_key = models.CharField(max_length=40, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def total_price(self):
        return sum(item.total_price for item in self.items.all())


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    @property
    def total_price(self):
        if self.product.discount_price:
            return self.product.discount_price * self.quantity
        return self.product.price * self.quantity
