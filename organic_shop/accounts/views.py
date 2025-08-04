from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from .models import Wishlist, Address, PromoCode, Order, OrderItem
from .forms import AddressForm,UserProfileForm
from shop.models import Cart, CartItem, Product,Review
import json
from decimal import Decimal

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


@login_required
def user_logout(request):
    logout(request)
    messages.success(request, 'You have been logged out.')
    return redirect('accounts:login')


def register_view(request):
    form = UserCreationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        login(request, user)
        return redirect('accounts:profile')
    return render(request, 'accounts/register.html', {'form': form})

@login_required
def profile_view(request):
    user = request.user
    cart = Cart.objects.filter(user=user).first()
    addresses = Address.objects.filter(user=user)
    cart_items = cart.items.select_related('product') if cart else []
    total_price = sum(item.total_price for item in cart_items)
    wishlist = Wishlist.objects.filter(user=user).select_related('product')
    
    reviews = Review.objects.filter(user=user).select_related('product').order_by('-created_at')
    
    return render(request, 'accounts/profile.html', {
        'cart_items': cart_items,
        'total_price': total_price,
        'reviews': reviews, 
        'addresses': addresses,
        'wishlist': wishlist,
    })


@login_required
def edit_profile_view(request):
    user = request.user
    form = UserProfileForm(instance=user)

    if request.method == 'POST':
        form = UserProfileForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated successfully.")
            return redirect('accounts:profile')
        else:
            messages.error(request, "Please correct the errors below.")

    return render(request, 'accounts/edit_profile.html', {'form': form})




@login_required
def wishlist_view(request):
    wishlist_items = Wishlist.objects.filter(user=request.user).select_related('product')
    wishlist_count = wishlist_items.count()
    return render(request, 'accounts/wishlist.html', {
        'wishlist_items': wishlist_items,
        'wishlist_count': wishlist_count
        })

@login_required
def add_to_wishlist(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    Wishlist.objects.get_or_create(user=request.user, product=product)
    return redirect('shop:product_detail', slug=product.slug)

@login_required
def remove_from_wishlist(request, product_id):
    Wishlist.objects.filter(user=request.user, product_id=product_id).delete()
    return redirect('accounts:wishlist')



@login_required
def checkout(request):
    user = request.user
    direct_data = request.session.get('direct_checkout')
    applied_promo_code = request.session.get('applied_promo_code')

    
    if request.GET.get('remove_promo') == '1':
        request.session.pop('applied_promo_code', None)
        messages.success(request, "Promo code removed successfully.")
        return redirect('accounts:checkout')

    
    def get_promo_discount(subtotal):
        promo_code_obj = None
        discount = 0
        total = subtotal

        if applied_promo_code:
            try:
                promo_code_obj = PromoCode.objects.get(code=applied_promo_code, active=True)
                discount = (Decimal(promo_code_obj.discount_percentage) / Decimal('100')) * subtotal
                total = subtotal - discount
            except PromoCode.DoesNotExist:
                request.session.pop('applied_promo_code', None)
                messages.error(request, "Invalid or expired promo code.")
                promo_code_obj = None

        return promo_code_obj, discount, total

    # Handle Direct Checkout
    if direct_data:
        product = get_object_or_404(Product, id=direct_data['product_id'])
        quantity = direct_data['quantity']
        price = Decimal(direct_data['price'])
        subtotal = price * quantity
        addresses = Address.objects.filter(user=user)

        promo_code_obj, discount, total = get_promo_discount(subtotal)

        if request.method == 'POST':
            if 'apply_promo' in request.POST:
                promo_code_input = request.POST.get('promo_code', '').strip()
                if promo_code_input:
                    try:
                        promo = PromoCode.objects.get(code=promo_code_input, active=True)
                        request.session['applied_promo_code'] = promo.code
                        messages.success(request, "Promo code applied successfully!")
                    except PromoCode.DoesNotExist:
                        messages.error(request, "Invalid or expired promo code.")
                return redirect('accounts:checkout')

            elif 'place_order' in request.POST:
                selected_address_id = request.POST.get('selected_address')
                payment_method = request.POST.get('payment_method')

                if selected_address_id and payment_method:
                    address = Address.objects.get(id=selected_address_id)
                    order = Order.objects.create(
                        user=user,
                        address=address,
                        total_price=total,
                        payment_method=payment_method,
                        promo_code=promo_code_obj
                    )

                    OrderItem.objects.create(
                        order=order,
                        product=product,
                        price=price,
                        quantity=quantity
                    )

                    product.stock -= quantity
                    product.sold_count += quantity
                    product.save()

                    del request.session['direct_checkout']
                    request.session.pop('applied_promo_code', None)

                    return redirect('accounts:order_summary', order_id=order.id)

        return render(request, 'accounts/checkout.html', {
    'addresses': addresses,
    'products': [{
        'product': product,
        'quantity': quantity,
        'price': price,
        'total_price': price * quantity
    }],
    'cart_items_count': quantity,  # For direct checkout, quantity = total items
    'subtotal': subtotal,
    'discount': discount,
    'total': total,
    'is_direct_checkout': True,
    'applied_promo_code': applied_promo_code
})

    # Handle Regular Cart Checkout
    else:
        cart = Cart.objects.filter(user=user).first()
        if not cart or not cart.items.exists():
            messages.warning(request, "Your cart is empty.")
            return redirect('shop:index')

        addresses = Address.objects.filter(user=user)
        subtotal = cart.total_price

        promo_code_obj, discount, total = get_promo_discount(subtotal)

        if request.method == 'POST':
            if 'apply_promo' in request.POST:
                promo_code_input = request.POST.get('promo_code', '').strip()
                if promo_code_input:
                    try:
                        promo = PromoCode.objects.get(code=promo_code_input, active=True)
                        request.session['applied_promo_code'] = promo.code
                        messages.success(request, "Promo code applied successfully!")
                    except PromoCode.DoesNotExist:
                        messages.error(request, "Invalid or expired promo code.")
                return redirect('accounts:checkout')

            elif 'place_order' in request.POST:
                selected_address_id = request.POST.get('selected_address')
                payment_method = request.POST.get('payment_method')

                if selected_address_id and payment_method:
                    address = Address.objects.get(id=selected_address_id)
                    order = Order.objects.create(
                        user=user,
                        address=address,
                        total_price=total,
                        promo_code=promo_code_obj,
                        payment_method=payment_method
                    )

                    for cart_item in cart.items.all():
                        OrderItem.objects.create(
                            order=order,
                            product=cart_item.product,
                            price=cart_item.product.price,
                            quantity=cart_item.quantity
                        )
                        cart_item.product.stock -= cart_item.quantity
                        cart_item.product.save()

                    cart.delete()
                    request.session.pop('applied_promo_code', None)

                    return redirect('accounts:order_summary', order_id=order.id)

        return render(request, 'accounts/checkout.html', {
    'addresses': addresses,
    'products': [{
        'product': item.product,
        'quantity': item.quantity,
        'price': item.product.price,
        'total_price': item.product.price * item.quantity
    } for item in cart.items.all()],
    'cart_items_count': cart.items.count(),
    'subtotal': subtotal,
    'discount': discount,
    'total': total,
    'is_direct_checkout': False,
    'applied_promo_code': applied_promo_code
})
@login_required
def direct_checkout(request, pk):
    product = get_object_or_404(Product, pk=pk)
    
    # Get quantity from POST or default to 1
    quantity = int(request.POST.get('quantity', 1))
    
    # Validate stock
    if quantity > product.stock:
        messages.error(request, f"Only {product.stock} available in stock")
        return redirect('shop:product_detail', pk=product.pk)
    
    # Calculate price and convert Decimal to float for session storage
    price = float(product.discount_price if product.discount_price else product.price)
    
    # Store direct checkout data in session
    request.session['direct_checkout'] = {
        'product_id': product.id,
        'quantity': quantity,
        'price': price  
    }
    
    return redirect('accounts:checkout')



@login_required
def add_address(request):
    if request.method == 'POST':
        form = AddressForm(request.POST)
        if form.is_valid():
            address = form.save(commit=False)
            address.user = request.user
            address.save()
            messages.success(request, 'Address added successfully.')
            return redirect('accounts:checkout')
    else:
        form = AddressForm()

    return render(request, 'accounts/add_address.html', {'form': form})

@login_required
def edit_address(request, address_id):
    address = get_object_or_404(Address, id=address_id, user=request.user)

    next_url = request.GET.get('next') or request.POST.get('next') or reverse('accounts:profile')

    if request.method == 'POST':
        for field in ['full_name', 'phone', 'address_line', 'city', 'state', 'postal_code', 'country']:
            setattr(address, field, request.POST.get(field, '').strip())
        address.save()
        messages.success(request, 'Address updated successfully.')
        return redirect(next_url)

    return render(request, 'accounts/edit_address.html', {
        'address': address,
        'next': next_url
    })


def delete_address(request, pk):
    address = get_object_or_404(Address, pk=pk, user=request.user)
    address.delete()
    messages.success(request, "Address deleted successfully.")
    return redirect('accounts:profile') 




@login_required
def my_orders_view(request):
    orders = Order.objects.filter(user=request.user).order_by('-created_at').prefetch_related('items__product')
    return render(request, 'accounts/my_orders.html', {'orders': orders})



@login_required
def order_detail_view(request, order_id):
    order = get_object_or_404(
        Order.objects.select_related('address', 'promo_code')
                     .prefetch_related('items__product'),
        id=order_id,
        user=request.user
    )

    subtotal = sum(item.price * item.quantity for item in order.items.all())
    discount = (Decimal(order.promo_code.discount_percentage) / Decimal('100')) * subtotal if order.promo_code else Decimal('0')
    total = order.total_price

    return render(request, 'accounts/order_detail.html', {
        'order': order,
        'items': order.items.all(),
        'subtotal': subtotal,
        'discount': discount,
        'total': total
    })

@login_required
def order_tracking_view(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return render(request, 'accounts/order_tracking.html', {'order': order})

@login_required
def place_order(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    order.is_paid = True
    order.save()
    
  
    if not request.session.get('direct_checkout'):
        Cart.objects.filter(user=request.user).delete()
    
    return render(request, 'accounts/order_success.html', {'order': order})


@login_required
def order_summary(request, order_id):
    order = get_object_or_404(
        Order.objects.select_related('address', 'promo_code')
                   .prefetch_related('items__product'),
        id=order_id,
        user=request.user
    )
    
    subtotal = sum(item.price * item.quantity for item in order.items.all())
    discount = (Decimal(order.promo_code.discount_percentage) / Decimal('100')) * subtotal if order.promo_code else Decimal('0')
    total = order.total_price
    
    context = {
        'order': order,
        'subtotal': subtotal,
        'discount': discount,
        'total': total,
        'items': order.items.all()
    }
    return render(request, 'accounts/order_summary.html', context)





