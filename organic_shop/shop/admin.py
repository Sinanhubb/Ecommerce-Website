from django.contrib import admin
from .models import (
    Category,
    Product,
    ProductImage,
    Cart,
    CartItem,
    VariantValue,
    VariantOption,
    ProductVariant
)

# Inline for multiple images in Product
class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'price', 'is_featured', 'stock', 'sold_count', 'views', 'created_at']
    list_filter = ['is_featured', 'category']
    list_editable = ['price', 'is_featured', 'stock']
    prepopulated_fields = {'slug': ('name',)}
    inlines = [ProductImageInline]

    def get_readonly_fields(self, request, obj=None):
        """
        If the product has variants, make the stock field read-only.
        This avoids duplicate/confusing stock entries.
        """
        if obj and obj.variants.exists():
            return self.readonly_fields + ['stock']
        return self.readonly_fields


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
    list_display = ['cart', 'product', 'variant', 'quantity']


@admin.register(VariantOption)
class VariantOptionAdmin(admin.ModelAdmin):
    list_display = ['name']


@admin.register(VariantValue)
class VariantValueAdmin(admin.ModelAdmin):
    list_display = ['option', 'value']


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = ['product', 'sku', 'price', 'stock']
    filter_horizontal = ['values']
    readonly_fields = ['sku']
