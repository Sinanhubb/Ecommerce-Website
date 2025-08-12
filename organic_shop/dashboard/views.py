from django.shortcuts import render, get_object_or_404, redirect
from .forms import ProductForm, ProductVariantForm
from shop.models import Product, ProductVariant, Category

def dashboard_home(request):
    products = Product.objects.all()
    variants = ProductVariant.objects.all()
    categories = Category.objects.all()
    
    return render(request, 'dashboard/home.html', {
        'products': products,
        'categories': categories,
        'variants': variants,
    })

def product_add(request):
    if request.method == "POST":
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('dashboard:dashboard_home')
    else:
        form = ProductForm()
    return render(request, 'dashboard/product_form.html', {'form': form, 'title': 'Add Product'})

# EDIT PRODUCT
def product_edit(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == "POST":
        form = ProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            form.save()
            return redirect('dashboard:dashboard_home')
    else:
        form = ProductForm(instance=product)
    return render(request, 'dashboard/product_form.html', {'form': form, 'title': 'Edit Product'})

# DELETE PRODUCT
def product_delete(request, pk):
    product = get_object_or_404(Product, pk=pk)
    product.delete()
    return redirect('dashboard:dashboard_home')

# ADD VARIANT
def variant_add(request):
    if request.method == "POST":
        form = ProductVariantForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('dashboard:dashboard_home')
    else:
        form = ProductVariantForm()
    return render(request, 'dashboard/variant_form.html', {'form': form, 'title': 'Add Variant'})

# EDIT VARIANT
def variant_edit(request, pk):
    variant = get_object_or_404(ProductVariant, pk=pk)
    if request.method == "POST":
        form = ProductVariantForm(request.POST, instance=variant)
        if form.is_valid():
            form.save()
            return redirect('dashboard:dashboard_home')
    else:
        form = ProductVariantForm(instance=variant)
    return render(request, 'dashboard/variant_form.html', {'form': form, 'title': 'Edit Variant'})

# DELETE VARIANT
def variant_delete(request, pk):
    variant = get_object_or_404(ProductVariant, pk=pk)
    variant.delete()
    return redirect('dashboard:dashboard_home')
