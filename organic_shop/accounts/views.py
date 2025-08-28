from shop.models import Cart, CartItem, Product,Review,ProductVariant
from django.shortcuts import render, redirect, get_object_or_404
from .models import Wishlist, Address, PromoCode, Order, OrderItem
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib.auth.forms import UserCreationForm
from .forms import AddressForm,UserProfileForm
from django.contrib import messages
from django.http import JsonResponse
from django.urls import reverse
from decimal import Decimal
import json
from django.utils import timezone


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
    wishlist = Wishlist.objects.filter(user=user).select_related('product', 'variant')    
    reviews = Review.objects.filter(user=user).select_related('product').order_by('-created_at')
    orders = Order.objects.filter(user=user).order_by('-created_at')

    
    return render(request, 'accounts/profile.html', {
        'cart_items': cart_items,
        'total_price': total_price,
        'reviews': reviews, 
        'addresses': addresses,
        'wishlist': wishlist,
        'orders': orders,
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
    wishlist_items = Wishlist.objects.filter(user=request.user).select_related('product', 'variant')
    wishlist_count = wishlist_items.count()
    return render(request, 'accounts/wishlist.html', {
        'wishlist_items': wishlist_items,
        'wishlist_count': wishlist_count
        })


from django.http import JsonResponse

# accounts/views.py

# ... (keep all your other imports)
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from shop.models import Product, ProductVariant
from .models import Wishlist

# ... (keep your other views like user_login, profile_view, etc.)


# accounts/views.py

@login_required
def add_to_wishlist(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    variant_id = request.POST.get('variant_id')
    variant = None

    if variant_id:
        try:
            variant = get_object_or_404(ProductVariant, id=variant_id, product=product)
        except (ValueError, TypeError):
            variant = None

    # Use filter().first() which is safer than get()
    wishlist_item = Wishlist.objects.filter(
        user=request.user,
        product=product,
        variant=variant
    ).first()

    if wishlist_item:
        # If the item already exists, delete it
        wishlist_item.delete()
        added = False
        message = "Removed from your wishlist."
    else:
        # If it does not exist, create it
        Wishlist.objects.create(
            user=request.user,
            product=product,
            variant=variant
        )
        added = True
        message = "Added to your wishlist."

    wishlist_count = Wishlist.objects.filter(user=request.user).count()

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({
            "added": added,
            "wishlist_count": wishlist_count,
            "message": message
        })

    messages.success(request, message)
    redirect_to = request.POST.get("next") or request.META.get("HTTP_REFERER", "/")
    return redirect(redirect_to)

@login_required
@require_POST
def remove_from_wishlist(request, item_id):
    """
    BUG FIX: Removes a specific item from the wishlist by its own ID, not the product's ID.
    This is much safer and more precise.
    """
    # Find the specific wishlist item and ensure it belongs to the logged-in user for security
    wishlist_item = get_object_or_404(Wishlist, id=item_id, user=request.user)
    wishlist_item.delete()
    messages.success(request, "Item removed from your wishlist.")
    
    redirect_to = request.POST.get('next', 'accounts:wishlist')
    return redirect(redirect_to)

from decimal import Decimal
from django.utils import timezone
from django.contrib import messages

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
        """
        Returns (promo_code_obj, discount_amount, total_amount)
        Validates promo code with timezone awareness, active flag, and usage limit
        """
        promo_code_obj = None
        discount = Decimal('0.00')
        total = subtotal

        if not applied_promo_code:
            return None, discount, total

        try:
            promo_code_obj = PromoCode.objects.get(code=applied_promo_code)

            now = timezone.localtime(timezone.now())

            # Check validity
            if not promo_code_obj.active:
                messages.error(request, "This promo code is not active.")
                promo_code_obj = None
                request.session.pop('applied_promo_code', None)

            elif promo_code_obj.start_date and promo_code_obj.start_date > now:
                messages.error(request, "This promo code is not active yet.")
                promo_code_obj = None
                request.session.pop('applied_promo_code', None)

            elif promo_code_obj.end_date and promo_code_obj.end_date < now:
                messages.error(request, "This promo code has expired.")
                promo_code_obj = None
                request.session.pop('applied_promo_code', None)

            elif promo_code_obj.usage_limit <= 0:
                messages.error(request, "This promo code has reached its usage limit.")
                promo_code_obj = None
                request.session.pop('applied_promo_code', None)

            else:
                # Only show success if promo is valid
                discount = (Decimal(promo_code_obj.discount_percentage) / Decimal('100')) * subtotal
                total = subtotal - discount
                messages.success(request, f"Promo code '{promo_code_obj.code}' applied successfully!")

        except PromoCode.DoesNotExist:
            messages.error(request, "Invalid promo code.")
            request.session.pop('applied_promo_code', None)
            promo_code_obj = None

        return promo_code_obj, discount, total

    # ----- Direct Checkout -----
    if direct_data:
        product = get_object_or_404(Product, id=direct_data['product_id'])
        variant = None
        variant_id = direct_data.get('variant_id')
        if variant_id:
            try:
                variant = ProductVariant.objects.get(sku=variant_id, product=product)
            except ProductVariant.DoesNotExist:
                messages.error(request, "Selected product variant does not exist anymore.")
                del request.session['direct_checkout']
                return redirect('shop:product_detail', slug=product.slug)

        quantity = direct_data['quantity']
        # Corrected Code
        if variant:
            # If a variant exists, use its price
            price = variant.discount_price if variant.discount_price else variant.price
        else:
            # Otherwise, fall back to the main product's price
            price = product.discount_price if product.discount_price else product.price
        subtotal = price * quantity
        addresses = Address.objects.filter(user=user)

        promo_code_obj, discount, total = get_promo_discount(subtotal)

        if request.method == 'POST':
            if 'apply_promo' in request.POST:
                promo_code_input = request.POST.get('promo_code', '').strip()
                if promo_code_input:
                    request.session['applied_promo_code'] = promo_code_input
                return redirect('accounts:checkout')

            elif 'place_order' in request.POST:
                selected_address_id = request.POST.get('selected_address')
                payment_method = request.POST.get('payment_method')
                if selected_address_id and payment_method:
                    address = Address.objects.get(id=selected_address_id)
                    promo_code_obj, discount, total = get_promo_discount(subtotal)

                    # Create Order
                    order = Order.objects.create(
                        user=user,
                        address=address,
                        total_price=total,
                        payment_method=payment_method,
                        promo_code=promo_code_obj
                    )

                    # Update promo usage
                    if promo_code_obj:
                        promo_code_obj.usage_limit -= 1
                        if promo_code_obj.usage_limit <= 0:
                            promo_code_obj.active = False
                        promo_code_obj.save()

                    # Create OrderItem
                    if quantity > variant.stock:
                        messages.error(request, f"Only {variant.stock} item(s) left in stock.")
                        return redirect('shop:product_detail', slug=product.slug)

                    OrderItem.objects.create(
                        order=order,
                        product=product,
                        variant=variant,
                        price=price,
                        quantity=quantity
                    )

                    variant.stock -= quantity
                    variant.sold_count += quantity
                    variant.save()
                    product.save()

                    # Cleanup session
                    del request.session['direct_checkout']
                    request.session.pop('applied_promo_code', None)

                    return redirect('accounts:order_summary', order_id=order.id)

        return render(request, 'accounts/checkout.html', {
            'addresses': addresses,
            'products': [{
                'product': product,
                'quantity': quantity,
                'variant': variant,
                'price': price,
                'total_price': price * quantity
            }],
            'cart_items_count': quantity,
            'subtotal': subtotal,
            'discount': discount,
            'total': total,
            'is_direct_checkout': True,
            'applied_promo_code': applied_promo_code
        })

    # ----- Cart Checkout -----
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
                request.session['applied_promo_code'] = promo_code_input
            return redirect('accounts:checkout')

        elif 'place_order' in request.POST:
            selected_address_id = request.POST.get('selected_address')
            payment_method = request.POST.get('payment_method')
            if selected_address_id and payment_method:
                address = Address.objects.get(id=selected_address_id)
                promo_code_obj, discount, total = get_promo_discount(subtotal)

                order = Order.objects.create(
                    user=user,
                    address=address,
                    total_price=total,
                    promo_code=promo_code_obj,
                    payment_method=payment_method
                )

                # Update promo usage
                if promo_code_obj:
                    promo_code_obj.usage_limit -= 1
                    if promo_code_obj.usage_limit <= 0:
                        promo_code_obj.active = False
                    promo_code_obj.save()

                for cart_item in cart.items.all():
                    item_price = (
                        cart_item.variant.discount_price if cart_item.variant and cart_item.variant.discount_price
                        else (cart_item.variant.price if cart_item.variant
                              else (cart_item.product.discount_price if cart_item.product.discount_price else cart_item.product.price))
                    )
                    OrderItem.objects.create(
                        order=order,
                        product=cart_item.product,
                        variant=cart_item.variant,
                        price=item_price,
                        quantity=cart_item.quantity
                    )

                    if cart_item.variant:
                        cart_item.variant.stock -= cart_item.quantity
                        cart_item.variant.sold_count += cart_item.quantity
                        cart_item.variant.save()

                cart.delete()
                request.session.pop('applied_promo_code', None)
                return redirect('accounts:order_summary', order_id=order.id)

    return render(request, 'accounts/checkout.html', {
        'addresses': addresses,
        'products': [{
            'product': item.product,
            'quantity': item.quantity,
            'variant': item.variant,
            'price': (
                item.variant.discount_price if item.variant and item.variant.discount_price
                else (item.variant.price if item.variant 
                      else (item.product.discount_price if item.product.discount_price else item.product.price))
            ),
            'total_price': (
                (item.variant.discount_price if item.variant and item.variant.discount_price
                 else (item.variant.price if item.variant 
                       else (item.product.discount_price if item.product.discount_price else item.product.price)))
                * item.quantity
            )
        } for item in cart.items.all()],
        'cart_items_count': cart.items.count(),
        'subtotal': subtotal,
        'discount': discount,
        'total': total,
        'is_direct_checkout': False,
        'applied_promo_code': applied_promo_code
    })

# accounts/views.py

from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from shop.models import Product, ProductVariant # Make sure models are imported

@login_required
def direct_checkout(request, pk):
    product = get_object_or_404(Product, pk=pk)
    variant_id = request.POST.get('variant_id')
    variant = None # Initialize variant as None by default

    # --- NEW: Conditionally find the variant ---
    if variant_id:
        # A variant was selected, so we MUST find it.
        try:
            variant = ProductVariant.objects.get(sku=variant_id, product=product)
        except ProductVariant.DoesNotExist:
            messages.error(request, "The selected product variant does not exist.")
            return redirect('shop:product_detail', slug=product.slug)

    try:
        quantity = int(request.POST.get('quantity', 1))
        if quantity <= 0:
            raise ValueError("Quantity must be at least 1.")

        # --- NEW: Check stock on either the variant or the main product ---
        # Note: This assumes your Product model has a 'stock' field for non-variant products.
        stock_available = variant.stock if variant else product.stock
        if quantity > stock_available:
            raise ValueError(f"Only {stock_available} item(s) are available in stock.")

        # Set up the session data, storing the SKU if a variant exists, otherwise None
        request.session['direct_checkout'] = {
            'product_id': product.id,
            'variant_id': variant.sku if variant else None,
            'quantity': quantity
        }
        return redirect('accounts:checkout')

    except ValueError as e:
        messages.error(request, str(e))
        return redirect('shop:product_detail', slug=product.slug)



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
    return render(request, 'accounts/order_success.html', {'order': order})


@login_required
def order_summary(request, order_id):
    order = get_object_or_404(
        Order.objects.select_related('address', 'promo_code')
                     .prefetch_related('items__product', 'items__variant'),
        id=order_id,
        user=request.user
    )

    items = order.items.all()
    subtotal = sum(item.price * item.quantity for item in items)
    discount = Decimal('0.00')

    if order.promo_code:
        discount = (Decimal(order.promo_code.discount_percentage) / Decimal('100')) * subtotal

    total = order.total_price

    return render(request, 'accounts/order_summary.html', {
        'order': order,
        'items': items,
        'subtotal': subtotal,
        'discount': discount,
        'total': total
    })