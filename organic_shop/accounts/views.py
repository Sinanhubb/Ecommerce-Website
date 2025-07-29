from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from shop.models import Cart, CartItem

def user_login(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)

           
            session_key = request.session.session_key
            if not session_key:
                request.session.create()  
                session_key = request.session.session_key

            try:
                anon_cart = Cart.objects.get(session_key=session_key, user__isnull=True)
                user_cart, created = Cart.objects.get_or_create(user=user)

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

            next_url = request.GET.get('next')
            return redirect(next_url if next_url else 'shop:index')
        else:
            messages.error(request, 'Invalid username or password')

    return render(request, 'accounts/login.html')


def register_view(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('accounts:profile')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = UserCreationForm()
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
