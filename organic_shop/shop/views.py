from django.shortcuts import render, get_object_or_404, redirect
from .models import Category, Product, Cart, CartItem, Review,VariantOption,VariantValue,ProductVariant
from django.views.decorators.http import require_POST
from .forms import CartAddProductForm,ReviewForm
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Avg,Subquery, OuterRef,F,Prefetch
from django.db.models.functions import Coalesce
from accounts.models import Wishlist
from django.http import JsonResponse
from django.contrib import messages
import json

def index(request):
    categories = Category.objects.filter(is_active=True)

    # 2. Define a reusable Prefetch object to get the highest-stocked variant
    default_variant_prefetch = Prefetch(
        'variants',
        queryset=ProductVariant.objects.order_by('-stock'),
        to_attr='default_variant_list' # This creates a temporary attribute
    )

    # 3. Apply this Prefetch to all your product queries
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

    # 4. Attach the default variant from the prefetched data (NO database queries here)
    product_lists = [featured_products, best_selling, just_arrived, most_popular]
    for product_list in product_lists:
        for product in product_list:
            # Get the first variant from the list we fetched, or None if the list is empty
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
    # This single, efficient query fetches the product AND all related data we need.
    product = get_object_or_404(
        Product.objects.prefetch_related(
            # Prefetch all variants AND their nested values/options in one go
            Prefetch(
                'variants',
                queryset=ProductVariant.objects.order_by('-stock').prefetch_related('values__option')
            ),
            'images',        # Prefetch all additional product images
            'reviews__user'  # Prefetch all reviews and the user who wrote them
        ),
        slug=slug,
        available=True
    )

    # Get the default variant from the data we already fetched (NO new query)
    all_product_variants = list(product.variants.all())
    default_variant = all_product_variants[0] if all_product_variants else None

    # Safely update view count using F()
    product.views = F('views') + 1
    product.save(update_fields=['views'])
    product.refresh_from_db(fields=['views']) # Gets the updated value from the DB

    # --- The rest of the view logic is now much cleaner and faster ---
    cart_product_form = CartAddProductForm()

    # SIMILAR PRODUCTS (your existing optimized code is great)
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

    # REVIEWS (No new DB query here)
    reviews = sorted(product.reviews.all(), key=lambda r: r.created_at, reverse=True)
    average_rating = sum(r.rating for r in reviews) / len(reviews) if reviews else 0

    # RECENTLY VIEWED (Session logic remains the same)
    recently_viewed_variant_ids = request.session.get('recently_viewed_variants', [])
    if default_variant and default_variant.id in recently_viewed_variant_ids:
        recently_viewed_variant_ids.remove(default_variant.id)
    if default_variant:
        recently_viewed_variant_ids.insert(0, default_variant.id)
    request.session['recently_viewed_variants'] = recently_viewed_variant_ids[:5]

    recently_viewed_queryset = ProductVariant.objects.select_related('product').filter(
        id__in=recently_viewed_variant_ids
    )
    if default_variant:
        recently_viewed_queryset = recently_viewed_queryset.exclude(id=default_variant.id)

    recently_viewed = sorted(
        recently_viewed_queryset,
        key=lambda x: recently_viewed_variant_ids.index(x.id)
    )

    # REVIEW FORM (Logic remains the same)
    review_form = ReviewForm()
    if request.method == 'POST' and request.user.is_authenticated:
        # Handle form post
        pass

    # VARIANT MAP & JSON (No new DB queries here, runs on prefetched data)
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
        # Make sure all your other necessary context variables are here
    }
    return render(request, 'shop/product_detail.html', context)

# def product_detail(request, slug):
#     product = get_object_or_404(Product, slug=slug, available=True)

    
#     default_variant = product.variants.order_by('-stock').first()

#     # Increase product view count
#     product.views = F('views') + 1
#     product.save(update_fields=['views']) 

#     cart_product_form = CartAddProductForm()

#     # The new, fast Prefetch solution
#     default_variant_prefetch = Prefetch(
#         'variants',
#         queryset=ProductVariant.objects.order_by('-stock'),
#         to_attr='default_variant_list'
#     )

#     similar_products = Product.objects.filter(
#         category=product.category
#     ).exclude(id=product.id).prefetch_related(default_variant_prefetch)[:4]

# # This loop now runs on data already in memory, making no database queries
#     similar_variants = []
#     for sp in similar_products:
#         if sp.default_variant_list:
#             similar_variants.append(sp.default_variant_list[0])

#     # REVIEWS and average rating
#     reviews = product.reviews.all().order_by('-created_at')
#     average_rating = reviews.aggregate(Avg('rating'))['rating__avg']

#     # RECENTLY VIEWED 
#     recently_viewed_variant_ids = request.session.get('recently_viewed_variants', [])

#     # Add current product's default_variant ID to recently viewed variants list
#     if default_variant and default_variant.id in recently_viewed_variant_ids:
#         recently_viewed_variant_ids.remove(default_variant.id)
#     if default_variant:
#         recently_viewed_variant_ids.insert(0, default_variant.id)
#     request.session['recently_viewed_variants'] = recently_viewed_variant_ids[:5]

#     if default_variant:
#      recently_viewed_queryset = ProductVariant.objects.filter(
#         id__in=recently_viewed_variant_ids
#     ).exclude(id=default_variant.id)
#     else:
#         recently_viewed_queryset = ProductVariant.objects.filter(
#             id__in=recently_viewed_variant_ids
#         )

#     recently_viewed = sorted(
#     recently_viewed_queryset,
#     key=lambda x: recently_viewed_variant_ids.index(x.id)
# )
#     # Handle review form POST
#     review_form = None
#     if request.method == 'POST' and request.user.is_authenticated:
#         review_form = ReviewForm(request.POST)
#         if review_form.is_valid():
#             review = review_form.save(commit=False)
#             review.user = request.user
#             review.product = product
#             review.save()
#             return redirect('shop:product_detail', slug=slug)
#     else:
#         review_form = ReviewForm()

#     # Variant options map
#     all_variants = ProductVariant.objects.filter(product=product).prefetch_related('values__option')
#     option_map = {}
#     for variant in all_variants:
#         for value in variant.values.all():
#             option_name = value.option.name
#             if option_name not in option_map:
#                 option_map[option_name] = set()
#             option_map[option_name].add(value.value)
#     for key in option_map:
#         option_map[key] = sorted(option_map[key])

#     # Variant data JSON for frontend
#     variant_data = []
#     for variant in all_variants:
#         variant_data.append({
#             'values': [v.value.lower() for v in variant.values.all()],
#             'stock': variant.stock
#         })

#     context = {
#         'product': product,
#         'cart_product_form': cart_product_form,
#         'similar_variants': similar_variants,           
#         'reviews': reviews,
#         'average_rating': average_rating,
#         'review_form': review_form,
#         'recently_viewed_variants': recently_viewed,   
#         'variant_options': option_map,
#         'all_variants': all_variants,
#         'variant_data_json': json.dumps(variant_data),
#         'default_variant': default_variant,
#     }
#     return render(request, 'shop/product_detail.html', context)




def category_detail(request, slug):
    category = get_object_or_404(Category, slug=slug, is_active=True)
    products = Product.objects.filter(category=category, available=True)

    
    # It finds the 'effective_price' which is the discount_price or the regular price.
    effective_price_subquery = ProductVariant.objects.filter(
        product=OuterRef('pk')
    ).annotate(
        effective_price=Coalesce('discount_price', 'price')
    ).order_by('-stock').values('effective_price')[:1]

    # 3. Annotate the main queryset with this new 'sorting_price'
    products = products.annotate(
        sorting_price=Subquery(effective_price_subquery),
        avg_rating=Avg('reviews__rating')
    ).prefetch_related('variants')

    sort = request.GET.get('sort')
    # 4. Use the new 'sorting_price' field for ordering
    if sort == 'price_asc':
        products = products.order_by('sorting_price')
    elif sort == 'price_desc':
        products = products.order_by('-sorting_price')
    # ... rest of the function is the same ...
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
            
            variant = get_object_or_404(ProductVariant, id=variant_id)
        

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
        
        session_key = request.session.session_key
        if session_key:
            anon_cart = Cart.objects.filter(session_key=session_key, user__isnull=True).first()
            if anon_cart:
                user_cart, created = Cart.objects.get_or_create(user=request.user)
                for item in anon_cart.items.all():
                    existing_item = user_cart.items.filter(product=item.product, variant=item.variant).first()
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
    # This is the variant's primary key (pk) from the form
    variant_pk = request.POST.get('variant_id') 
    
    # A variant MUST be selected if the product has options
    if product.variants.exists() and not variant_pk:
        messages.error(request, "Please select a product option to buy now.")
        return redirect('shop:product_detail', slug=product.slug)

    try:
        quantity = int(request.POST.get('quantity', 1))
        if quantity <= 0:
            raise ValueError("Quantity must be at least 1.")

        variant = None
        stock_to_check = product.stock 
        variant_sku_for_session = None # The checkout view expects the variant's SKU

        if variant_pk:
            variant = get_object_or_404(ProductVariant, pk=variant_pk, product=product)
            stock_to_check = variant.stock
            variant_sku_for_session = variant.sku

        # Check if the requested quantity is available
        if quantity > stock_to_check:
            messages.error(request, f"Sorry, only {stock_to_check} are available in stock.")
            return redirect('shop:product_detail', slug=product.slug)

        # Set the session data for the checkout view. This completely bypasses the cart.
        request.session['direct_checkout'] = {
            'product_id': product.id,
            'variant_id': variant_sku_for_session, # This is the SKU, which the checkout view expects
            'quantity': quantity
        }
        
        # Clear any old promo code when starting a new direct purchase
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

        product = Product.objects.get(id=product_id)
        variants = ProductVariant.objects.filter(product=product)

        # ✅ Case 1: Product has NO variants (normal product)
        if not variants.exists():
            base_price = float(product.price)
            discount_price = float(product.discount_price) if product.discount_price else None

            return JsonResponse({
                "success": True,
                "sku": None,
                "price": f"{base_price:.2f}",
                "discount_price": f"{discount_price:.2f}" if discount_price else None,
                "stock": product.stock,
                "image": product.image.url if product.image else "",
                "variant_id": None,   # No variant ID
                "is_variant_product": False,
            })

        # ✅ Case 2: Product HAS variants
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
                    "is_variant_product": True,
                })
            else:
                return JsonResponse({"success": False, "message": "No variants available for this product."})

        # ✅ Case 3: Match by selected values
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
                    "is_variant_product": True,
                })

        return JsonResponse({"success": False, "message": "Matching variant not found."})

    except Product.DoesNotExist:
        return JsonResponse({"success": False, "message": "Product not found."})

    except Exception as e:
        return JsonResponse({"success": False, "message": f"Error: {str(e)}"})
