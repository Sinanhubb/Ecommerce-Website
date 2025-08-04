from django.contrib import admin
from .models import Order, OrderItem,Address,PromoCode

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
