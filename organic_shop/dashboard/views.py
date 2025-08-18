from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator

from .forms import ProductForm, ProductVariantForm
from shop.models import Product, ProductVariant, Category


def dashboard_home(request):
    query = request.GET.get("q")
    product_list = Product.objects.all().order_by("-id")

    if query:
        product_list = product_list.filter(name__icontains=query)

    paginator = Paginator(product_list, 10)
    page_number = request.GET.get("page")
    products = paginator.get_page(page_number)

    latest_product = Product.objects.order_by("-id").first()

    # Get latest 5 orders
    orders = Order.objects.all().order_by("-created_at")[:5]

    return render(request, "dashboard/home.html", {
        "products": products,
        "categories": Category.objects.all(),
        "variants": ProductVariant.objects.all(),
        "latest_product": latest_product,
        "orders": orders,
    })


# 🔹 Product Add/Edit (combined)
def product_form(request, pk=None):
    product = get_object_or_404(Product, pk=pk) if pk else None
    if request.method == "POST":
        form = ProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            form.save()
            messages.success(request, f"Product {'updated' if pk else 'added'} successfully ✅")
            return redirect("dashboard:dashboard_home")
        else:
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


# 🔹 Variant Add/Edit (combined)
def variant_form(request, pk=None):
    variant = get_object_or_404(ProductVariant, pk=pk) if pk else None
    if request.method == "POST":
        form = ProductVariantForm(request.POST, instance=variant)
        if form.is_valid():
            form.save()
            messages.success(request, f"Variant {'updated' if pk else 'added'} successfully ✅")
            return redirect("dashboard:dashboard_home")
        else:
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



from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from .forms import OrderForm, OrderItemForm
from shop.models import Product, ProductVariant
from accounts.models import Order, OrderItem, PromoCode, Address  # adjust import if in same app


# List all orders
def order_list(request):
    orders = Order.objects.all().order_by('-created_at')
    return render(request, 'dashboard/orders/order_list.html', {'orders': orders})


# View order details
def order_detail(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    return render(request, 'dashboard/orders/order_detail.html', {'order': order})


# Update order status/payment
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


# Delete an order
def order_delete(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    if request.method == "POST":
        order.delete()
        messages.success(request, "Order deleted successfully.")
        return redirect("dashboard:order_list")
    return render(request, "dashboard/orders/order_confirm_delete.html", {"order": order})




