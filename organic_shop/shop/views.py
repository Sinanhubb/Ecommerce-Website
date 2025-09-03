from django.shortcuts import render, get_object_or_404, redirect
from .models import Category, Product, Cart, CartItem, Review,VariantOption,VariantValue,ProductVariant
from django.views.decorators.http import require_POST
from .forms import CartAddProductForm,ReviewForm
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Avg,Subquery, OuterRef,F,Prefetch,Count
from django.db.models.functions import Coalesce
from accounts.models import Wishlist
from django.http import JsonResponse
from django.contrib import messages
import json

def index(request):
    categories = Category.objects.filter(is_active=True)
    default_variant_prefetch = Prefetch(
        'variants',
        queryset=ProductVariant.objects.order_by('-stock'),
        to_attr='default_variant_list' 
    )

    
    featured_products = Product.objects.filter(
        available=True, is_featured=True, category__is_active=True
    ).prefetch_related(default_variant_prefetch)[:8]

    best_selling = Product.objects.filter(
        available=True, category__is_active=True
    ).order_by('-sold_count').prefetch_related(default_variant_prefetch)[:10]

    just_arrived = Product.objects.filter(
        available=True, category__is_active=True
    ).order_by('-created_at').prefetch_related(default_variant_prefetch)[:10]

    most_popular = Product.objects.filter(
        available=True, category__is_active=True
    ).order_by('-views').prefetch_related(default_variant_prefetch)[:8]

   
    product_lists = [featured_products, best_selling, just_arrived, most_popular]
    for product_list in product_lists:
        for product in product_list:
            product.default_variant = product.default_variant_list[0] if product.default_variant_list else None

    wishlist_items = []
    if request.user.is_authenticated:
        wishlist_items = Wishlist.objects.filter(user=request.user).values_list('product_id', flat=True)

    context = {
        'categories': categories,
        'featured_products': featured_products,
        'best_selling': best_selling,
        'just_arrived': just_arrived,
        'most_popular': most_popular,
        'wishlist_items': wishlist_items,
    }
    return render(request, 'shop/index.html', context)


def product_detail(request, slug):
    product = get_object_or_404(
        Product.objects.annotate(
            average_rating=Avg('reviews__rating')
        ).prefetch_related(
           
            Prefetch(
                'variants',
                queryset=ProductVariant.objects.order_by('-stock').prefetch_related('values__option')
            ),
            'images', 
            Prefetch(
                'reviews',
                queryset=Review.objects.order_by('-created_at').select_related('user')
            )
        ),
        slug=slug,
        available=True
    )
    if request.method == 'POST' and request.user.is_authenticated:
        review_form = ReviewForm(request.POST)
        if review_form.is_valid():
            new_review = review_form.save(commit=False)
            new_review.product = product
            new_review.user = request.user
            new_review.save()
            messages.success(request, 'Your review has been submitted!')
            return redirect('shop:product_detail', slug=product.slug)
    else:
        review_form = ReviewForm()

    all_product_variants = list(product.variants.all())
    default_variant = all_product_variants[0] if all_product_variants else None
    reviews = list(product.reviews.all())
    average_rating = product.average_rating or 0
    product.views = F('views') + 1
    product.save(update_fields=['views'])
    product.refresh_from_db(fields=['views'])
    cart_product_form = CartAddProductForm()

    # SIMILAR PRODUCTS
    default_variant_prefetch = Prefetch(
        'variants',
        queryset=ProductVariant.objects.order_by('-stock'),
        to_attr='default_variant_list'
    )
    similar_products = Product.objects.filter(
        category=product.category
    ).exclude(id=product.id).prefetch_related(default_variant_prefetch)[:4]

    similar_variants = []
    for sp in similar_products:
        if sp.default_variant_list:
            similar_variants.append(sp.default_variant_list[0])

    # RECENTLY VIEWED
    recently_viewed_variant_ids = request.session.get('recently_viewed_variants', [])
    if default_variant and default_variant.id in recently_viewed_variant_ids:
        recently_viewed_variant_ids.remove(default_variant.id)
    if default_variant:
        recently_viewed_variant_ids.insert(0, default_variant.id)
    request.session['recently_viewed_variants'] = recently_viewed_variant_ids[:5]

    recently_viewed_queryset = ProductVariant.objects.select_related('product').filter(
        id__in=recently_viewed_variant_ids
    ).exclude(id=default_variant.id if default_variant else None)

    recently_viewed = sorted(
        recently_viewed_queryset,
        key=lambda x: recently_viewed_variant_ids.index(x.id)
    )

    # VARIANT MAP & JSON
    option_map = {}
    for variant in all_product_variants:
        for value in variant.values.all():
            option_name = value.option.name
            if option_name not in option_map:
                option_map[option_name] = set()
            option_map[option_name].add(value.value)
    for key in option_map:
        option_map[key] = sorted(list(option_map[key]))

    variant_data = [{
        'values': [v.value.lower() for v in variant.values.all()],
        'stock': variant.stock
    } for variant in all_product_variants]

    context = {
        'product': product,
        'default_variant': default_variant,
        'reviews': reviews,
        'average_rating': average_rating,
        'similar_variants': similar_variants,
        'variant_options': option_map,
        'variant_data_json': json.dumps(variant_data),
        'cart_product_form': cart_product_form,
        'review_form': review_form,
        'recently_viewed_variants': recently_viewed,
    }
    return render(request, 'shop/product_detail.html', context)


def category_detail(request, slug):
    category = get_object_or_404(Category, slug=slug, is_active=True)
    products = Product.objects.filter(category=category, available=True)

    
   
    effective_price_subquery = ProductVariant.objects.filter(
        product=OuterRef('pk')
    ).annotate(
        effective_price=Coalesce('discount_price', 'price')
    ).order_by('-stock').values('effective_price')[:1]

   
    products = products.annotate(
        sorting_price=Subquery(effective_price_subquery),
        avg_rating=Avg('reviews__rating')
    ).prefetch_related('variants')

    sort = request.GET.get('sort')
   
    if sort == 'price_asc':
        products = products.order_by('sorting_price')
    elif sort == 'price_desc':
        products = products.order_by('-sorting_price')
   
    elif sort == 'newest':
        products = products.order_by('-created_at')
    elif sort == 'rating':
    
        products = products.order_by(F('avg_rating').desc(nulls_last=True))

    for product in products:
    
        all_variants = sorted(product.variants.all(), key=lambda v: v.stock, reverse=True)
        product.default_variant = all_variants[0] if all_variants else None

    wishlist_items = []
    if request.user.is_authenticated:
        wishlist_items = Wishlist.objects.filter(user=request.user).values_list('product_id', flat=True)

    context = {
        'category': category,
        'products': products,
        'wishlist_items': wishlist_items,
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

      
        variant_id = request.POST.get('variant_id')
        variant = None
        if variant_id:
            variant = get_object_or_404(ProductVariant, id=variant_id, product=product)

        available_stock = variant.stock if variant else product.stock
        if quantity > available_stock:
            messages.error(request, f"Only {available_stock} left in stock.")
            return redirect('shop:product_detail', slug=product.slug)

   
        item, created = CartItem.objects.get_or_create(
            cart=cart,
            product=product,
            variant=variant,
            defaults={'quantity': 0}  
        )


        item.quantity = min(item.quantity + quantity, available_stock)
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
        
        cart, _ = Cart.objects.get_or_create(user=request.user)
    else:
       
        if not request.session.session_key:
            request.session.create()
        session_key = request.session.session_key
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
    variant_pk = request.POST.get('variant_id') 
    
    if product.variants.exists() and not variant_pk:
        messages.error(request, "Please select a product option to buy now.")
        return redirect('shop:product_detail', slug=product.slug)

    try:
        quantity = int(request.POST.get('quantity', 1))
        if quantity <= 0:
            raise ValueError("Quantity must be at least 1.")

        variant = None
        stock_to_check = product.stock 
        variant_sku_for_session = None 

        if variant_pk:
            variant = get_object_or_404(ProductVariant, pk=variant_pk, product=product)
            stock_to_check = variant.stock
            variant_sku_for_session = variant.sku

       
        if quantity > stock_to_check:
            messages.error(request, f"Sorry, only {stock_to_check} are available in stock.")
            return redirect('shop:product_detail', slug=product.slug)

        
        request.session['direct_checkout'] = {
            'product_id': product.id,
            'variant_id': variant_sku_for_session, 
            'quantity': quantity
        }
        
        
        request.session.pop('applied_promo_code', None)

        return redirect('accounts:checkout')

    except ValueError as e:
        messages.error(request, str(e))
        return redirect('shop:product_detail', slug=product.slug)
    except ProductVariant.DoesNotExist:
        messages.error(request, "The selected product option does not exist.")
        return redirect('shop:product_detail', slug=product.slug)


@require_POST
def get_matching_variant(request):
    try:
        data = json.loads(request.body)
        product_id = data.get("product_id")
        selected_values = data.get("selected_values", [])
        product = get_object_or_404(Product, id=product_id)

       
        if not product.variants.exists():
            
            base_price = float(product.price)
            discount_price = float(product.discount_price) if product.discount_price else None

            return JsonResponse({
                "success": True,
                "sku": None, 
                "price": f"{base_price:.2f}",
                "discount_price": f"{discount_price:.2f}" if discount_price else None,
                "stock": product.stock,
                "image": product.image.url if product.image else "",
                "variant_id": None, 
                "is_variant_product": False,
            })

        
        variant = None
        if not selected_values:
            
            variant = product.variants.order_by('-stock').first()
        else:
        
            num_selected = len(selected_values)
            variant = ProductVariant.objects.filter(
                product_id=product_id,
                values__value__in=selected_values
            ).annotate(
                value_count=Count('values')
            ).filter(
                value_count=num_selected
            ).first()

        if not variant:
            return JsonResponse({"success": False, "message": "This combination is not available."})

       
        base_price = float(variant.price)
        discount_price = float(variant.discount_price) if variant.discount_price else None
        
        image_url = variant.image.url if variant.image else (product.image.url if product.image else "")

        return JsonResponse({
            "success": True,
            "sku": variant.sku,
            "price": f"{base_price:.2f}",
            "discount_price": f"{discount_price:.2f}" if discount_price else None,
            "stock": variant.stock,
            "image": image_url,
            "variant_id": variant.id,
            "is_variant_product": True,
        })

    except Exception as e:
        return JsonResponse({"success": False, "message": "An unexpected error occurred."})