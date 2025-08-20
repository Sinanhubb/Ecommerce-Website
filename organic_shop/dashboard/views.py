from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator
from django.contrib.admin.views.decorators import staff_member_required
from .forms import ProductForm, ProductVariantForm, OrderForm, PromoCodeForm,ReviewForm
from shop.models import Product, ProductVariant, Category,Review
from accounts.models import Order, OrderItem, PromoCode, Address
from django.contrib.auth.models import User

# -------------------------
# Dashboard Home
# -------------------------
def dashboard_home(request):
    query = request.GET.get("q")
    product_list = Product.objects.all().order_by("-id")

    if query:
        product_list = product_list.filter(name__icontains=query)

    paginator = Paginator(product_list, 10)
    page_number = request.GET.get("page")
    products = paginator.get_page(page_number)

    latest_product = Product.objects.order_by("-id").first()
    orders = Order.objects.all().order_by("-created_at")[:5]
    promocodes = PromoCode.objects.all().order_by('-id')
    latest_review = Review.objects.order_by('-created_at').first()

    return render(request, "dashboard/home.html", {
        "products": products,
        "product_list": product_list,
        "categories": Category.objects.all(),
        "variants": ProductVariant.objects.all(),
        "latest_product": latest_product,
        "orders": orders,
        "promocodes": promocodes,
        "reviews": Review.objects.all(), 
        "latest_review": latest_review, 
    })

# -------------------------
# Product CRUD
# -------------------------
def product_list(request):
    products = Product.objects.all().order_by('-id')
    return render(request, 'dashboard/product_list.html', {'products': products})
def product_form(request, pk=None):
    product = get_object_or_404(Product, pk=pk) if pk else None
    if request.method == "POST":
        form = ProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            form.save()
            messages.success(request, f"Product {'updated' if pk else 'added'} successfully ✅")
            return redirect("dashboard:dashboard_home")
        messages.error(request, "Please correct the errors below ❌")
    else:
        form = ProductForm(instance=product)

    return render(request, "dashboard/product_form.html", {
        "form": form,
        "title": "Edit Product" if pk else "Add Product",
    })

@require_POST
def product_delete(request, pk):
    product = get_object_or_404(Product, pk=pk)
    product.delete()
    messages.success(request, "Product deleted successfully 🗑️")
    return redirect("dashboard:dashboard_home")

# -------------------------
# Variant CRUD
# -------------------------



def variant_list(request):
    variants = ProductVariant.objects.all().select_related('product').prefetch_related('values')
    product_id = request.GET.get('product')
    
    if product_id:
        variants = variants.filter(product_id=product_id)
        product = get_object_or_404(Product, id=product_id)
    else:
        product = None
    
    return render(request, 'dashboard/variant_list.html', {
        'variants': variants,
        'product': product,
    })

def variant_form(request, pk=None):
    variant = get_object_or_404(ProductVariant, pk=pk) if pk else None
    if request.method == "POST":
        form = ProductVariantForm(request.POST, instance=variant)
        if form.is_valid():
            form.save()
            messages.success(request, f"Variant {'updated' if pk else 'added'} successfully ✅")
            return redirect("dashboard:dashboard_home")
        messages.error(request, "Please correct the errors below ❌")
    else:
        form = ProductVariantForm(instance=variant)

    return render(request, "dashboard/variant_form.html", {
        "form": form,
        "title": "Edit Variant" if pk else "Add Variant",
    })

@require_POST
def variant_delete(request, pk):
    variant = get_object_or_404(ProductVariant, pk=pk)
    variant.delete()
    messages.success(request, "Variant deleted successfully 🗑️")
    return redirect("dashboard:dashboard_home")

# -------------------------
# Orders
# -------------------------
def order_list(request):
    orders = Order.objects.all().order_by('-created_at')
    return render(request, 'dashboard/orders/order_list.html', {'orders': orders})

def order_detail(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    return render(request, 'dashboard/orders/order_detail.html', {'order': order})

def order_edit(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    if request.method == "POST":
        form = OrderForm(request.POST, instance=order)
        if form.is_valid():
            form.save()
            messages.success(request, "Order updated successfully.")
            return redirect("dashboard:order_list")
    else:
        form = OrderForm(instance=order)
    return render(request, 'dashboard/orders/order_form.html', {"form": form})

def order_delete(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    if request.method == "POST":
        order.delete()
        messages.success(request, "Order deleted successfully.")
        return redirect("dashboard:order_list")
    return render(request, "dashboard/orders/order_confirm_delete.html", {"order": order})

# -------------------------
# PromoCode (Admin Only)
# -------------------------
@staff_member_required
def promocode_list(request):
    promocodes = PromoCode.objects.all().order_by("-id")
    return render(request, "dashboard/promocode_list.html", {"promocodes": promocodes})

@staff_member_required
def promocode_form(request, pk=None):
    promocode = get_object_or_404(PromoCode, pk=pk) if pk else None
    if request.method == "POST":
        form = PromoCodeForm(request.POST, instance=promocode)
        if form.is_valid():
            form.save()
            messages.success(request, f"PromoCode {'updated' if pk else 'added'} successfully ✅")
            return redirect("dashboard:promocode_list")
        messages.error(request, "Please correct the errors below ❌")
    else:
        form = PromoCodeForm(instance=promocode)

    return render(request, "dashboard/promocode_form.html", {
        "form": form,
        "title": "Edit PromoCode" if pk else "Add PromoCode",
    })

@staff_member_required
def promocode_delete(request, pk):
    promocode = get_object_or_404(PromoCode, pk=pk)
    if request.method == "POST":
        promocode.delete()
        messages.success(request, "PromoCode deleted successfully 🗑️")
        return redirect("dashboard:promocode_list")
    return render(request, "dashboard/promocode_confirm_delete.html", {"promocode": promocode})


# List all reviews
@staff_member_required
def review_list(request):
    reviews = Review.objects.all().order_by('-created_at')
    return render(request, 'dashboard/review_list.html', {'reviews': reviews})

# Add/Edit review
@staff_member_required
def review_form(request, pk=None):
    review = get_object_or_404(Review, pk=pk) if pk else None
    if request.method == 'POST':
        form = ReviewForm(request.POST, instance=review)
        if form.is_valid():
            form.save()
            messages.success(request, f"Review {'updated' if pk else 'added'} successfully ✅")
            return redirect('dashboard:review_list')
        else:
            messages.error(request, "Please correct the errors below ❌")
    else:
        form = ReviewForm(instance=review)
    return render(request, 'dashboard/review_form.html', {'form': form, 'title': 'Edit Review' if pk else 'Add Review'})

# Delete review
@staff_member_required
def review_delete(request, pk):
    review = get_object_or_404(Review, pk=pk)
    if request.method == 'POST':
        review.delete()
        messages.success(request, "Review deleted successfully 🗑️")
        return redirect('dashboard:review_list')
    return render(request, 'dashboard/review_confirm_delete.html', {'review': review})


# dashboard/views.py
from django.shortcuts import render, get_object_or_404, redirect
from .forms import ProductForm, ProductVariantForm, CategoryForm
from shop.models import Product, ProductVariant, Category


def category_list(request):
    categories = Category.objects.all()
    return render(request, "dashboard/category_list.html", {"categories": categories})


def category_form(request, pk=None):
    if pk:
        category = get_object_or_404(Category, pk=pk)
    else:
        category = None

    if request.method == "POST":
        form = CategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            return redirect("dashboard:category_list")
    else:
        form = CategoryForm(instance=category)

    return render(request, "dashboard/category_form.html", {"form": form})


def category_delete(request, pk):
    category = get_object_or_404(Category, pk=pk)
    if request.method == "POST":
        category.delete()
        return redirect("dashboard:category_list")
    return render(request, "dashboard/category_confirm_delete.html", {"category": category})

def customer_list(request):
    customers = User.objects.all().prefetch_related('order_set', 'addresses')

    customer_data = []
    for customer in customers:
        customer_data.append({
            'id': customer.id,
            'username': customer.username,
            'email': customer.email,
            'date_joined': customer.date_joined,
            'is_active': customer.is_active,
            'orders_count': customer.order_set.count(),
            'addresses_count': customer.addresses.count(),
        })

    return render(request, 'dashboard/customer_list.html', {
        'customers': customer_data,
    })


# dashboard/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages

from .forms import (
    ProductForm, ProductVariantFormSet, ProductVariantForm,
    OrderForm, OrderItemForm, PromoCodeForm, ReviewForm, CategoryForm
)
from shop.models import Product


def product_form(request, pk=None):
    """Add/Edit a Product with its Variants"""
    product = get_object_or_404(Product, pk=pk) if pk else None

    if request.method == "POST":
        form = ProductForm(request.POST, request.FILES, instance=product)
        formset = ProductVariantFormSet(request.POST, request.FILES, instance=product, prefix='variants')

        if form.is_valid() and formset.is_valid():
            product = form.save()  # save product first
            formset.instance = product
            formset.save()
            messages.success(request, f"Product {'updated' if pk else 'added'} successfully ✅")
            return redirect("dashboard:dashboard_home")
        else:
            messages.error(request, "Please correct the errors below ❌")

    else:
        form = ProductForm(instance=product)
        formset = ProductVariantFormSet(instance=product, prefix='variants')

    return render(request, "dashboard/product_form.html", {
        "form": form,
        "formset": formset,
        "title": "Edit Product" if pk else "Add Product",
    })




