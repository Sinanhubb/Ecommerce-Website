from django.urls import path
from . import views
from django.contrib.auth.views import LogoutView

app_name = 'accounts'

urlpatterns = [
    path('register/', views.register_view, name='register'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    path('profile/', views.profile_view, name='profile'),
    path('profile/edit/', views.edit_profile_view, name='edit_profile'),
    path('wishlist/', views.wishlist_view, name='wishlist'),
    path('wishlist/add/<int:product_id>/', views.add_to_wishlist, name='add_to_wishlist'),
    path('wishlist/remove/<int:item_id>/', views.remove_from_wishlist, name='remove_from_wishlist'),
    path('direct-checkout/<int:pk>/', views.direct_checkout, name='direct_checkout'),
    path('checkout/', views.checkout, name='checkout'),
    path('address/add/', views.add_address, name='add_address'),
    path('address/edit/<int:address_id>/', views.edit_address, name='edit_address'),
    path('order-summary/<int:order_id>/', views.order_summary, name='order_summary'),
    path('place-order/<int:order_id>/', views.place_order, name='place_order'),
    path('orders/', views.my_orders_view, name='my_orders'),
    path('orders/<int:order_id>/', views.order_detail_view, name='order_detail'),
    path('orders/<int:order_id>/tracking/', views.order_tracking_view, name='order_tracking'),
    path('address/delete/<int:pk>/', views.delete_address, name='delete_address'),







]