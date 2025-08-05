from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static

app_name = 'shop'

urlpatterns = [
    path('', views.index, name='index'),
    path('category/<slug:slug>/', views.category_detail, name='category_detail'),
    path('product/<slug:slug>/', views.product_detail, name='product_detail'),
    path('cart/', views.cart_detail, name='cart_detail'),
    path('cart/add/<int:product_id>/', views.cart_add, name='cart_add'),
    path('cart/remove/<int:item_id>/', views.cart_remove, name='cart_remove'),
    path('get-matching-variant/', views.get_matching_variant, name='get_matching_variant'),  
    path('cart/update/<int:item_id>/', views.update_cart_item, name='update_cart_item'),
    path('ajax/search/', views.ajax_search, name='ajax_search'),
    path('remove-from-cart/<int:item_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('cart/update-ajax/', views.update_cart_item_ajax, name='update_cart_item_ajax'),
    path('buy-now/<int:product_id>/', views.buy_now, name='buy_now'),
 
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)