
from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path("", views.dashboard_home, name="dashboard_home"),

    path('products/', views.product_list, name='product_list'),
    path("product/add/", views.product_form, name="product_add"),
    path("product/<int:pk>/edit/", views.product_form, name="product_edit"),
    path("product/<int:pk>/delete/", views.product_delete, name="product_delete"),

   path('variant/', views.variant_list, name='variant_list'),
path("variant/add/", views.variant_form, name="variant_add"),
path("variant/<int:pk>/edit/", views.variant_form, name="variant_edit"),
path("variant/<int:pk>/delete/", views.variant_delete, name="variant_delete"),

    path("orders/", views.order_list, name="order_list"),
    path("orders/<int:order_id>/", views.order_detail, name="order_detail"),
    path("orders/<int:order_id>/edit/", views.order_edit, name="order_edit"),
    path("orders/<int:order_id>/delete/", views.order_delete, name="order_delete"),


    path("promocode/", views.promocode_list, name="promocode_list"),
    path("promocode/add/", views.promocode_form, name="promocode_add"),
    path("promocode/edit/<int:pk>/", views.promocode_form, name="promocode_edit"),
    path("promocode/delete/<int:pk>/", views.promocode_delete, name="promocode_delete"),


    path('reviews/', views.review_list, name='review_list'),
    path('reviews/add/', views.review_form, name='review_add'),
    path('reviews/<int:pk>/edit/', views.review_form, name='review_edit'),
    path('reviews/<int:pk>/delete/', views.review_delete, name='review_delete'),


    path("categories/", views.category_list, name="category_list"),
    path("categories/add/", views.category_form, name="category_add"),
    path("categories/<int:pk>/edit/", views.category_form, name="category_edit"),
    path("categories/<int:pk>/delete/", views.category_delete, name="category_delete"),

    path('customers/', views.customer_list, name="customer_list"),
]