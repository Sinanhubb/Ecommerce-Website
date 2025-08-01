from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.views.decorators.http import require_POST
from django.http import JsonResponse
import json

from .models import Wishlist, Address, PromoCode, Order, OrderItem
from .forms import AddressForm,UserProfileForm
from shop.models import Cart, CartItem, Product,Review

# --- AUTH --- (unchanged)
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
        'wishlist': wishlist, # pass reviews to template
    })


@login_required
def user_logout(request):
    logout(request)
    messages.success(request, 'You have been logged out.')
    return redirect('accounts:login')

# --- WISHLIST --- (unchanged)
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

# --- CHECKOUT SYSTEM ---

def checkout(request):
    user = request.user
    direct_data = request.session.get('direct_checkout')
    
    if direct_data:
        product = get_object_or_404(Product, id=direct_data['product_id'])
        total = float(direct_data['price']) * direct_data['quantity']
        addresses = Address.objects.filter(user=user)
        
        if request.method == 'POST':
            selected_address_id = request.POST.get('selected_address')
            payment_method = request.POST.get('payment_method')
            promo_code_input = request.POST.get('promo_code')
            
            # Initialize total price
            total = direct_data['price'] * direct_data['quantity']
            discount = 0
            promo_code_obj = None
            
            # Handle promo code if provided
            if promo_code_input:
                try:
                    promo_code_obj = PromoCode.objects.get(code=promo_code_input, active=True)
                    discount = (promo_code_obj.discount_percentage / 100) * total
                    total -= discount
                except PromoCode.DoesNotExist:
                    messages.error(request, "Invalid or expired promo code.")
                    return render(request, 'accounts/checkout.html', {
                        'addresses': addresses,
                        'direct_product': product,
                        'direct_quantity': direct_data['quantity'],
                        'total': total,
                        'is_direct_checkout': True,
                        'promo_error': "Invalid or expired promo code."
                    })
            
            if selected_address_id and payment_method:
                address = Address.objects.get(id=selected_address_id)
                
                # Create order
                order = Order.objects.create(
                    user=user,
                    address=address,
                    total_price=total,
                    payment_method=payment_method,
                    promo_code=promo_code_obj
                )
                
                # Create order item
                OrderItem.objects.create(
                    order=order,
                    product=product,
                    price=direct_data['price'],
                    quantity=direct_data['quantity'],
                )
                
                # Update stock
                product.stock -= direct_data['quantity']
                product.sold_count += direct_data['quantity']
                product.save()
                
                # Clear session data
                del request.session['direct_checkout']
                
                return redirect('accounts:order_summary', order_id=order.id)
        
        return render(request, 'accounts/checkout.html', {
            'addresses': addresses,
            'direct_product': product,
            'direct_quantity': direct_data['quantity'],
            'total': direct_data['price'] * direct_data['quantity'],
            'is_direct_checkout': True
        })
    
    else:
        # Regular cart checkout flow
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
                
                for cart_item in cart.items.all():
                    product = cart_item.product
                    OrderItem.objects.create(
                        order=order,
                        product=product,
                        price=product.price,
                        quantity=cart_item.quantity
                    )
                    
                   
                    product.stock -= cart_item.quantity
                    product.save()

                
                return redirect('accounts:order_summary', order_id=order.id)

        return render(request, 'accounts/checkout.html', {
            'addresses': addresses,
            'cart': cart,
            'promo_error': promo_error,
            'total': total,
            'discount': discount,
            'is_direct_checkout': False
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
        'price': price  # Now storing as float instead of Decimal
    }
    
    return redirect('accounts:checkout')

@login_required
def order_summary(request, order_id):
    order = get_object_or_404(
        Order.objects.select_related('address', 'promo_code')
                   .prefetch_related('items__product'),
        id=order_id,
        user=request.user
    )
    
    subtotal = sum(item.price * item.quantity for item in order.items.all())
    discount = order.promo_code.discount_percentage / 100 * subtotal if order.promo_code else 0
    total = order.total_price
    
    context = {
        'order': order,
        'subtotal': subtotal,
        'discount': discount,
        'total': total,
        'items': order.items.all()
    }
    return render(request, 'accounts/order_summary.html', context)

@login_required
def place_order(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    order.is_paid = True
    order.save()
    
    # Clear cart only if this was a cart checkout
    if not request.session.get('direct_checkout'):
        Cart.objects.filter(user=request.user).delete()
    
    return render(request, 'accounts/order_success.html', {'order': order})

# --- ADDRESS MANAGEMENT --- (unchanged)
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
    discount = (order.promo_code.discount_percentage / 100) * subtotal if order.promo_code else 0
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


def delete_address(request, pk):
    address = get_object_or_404(Address, pk=pk, user=request.user)
    address.delete()
    messages.success(request, "Address deleted successfully.")
    return redirect('accounts:profile') 


