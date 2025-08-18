
from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path("", views.dashboard_home, name="dashboard_home"),

   
    path("product/add/", views.product_form, name="product_add"),
    path("product/<int:pk>/edit/", views.product_form, name="product_edit"),
    path("product/<int:pk>/delete/", views.product_delete, name="product_delete"),

    
    path("variant/add/", views.variant_form, name="variant_add"),
    path("variant/<int:pk>/edit/", views.variant_form, name="variant_edit"),
    path("variant/<int:pk>/delete/", views.variant_delete, name="variant_delete"),

    path("orders/", views.order_list, name="order_list"),
    path("orders/<int:order_id>/", views.order_detail, name="order_detail"),
    path("orders/<int:order_id>/edit/", views.order_edit, name="order_edit"),
    path("orders/<int:order_id>/delete/", views.order_delete, name="order_delete"),
]