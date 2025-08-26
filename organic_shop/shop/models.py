from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.text import slugify
import shortuuid
from django.db.models import Sum, Min


class Category(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, blank=True)
    image = models.ImageField(upload_to='categories/')
    is_active = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
       
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
           
            while Category.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs) 

    class Meta:
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.name

class Product(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products')
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True ,blank=True) 
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    discount_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    image = models.ImageField(upload_to='products/')
    is_featured = models.BooleanField(default=False)  
    sold_count = models.PositiveIntegerField(default=0)  
    created_at = models.DateTimeField(auto_now_add=True)  
    views = models.PositiveIntegerField(default=1)  
    available = models.BooleanField(default=True)
    stock = models.PositiveIntegerField(default=0)

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            query = Product.objects.filter(slug=base_slug)
            if self.pk:
                query = query.exclude(pk=self.pk)
            
            if query.exists():
                self.slug = f"{base_slug}-{shortuuid.uuid()[:8]}"
            else:
                self.slug = base_slug
        super().save(*args, **kwargs)


    @property
    def total_stock(self):
        if self.has_variants:
            return self.variants.aggregate(total=Sum('stock'))['total'] or 0
        return self.stock
    @property
    def has_variants(self):
        
        return self.variants.exists()
    @property
    def is_active(self):
        return self.available

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('shop:product_detail', kwargs={'slug': self.slug})

    @property
    def get_discount_percentage(self):
        if self.discount_price:
            return int(100 - (self.discount_price / self.price * 100))
        return 0
    def get_default_variant(self):
    
        if self.has_variants:
            return self.variants.order_by('-stock').first()
        return None
    def get_min_price(self):
        """Returns the minimum price among all variants"""
        if self.has_variants:
            return self.variants.aggregate(models.Min('price'))['price__min']
        return self.price

    def get_min_discount_price(self):
        """Returns the minimum discount price among all variants"""
        if self.has_variants:
            return self.variants.aggregate(models.Min('discount_price'))['discount_price__min']
        return self.discount_price
    
    @property
    def display_price(self):
        """Returns the effective price to display (uses variant prices if they exist)"""
        if self.has_variants:
            return None  
        return self.discount_price or self.price

    @property
    def display_discount(self):
        """Returns discount percentage if applicable (only for non-variant products)"""
        if self.has_variants or not self.discount_price:
            return None
        return self.get_discount_percentage


class ProductImage(models.Model):
    product = models.ForeignKey(Product, related_name='images', on_delete=models.CASCADE)
    image = models.ImageField(upload_to='products/')

class VariantOption(models.Model):
    name = models.CharField(max_length=50)

    def __str__(self):
        return self.name

class VariantValue(models.Model):
    option = models.ForeignKey(VariantOption, on_delete=models.CASCADE)
    value = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.option.name}: {self.value}"

class ProductVariant(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')
    values = models.ManyToManyField(VariantValue)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    discount_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    stock = models.IntegerField()
    sku = models.CharField(max_length=50, unique=True, blank=True)
    image = models.ImageField(upload_to='variants/', null=True, blank=True)
    sold_count = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.product.name} - {', '.join(v.value for v in self.values.all())}"

    def generate_sku(self):
        base = self.product.name[:3].upper()
        variant_parts = sorted([v.value[:3].upper() for v in self.values.all()])
        sku_base = f"{base}-{'-'.join(variant_parts)}"
        
        counter = 1
        sku = sku_base
        while ProductVariant.objects.filter(sku=sku).exclude(id=self.id).exists():
            sku = f"{sku_base}-{counter}"
            counter += 1
        return sku

   
    def save(self, *args, **kwargs):
        with transaction.atomic():
            if self._state.adding:
                super().save(*args, **kwargs)

            if not self.sku:
                self.sku = self.generate_sku()
            
            super().save(*args, **kwargs)

    @property
    def get_discount_percentage(self):
        if self.discount_price:
            return int(100 - (self.discount_price / self.price * 100))
        return 0
class Cart(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    session_key = models.CharField(max_length=40, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def total_price(self):
        return sum(item.total_price for item in self.items.all())

    @property
    def total_savings(self):
        return sum(item.savings for item in self.items.all())

class CartItem(models.Model):
    cart = models.ForeignKey(Cart, related_name='items', on_delete=models.CASCADE)
    variant = models.ForeignKey(ProductVariant, null=True, blank=True, on_delete=models.SET_NULL)
    product = models.ForeignKey(Product, null=True, blank=True, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    def clean(self):
        if not self.product and not self.variant:
            raise ValidationError("Cart item must have either a product or variant")
        if self.product and self.variant:
            raise ValidationError("Cart item can't have both product and variant")
        
    @property
    def available_stock(self):
        
        if self.variant:
            return self.variant.stock
        return self.product.stock


    @property
    def total_price(self):
        if self.variant:
            if self.variant.discount_price:
                return self.variant.discount_price * self.quantity
            return self.variant.price * self.quantity
        elif self.product.discount_price:
            return self.product.discount_price * self.quantity
        return self.product.price * self.quantity


    @property
    def savings(self):
        if self.variant:
            if self.variant.discount_price:
                return (self.variant.price - self.variant.discount_price) * self.quantity
            elif self.product.discount_price:
                return (self.product.price - self.product.discount_price) * self.quantity
            return 0
        elif self.product.discount_price:
            return (self.product.price - self.product.discount_price) * self.quantity
        return 0


    @property
    def get_product(self):
        return self.variant.product if self.variant else self.product

    def __str__(self):
        name = self.variant if self.variant else self.product
        return f"{name} x {self.quantity}"

class Review(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    rating = models.PositiveSmallIntegerField(choices=[(i, i) for i in range(1, 6)])
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.rating}⭐"