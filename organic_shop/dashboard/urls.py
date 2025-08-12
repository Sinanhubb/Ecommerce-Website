
from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.dashboard_home, name='dashboard_home'),
    path('product/add/', views.product_add, name='product_add'),
    path('product/<int:pk>/edit/', views.product_edit, name='product_edit'),
    path('product/<int:pk>/delete/', views.product_delete, name='product_delete'),

    # Variant CRUD
    path('variant/add/', views.variant_add, name='variant_add'),
    path('variant/<int:pk>/edit/', views.variant_edit, name='variant_edit'),
    path('variant/<int:pk>/delete/', views.variant_delete, name='variant_delete'),
]

