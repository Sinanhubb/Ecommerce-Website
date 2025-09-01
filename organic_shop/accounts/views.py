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

# accounts/views.py
from django.db import transaction

# ... (all your other imports) ...

def _create_order_with_items(request, address, payment_method, items_data, subtotal, promo_code_obj):
    """
    A robust helper function to create an order from a list of items.
    Handles stock checking, transactions, and promo code usage.
    Returns the created Order object on success, or None on failure.
    """
    user = request.user
    discount = Decimal('0.00')
    total = subtotal

    # Recalculate discount based on the final promo code object
    if promo_code_obj:
        discount = (Decimal(promo_code_obj.discount_percentage) / Decimal('100')) * subtotal
        total = subtotal - discount

    try:
        # Use a transaction to ensure all database operations are atomic.
        # This prevents creating a partial order if stock runs out mid-process.
        with transaction.atomic():
            # 1. Create the main Order object
            order = Order.objects.create(
                user=user,
                address=address,
                total_price=total,
                payment_method=payment_method,
                promo_code=promo_code_obj
            )

            # 2. Loop through the items to create OrderItems and check stock
            for item_info in items_data:
                variant = item_info.get('variant')

                # Lock the variant/product to prevent race conditions (overselling)
                if variant:
                    # Use select_for_update() to lock the database row until the transaction is complete
                    variant_to_check = ProductVariant.objects.select_for_update().get(id=variant.id)
                    stock_available = variant_to_check.stock
                else:
                    # Handle non-variant products if necessary (assuming Product has a stock field)
                    product_to_check = Product.objects.select_for_update().get(id=item_info['product'].id)
                    stock_available = product_to_check.stock

                # Check stock right before creating the order item
                if item_info['quantity'] > stock_available:
                    messages.error(request, f"Sorry, '{item_info['product'].name}' went out of stock while you were checking out.")
                    # By raising an exception, the transaction.atomic() block will automatically roll back
                    raise ValueError("Insufficient stock")

                # 3. Create the OrderItem
                OrderItem.objects.create(
                    order=order,
                    product=item_info['product'],
                    variant=variant,
                    price=item_info['price'],
                    quantity=item_info['quantity']
                )

                # 4. Update the stock
                if variant:
                    variant_to_check.stock -= item_info['quantity']
                    variant_to_check.sold_count += item_info['quantity']
                    variant_to_check.save()
                else:
                    product_to_check.stock -= item_info['quantity']
                    product_to_check.sold_count += item_info['quantity']
                    product_to_check.save()

            # 5. Update promo code usage after the order is successfully created
            if promo_code_obj:
                promo_code_obj.usage_limit -= 1
                if promo_code_obj.usage_limit <= 0:
                    promo_code_obj.active = False
                promo_code_obj.save()

        # If the transaction completes without errors, return the order
        return order

    except ValueError as e:
        # This will catch our "Insufficient stock" error and stop the process
        return None


# accounts/views.py

def user_login(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)

        if user:
            login(request, user) # The signal will fire automatically here
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

# accounts/views.py

@login_required
def checkout(request):
    user = request.user
    direct_data = request.session.get('direct_checkout')
    applied_promo_code_str = request.session.get('applied_promo_code')
    addresses = Address.objects.filter(user=user)

    # ----- 1. PREPARE ITEMS AND SUBTOTAL (Handles both flows) -----
    items_data = []
    subtotal = Decimal('0.00')

    if direct_data:
        # --- Direct Checkout Flow ---
        try:
            product = get_object_or_404(Product, id=direct_data['product_id'])
            variant = None
            variant_sku = direct_data.get('variant_id') # Changed from 'sku' to 'id' for reliability
            if variant_sku:
                variant = get_object_or_404(ProductVariant, sku=variant_sku, product=product)

            price = (variant.discount_price if variant and variant.discount_price else
                     variant.price if variant else
                     product.discount_price if product.discount_price else
                     product.price)
            
            quantity = direct_data['quantity']
            items_data.append({
                'product': product,
                'variant': variant,
                'quantity': quantity,
                'price': price,
                'total_price': price * quantity
            })
            subtotal = price * quantity
        except (Product.DoesNotExist, ProductVariant.DoesNotExist):
            messages.error(request, "The product you were trying to buy is no longer available.")
            request.session.pop('direct_checkout', None)
            return redirect('shop:index')
    else:
        # --- Cart Checkout Flow ---
        cart = Cart.objects.filter(user=user).first()
        if not cart or not cart.items.exists():
            messages.warning(request, "Your cart is empty.")
            return redirect('shop:index')

        for item in cart.items.all():
            price = item.get_price() # Assumes a get_price() method on CartItem model
            items_data.append({
                'product': item.product,
                'variant': item.variant,
                'quantity': item.quantity,
                'price': price,
                'total_price': item.total_price # Assumes a total_price property on CartItem model
            })
        subtotal = cart.total_price

    # ----- 2. HANDLE PROMO CODES -----
    # Note: Your `get_promo_discount` function can be simplified or used as is.
    # For this example, we'll fetch the object and let the helper calculate the final discount.
    promo_code_obj = None
    if applied_promo_code_str:
        try:
            promo_code_obj = PromoCode.objects.get(code=applied_promo_code_str, active=True)
            # You can add your other validation checks here (dates, usage, etc.)
        except PromoCode.DoesNotExist:
            messages.error(request, "The applied promo code is not valid.")
            request.session.pop('applied_promo_code', None)

    # Let's get the final discount and total for display
    discount_display = (Decimal(promo_code_obj.discount_percentage) / Decimal('100')) * subtotal if promo_code_obj else Decimal('0.00')
    total_display = subtotal - discount_display

    # ----- 3. HANDLE POST REQUESTS (Placing Order / Applying Promo) -----
    if request.method == 'POST':
        if 'apply_promo' in request.POST:
            promo_code_input = request.POST.get('promo_code', '').strip()
            if promo_code_input:
                request.session['applied_promo_code'] = promo_code_input
            return redirect('accounts:checkout')

        elif 'place_order' in request.POST:
            selected_address_id = request.POST.get('selected_address')
            payment_method = request.POST.get('payment_method')

            if not selected_address_id or not payment_method:
                messages.error(request, "Please select a shipping address and payment method.")
                return redirect('accounts:checkout')

            address = get_object_or_404(Address, id=selected_address_id, user=user)

            # CALL THE HELPER FUNCTION!
            order = _create_order_with_items(
                request=request,
                address=address,
                payment_method=payment_method,
                items_data=items_data,
                subtotal=subtotal,
                promo_code_obj=promo_code_obj # Pass the validated object
            )

            if order:
                # Success! The helper function did all the work.
                # Clean up session data.
                request.session.pop('direct_checkout', None)
                request.session.pop('applied_promo_code', None)
                if not direct_data: # If it was a cart checkout, delete the cart
                    cart.delete()
                
                messages.success(request, "Your order has been placed successfully!")
                return redirect('accounts:order_summary', order_id=order.id)
            else:
                # Failure! The helper function already set the error message.
                # Just redirect back to the checkout page.
                return redirect('accounts:checkout')

    # ----- 4. RENDER THE TEMPLATE -----
    context = {
        'addresses': addresses,
        'products': items_data,
        'cart_items_count': sum(item['quantity'] for item in items_data),
        'subtotal': subtotal,
        'discount': discount_display,
        'total': total_display,
        'is_direct_checkout': bool(direct_data),
        'applied_promo_code': applied_promo_code_str if promo_code_obj else None
    }
    return render(request, 'accounts/checkout.html', context)

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
    
    # 1. Get the 'next' URL from the query string, form post, or use a default
    next_url = request.GET.get('next') or request.POST.get('next') or reverse('accounts:profile')

    if request.method == 'POST':
        form = AddressForm(request.POST, instance=address)
        if form.is_valid():
            form.save()
            messages.success(request, 'Address updated successfully.')
            # 2. Redirect to the determined next_url after a successful save
            return redirect(next_url)
    else:
        form = AddressForm(instance=address)
        
    # 3. Pass all necessary context to the template
    context = {
        'form': form,
        'address': address, # Pass the address object for display purposes (e.g., in a title)
        'next': next_url
    }
    return render(request, 'accounts/edit_address.html', context)

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

from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Order
from .utils import generate_invoice

@login_required
def download_invoice(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return generate_invoice(order)
