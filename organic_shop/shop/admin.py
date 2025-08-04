from django.contrib import admin
from .models import Category, Product, ProductImage, Cart, CartItem,VariantValue,VariantOption,ProductVariant

class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'price', 'is_featured','stock', 'sold_count', 'views', 'created_at']
    list_filter = ['is_featured', 'category']
    list_editable = ['price', 'is_featured','stock']
    prepopulated_fields = {'slug': ('name',)}
    inlines = [ProductImageInline]

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}

@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ['user', 'created_at', 'updated_at']
    readonly_fields = ['created_at', 'updated_at']

@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ['cart', 'product', 'quantity']


admin.site.register(ProductVariant)
admin.site.register(VariantOption)
admin.site.register(VariantValue)
