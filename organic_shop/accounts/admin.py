from django.contrib import admin
from .models import Order, OrderItem,Address,PromoCode,Wishlist

class OrderItemInline(admin.TabularInline):  
    model = OrderItem
    extra = 0  # Don’t show empty rows
    readonly_fields = ['product', 'quantity', 'price']
    can_delete = False

class OrderAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'total_price', 'status', 'created_at']
    inlines = [OrderItemInline] 
    list_editable = ['status']
    list_filter = ['status', 'created_at']
    search_fields = ['user__username', 'id']

admin.site.register(Order, OrderAdmin)
admin.site.register(Address)
admin.site.register(PromoCode)

@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'product', 'variant', 'added_at')
    list_filter = ('user',)
    search_fields = ('product__name',)
