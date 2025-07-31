from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.views.decorators.http import require_POST

from .models import Wishlist, Address, PromoCode, Order
from .forms import AddressForm
from shop.models import Cart, CartItem, Product


# --- AUTH ---
def user_login(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)

        if user:
            login(request, user)
            session_key = request.session.session_key or request.session.create()

            try:
                anon_cart = Cart.objects.get(session_key=session_key, user__isnull=True)
                user_cart, _ = Cart.objects.get_or_create(user=user)

                for item in anon_cart.items.all():
                    existing = user_cart.items.filter(product=item.product).first()
                    if existing:
                        existing.quantity += item.quantity
                        existing.save()
                    else:
                        item.cart = user_cart
                        item.save()

                anon_cart.delete()
            except Cart.DoesNotExist:
                pass

            return redirect(request.GET.get('next', 'shop:index'))
        else:
            messages.error(request, 'Invalid username or password.')

    return render(request, 'accounts/login.html')


def register_view(request):
    form = UserCreationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        login(request, user)
        return redirect('accounts:profile')
    return render(request, 'accounts/register.html', {'form': form})


@login_required
def profile_view(request):
    cart = Cart.objects.filter(user=request.user).first()
    cart_items = cart.items.select_related('product') if cart else []
    total_price = sum(item.total_price for item in cart_items)
    return render(request, 'accounts/profile.html', {
        'cart_items': cart_items,
        'total_price': total_price,
    })


@login_required
def user_logout(request):
    logout(request)
    messages.success(request, 'You have been logged out.')
    return redirect('accounts:login')


# --- WISHLIST ---
@login_required
def wishlist_view(request):
    wishlist_items = Wishlist.objects.filter(user=request.user).select_related('product')
    return render(request, 'accounts/wishlist.html', {'wishlist_items': wishlist_items})


@login_required
def add_to_wishlist(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    Wishlist.objects.get_or_create(user=request.user, product=product)
    return redirect('shop:product_detail', slug=product.slug)


@login_required
def remove_from_wishlist(request, product_id):
    Wishlist.objects.filter(user=request.user, product_id=product_id).delete()
    return redirect('accounts:wishlist')


# --- CHECKOUT (CART-BASED) ---
@login_required
def checkout(request):
    user = request.user
    cart = Cart.objects.filter(user=user).first()
    if not cart or not cart.items.exists():
        messages.warning(request, "Your cart is empty.")
        return redirect('shop:index')

    addresses = Address.objects.filter(user=user)
    promo_error = ''
    promo_code_obj = None
    discount = 0
    total = cart.total_price

    if request.method == 'POST':
        selected_address_id = request.POST.get('selected_address')
        payment_method = request.POST.get('payment_method')
        promo_code_input = request.POST.get('promo_code')

        if promo_code_input:
            try:
                promo_code_obj = PromoCode.objects.get(code=promo_code_input, active=True)
                discount = (promo_code_obj.discount_percentage / 100) * total
                total -= discount
            except PromoCode.DoesNotExist:
                promo_error = "Invalid or expired promo code."

        if selected_address_id and payment_method:
            address = Address.objects.get(id=selected_address_id)
            order = Order.objects.create(
                user=user,
                address=address,
                total_price=total,
                promo_code=promo_code_obj,
                payment_method=payment_method
            )
            return redirect('accounts:order_summary', order_id=order.id)

    return render(request, 'accounts/checkout.html', {
        'addresses': addresses,
        'cart': cart,
        'promo_error': promo_error,
        'total': total,
        'discount': discount,
    })


@login_required
def order_summary(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return render(request, 'accounts/order_summary.html', {'order': order})


@login_required
def place_order(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    order.is_paid = True
    order.save()
    Cart.objects.filter(user=request.user).delete()  # Clear cart
    return render(request, 'shop/order_success.html', {'order': order})



@login_required
def place_direct_order(request, product_id):
    product = get_object_or_404(Product, id=product_id)

    if request.method == 'POST':
        quantity = 1
        price = product.discount_price if product.discount_price else product.price
        total_price = price * quantity

        address = Address.objects.filter(user=request.user).first()
        if not address:
            messages.error(request, "Please add an address before placing the order.")
            return redirect('accounts:add_address')

        order = Order.objects.create(
            user=request.user,
            address=address,
            product=product,  # only if Order model has `product` field
            total_price=total_price,
            payment_method='COD',
            is_paid=True
        )

        return render(request, 'shop/order_success.html', {'order': order})

    return redirect('shop:index')


# --- ADDRESS MANAGEMENT ---
@login_required
def add_address(request):
    if request.method == 'POST':
        required_fields = ['full_name', 'phone', 'address_line', 'city', 'postal_code', 'country']
        if all(request.POST.get(field, '').strip() for field in required_fields):
            Address.objects.create(
                user=request.user,
                full_name=request.POST['full_name'],
                phone=request.POST['phone'],
                address_line=request.POST['address_line'],
                city=request.POST['city'],
                postal_code=request.POST['postal_code'],
                country=request.POST['country'],
            )
            messages.success(request, 'Address added successfully.')
            return redirect('accounts:checkout')
        messages.error(request, 'Please fill in all fields.')

    return render(request, 'accounts/add_address.html')


@login_required
def edit_address(request, address_id):
    address = get_object_or_404(Address, id=address_id, user=request.user)

    if request.method == 'POST':
        for field in ['full_name', 'phone', 'address_line', 'city', 'postal_code', 'country']:
            setattr(address, field, request.POST.get(field, '').strip())
        address.save()
        messages.success(request, 'Address updated successfully.')
        return redirect('accounts:checkout')

    return render(request, 'accounts/edit_address.html', {'address': address})


@login_required
def direct_checkout(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    total_price = product.discount_price if product.discount_price else product.price
    address = Address.objects.filter(user=request.user)

    if request.method == 'POST':
        selected_address_id = request.POST.get('selected_address')
        payment_method = request.POST.get('payment_method')

        if selected_address_id and payment_method:
            selected_address = Address.objects.get(id=selected_address_id)
            order = Order.objects.create(
                user=request.user,
                product=product,
                address=selected_address,
                total_price=total_price,
                payment_method=payment_method,
                is_paid=True
            )
            return redirect('accounts:order_summary', order.id)

    return render(request, 'accounts/direct_checkout.html', {
        'product': product,
        'addresses': address,
        'total': total_price
    })

