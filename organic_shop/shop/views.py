from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from .models import Category, Product, Cart, CartItem, Review,VariantOption,VariantValue,ProductVariant
from .forms import CartAddProductForm,ReviewForm
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Avg
import json
from accounts.models import Wishlist

def index(request):
    categories = Category.objects.filter(is_active=True)

    featured_products = Product.objects.filter(
        available=True,
        is_featured=True,
        category__is_active=True
    )[:8]

    best_selling = Product.objects.filter(
        available=True,
        category__is_active=True
    ).order_by('-sold_count')[:10]

    just_arrived = Product.objects.filter(
        available=True,
        category__is_active=True
    ).order_by('-created_at')[:10]

    most_popular = Product.objects.filter(
        available=True,
        category__is_active=True
    ).order_by('-views')[:8]

    for product in list(featured_products) + list(best_selling) + list(just_arrived) + list(most_popular):
        product.default_variant = product.variants.order_by('-stock').first()

    # ✅ wishlist items for current user
    wishlist_items = []
    if request.user.is_authenticated:
        wishlist_items = Wishlist.objects.filter(user=request.user).values_list('product_id', flat=True)

    context = {
        'categories': categories,
        'featured_products': featured_products,
        'best_selling': best_selling,
        'just_arrived': just_arrived,
        'most_popular': most_popular,
        'wishlist_items': wishlist_items,  # pass here
    }
    return render(request, 'shop/index.html', context)



def product_detail(request, slug):
    product = get_object_or_404(Product, slug=slug, available=True)

    
    default_variant = product.variants.order_by('-stock').first()

    # Increase product view count
    product.views += 1
    
    product.save()

    cart_product_form = CartAddProductForm()

    # SIMILAR PRODUCTS - get product variants of products in same category excluding this product
    similar_products = Product.objects.filter(category=product.category).exclude(id=product.id)[:4]

    # Get default/highest stock variant of similar products
    similar_variants = []
    for sp in similar_products:
        variant = sp.variants.order_by('-stock').first()
        if variant:
            similar_variants.append(variant)

    # REVIEWS and average rating
    reviews = product.reviews.all().order_by('-created_at')
    average_rating = reviews.aggregate(Avg('rating'))['rating__avg']

    # RECENTLY VIEWED 
    recently_viewed_variant_ids = request.session.get('recently_viewed_variants', [])

    # Add current product's default_variant ID to recently viewed variants list
    if default_variant and default_variant.id in recently_viewed_variant_ids:
        recently_viewed_variant_ids.remove(default_variant.id)
    if default_variant:
        recently_viewed_variant_ids.insert(0, default_variant.id)
    request.session['recently_viewed_variants'] = recently_viewed_variant_ids[:5]

   
    recently_viewed_queryset = ProductVariant.objects.filter(id__in=recently_viewed_variant_ids).exclude(id=default_variant.id)
    recently_viewed = sorted(
        recently_viewed_queryset,
        key=lambda x: recently_viewed_variant_ids.index(x.id)
    )

    # Handle review form POST
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

    # Variant options map
    all_variants = ProductVariant.objects.filter(product=product).prefetch_related('values__option')
    option_map = {}
    for variant in all_variants:
        for value in variant.values.all():
            option_name = value.option.name
            if option_name not in option_map:
                option_map[option_name] = set()
            option_map[option_name].add(value.value)
    for key in option_map:
        option_map[key] = sorted(option_map[key])

    # Variant data JSON for frontend
    variant_data = []
    for variant in all_variants:
        variant_data.append({
            'values': [v.value.lower() for v in variant.values.all()],
            'stock': variant.stock
        })

    context = {
        'product': product,
        'cart_product_form': cart_product_form,
        'similar_variants': similar_variants,           
        'reviews': reviews,
        'average_rating': average_rating,
        'review_form': review_form,
        'recently_viewed_variants': recently_viewed,   
        'variant_options': option_map,
        'all_variants': all_variants,
        'variant_data_json': json.dumps(variant_data),
        'default_variant': default_variant,
    }
    return render(request, 'shop/product_detail.html', context)

def category_detail(request, slug):
    category = get_object_or_404(Category, slug=slug)
    products = category.products.filter(available=True).prefetch_related('variants')
    category = get_object_or_404(Category, slug=slug, is_active=True)

    sort = request.GET.get('sort')
    if sort == 'price_asc':
        products = sorted(products, key=lambda p: (p.variants.order_by('-stock').first().price if p.variants.exists() else 0))
    elif sort == 'price_desc':
        products = sorted(products, key=lambda p: (p.variants.order_by('-stock').first().price if p.variants.exists() else 0), reverse=True)
    elif sort == 'newest':
        products = products.order_by('-created_at')
    elif sort == 'rating':
        products = sorted(products, key=lambda p: p.reviews.aggregate(avg=Avg('rating'))['avg'] or 0, reverse=True)

    for product in products:
        default_variant = product.variants.order_by('-stock').first()
        product.default_variant = default_variant

    # ✅ wishlist items for current user
    wishlist_items = []
    if request.user.is_authenticated:
        wishlist_items = Wishlist.objects.filter(user=request.user).values_list('product_id', flat=True)

    context = {
        'category': category,
        'products': products,
        'wishlist_items': wishlist_items,  # pass to template
    }
    return render(request, 'shop/category_detail.html', context)


@login_required(login_url='accounts:login')
def cart_add(request, product_id):
    cart = get_or_create_cart(request)
    product = get_object_or_404(Product, id=product_id)
    form = CartAddProductForm(request.POST)

    if form.is_valid():
        cd = form.cleaned_data
        quantity = cd['quantity']
        variant_sku = request.POST.get('variant_id')
        variant = None

        if variant_sku:
            variant = get_object_or_404(ProductVariant, sku=variant_sku)

        item, created = CartItem.objects.get_or_create(
            cart=cart,
            product=product,
            variant=variant,
            defaults={'quantity': quantity}
        )
        if not created:
            item.quantity += quantity
            item.save()

        return redirect('shop:cart_detail')  

    return redirect('shop:product_detail', slug=product.slug) 

@login_required
def cart_remove(request, item_id):
    cart = get_or_create_cart(request)
    item = get_object_or_404(CartItem, id=item_id, cart=cart)
    item.delete()
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

    try:
        quantity = int(request.POST.get('quantity', 1))
    except ValueError:
        quantity = 1

    variant_sku = request.POST.get('variant_id')
    variant = None

    if variant_sku:
        variant = get_object_or_404(ProductVariant, sku=variant_sku)

    # Create or update the cart item
    item, created = CartItem.objects.get_or_create(
        cart=cart,
        product=product,
        variant=variant,
        defaults={'quantity': quantity}
    )

    if not created:
        item.quantity += quantity
        item.save()

    return redirect('accounts:checkout')


@csrf_exempt
@require_POST
def get_matching_variant(request):
    try:
        data = json.loads(request.body)
        product_id = data.get("product_id")
        selected_values = data.get("selected_values", [])

        product = Product.objects.get(id=product_id)
        variants = ProductVariant.objects.filter(product=product)

        if not selected_values:
            highest_stock_variant = variants.order_by('-stock').first()
            if highest_stock_variant:
                base_price = float(highest_stock_variant.price)
                discount_price = float(highest_stock_variant.discount_price) if highest_stock_variant.discount_price else None

                return JsonResponse({
                    "success": True,
                    "sku": highest_stock_variant.sku,
                    "price": f"{base_price:.2f}",
                    "discount_price": f"{discount_price:.2f}" if discount_price else None,
                    "stock": highest_stock_variant.stock,
                    "image": highest_stock_variant.image.url if highest_stock_variant.image else "",
                    "variant_id": highest_stock_variant.id,
                })
            else:
                return JsonResponse({"success": False, "message": "No variants available for this product."})

        # Match by selected values
        for variant in variants:
            variant_values = list(variant.values.values_list("value", flat=True))
            if sorted(variant_values) == sorted(selected_values):
                base_price = float(variant.price)
                discount_price = float(variant.discount_price) if variant.discount_price else None

                return JsonResponse({
                    "success": True,
                    "sku": variant.sku,
                    "price": f"{base_price:.2f}",
                    "discount_price": f"{discount_price:.2f}" if discount_price else None,
                    "stock": variant.stock,
                    "image": variant.image.url if variant.image else "",
                    "variant_id": variant.id,
                })

        return JsonResponse({"success": False, "message": "Matching variant not found."})

    except Product.DoesNotExist:
        return JsonResponse({"success": False, "message": "Product not found."})

    except Exception as e:
        return JsonResponse({"success": False, "message": f"Error: {str(e)}"})