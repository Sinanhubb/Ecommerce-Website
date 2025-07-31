from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from .models import Category, Product, Cart, CartItem, Review
from .forms import CartAddProductForm,ReviewForm
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Avg
import json


def index(request):
    categories = Category.objects.all()
    featured_products = Product.objects.filter(available=True, is_featured=True)[:8]
    best_selling = Product.objects.filter(available=True).order_by('-sold_count')[:10]
    just_arrived = Product.objects.filter(available=True).order_by('-created_at')[:10]
    most_popular = Product.objects.filter(available=True).order_by('-views')[:8]

    context = {
        'categories': categories,
       'featured_products': featured_products,
        'best_selling': best_selling,
        'just_arrived': just_arrived,
        'most_popular': most_popular,
    }
    return render(request, 'shop/index.html', context)



def product_detail(request, slug):
    product = get_object_or_404(Product, slug=slug, available=True)

    # Increment view count
    product.views += 1
    product.save()

    # Cart form
    cart_product_form = CartAddProductForm()

    # Related/similar products
    similar_products = Product.objects.filter(category=product.category).exclude(id=product.id)[:4]

    # Fetch reviews
    reviews = product.reviews.all().order_by('-created_at')
    average_rating = reviews.aggregate(Avg('rating'))['rating__avg']
    recently_viewed_ids = request.session.get('recently_viewed', [])

    # Remove current product ID
    if product.id in recently_viewed_ids:
        recently_viewed_ids.remove(product.id)

    # Add current product to front
    recently_viewed_ids.insert(0, product.id)

    # Save updated list to session (limit to last 5)
    request.session['recently_viewed'] = recently_viewed_ids[:5]

    # Get products in same order as IDs
    recently_viewed_queryset = Product.objects.filter(id__in=recently_viewed_ids).exclude(id=product.id)
    recently_viewed = sorted(
        recently_viewed_queryset,
        key=lambda x: recently_viewed_ids.index(x.id)
    )



    # Handle review form
    review_form = None
    if request.method == 'POST' and request.user.is_authenticated:
        review_form = ReviewForm(request.POST)
        if review_form.is_valid():
            review = review_form.save(commit=False)
            review.user = request.user
            review.product = product
            review.save()
            return redirect('shop:product_detail', slug=slug)
    else:
        review_form = ReviewForm()


    recent = request.session.get('recently_viewed', [])
    if product.id in recent:
        recent.remove(product.id)
    recent.insert(0, product.id)
    request.session['recently_viewed'] = recent[:5]



    context = {
        'product': product,
        'cart_product_form': cart_product_form,
        'similar_products': similar_products,
        'reviews': reviews,
        'average_rating': average_rating,
        'review_form': review_form,
        'recently_viewed': recently_viewed,

    }
    return render(request, 'shop/product_detail.html', context)


def category_detail(request, slug):
    category = get_object_or_404(Category, slug=slug)
    products = category.products.filter(available=True)
    
    context = {
        'category': category,
        'products': products,
    }
    return render(request, 'shop/category_detail.html', context)

@login_required(login_url='accounts:login')
def cart_add(request, product_id):
    cart = get_or_create_cart(request)
    product = get_object_or_404(Product, id=product_id)
    form = CartAddProductForm(request.POST)

    if form.is_valid():
        cd = form.cleaned_data
        item, created = CartItem.objects.get_or_create(
            cart=cart,
            product=product,
            defaults={'quantity': cd['quantity']}
        )
        if not created:
            item.quantity += cd['quantity']
            item.save()
    return redirect('shop:cart_detail')

def cart_remove(request, product_id):
    cart = get_or_create_cart(request)
    product = get_object_or_404(Product, id=product_id)
    cart.items.filter(product=product).delete()
    return redirect('shop:cart_detail')

def cart_detail(request):
    cart = get_or_create_cart(request)
    return render(request, 'shop/cart_detail.html', {'cart': cart})

def get_or_create_cart(request):
    if request.user.is_authenticated:
        # If session has anonymous cart, merge it
        session_key = request.session.session_key
        if session_key:
            anon_cart = Cart.objects.filter(session_key=session_key, user__isnull=True).first()
            if anon_cart:
                user_cart, created = Cart.objects.get_or_create(user=request.user)
                for item in anon_cart.items.all():
                    existing_item = user_cart.items.filter(product=item.product).first()
                    if existing_item:
                        existing_item.quantity += item.quantity
                        existing_item.save()
                    else:
                        item.cart = user_cart
                        item.save()
                anon_cart.delete()
        cart, _ = Cart.objects.get_or_create(user=request.user)
    else:
        session_key = request.session.session_key or request.session.create()
        cart, _ = Cart.objects.get_or_create(session_key=session_key, user=None)
    return cart

def checkout(request):
    return render(request, 'accounts/checkout.html')

def ajax_search(request):
    query = request.GET.get('q', '')
    results = []
    if query:
        products = Product.objects.filter(name__icontains=query, available=True)
        for product in products:
            results.append({
                'name': product.name,
                'price': str(product.price),
                'image_url': product.image.url if product.image else '/static/images/no-image.jpg',
                'detail_url': product.get_absolute_url(),  
            })
    return JsonResponse({'results': results})


@login_required
def remove_from_cart(request, item_id):
    item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
    item.delete()
    return redirect('accounts:profile')


@require_POST
@login_required
def update_cart_item(request, item_id):
    item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
    try:
        quantity = int(request.POST.get('quantity'))
        if quantity > 0:
            item.quantity = quantity
            item.save()
        else:
            item.delete()
    except (ValueError, TypeError):
        pass
    return redirect('shop:cart_detail')


@csrf_exempt
@require_POST
@login_required
def update_cart_item_ajax(request):
    try:
        data = json.loads(request.body)
        item_id = data.get("item_id")
        quantity = int(data.get("quantity"))

        item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)

        if quantity > 0:
            item.quantity = quantity
            item.save()
        else:
            item.delete()

        return JsonResponse({"success": True})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})
    


@login_required
def buy_now(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    cart = get_or_create_cart(request)

    # Add 1 quantity by default
    item, created = CartItem.objects.get_or_create(
        cart=cart,
        product=product,
        defaults={'quantity': 1}
    )
    if not created:
        item.quantity += 1
        item.save()

    return redirect('accounts:checkout')








