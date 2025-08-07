from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from .models import Category, Product, Cart, CartItem, Review,VariantOption,VariantValue,ProductVariant
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



from django.db.models import Avg  # make sure this is at the top

def product_detail(request, slug):
    product = get_object_or_404(Product, slug=slug, available=True)

    # 🔧 Step 1: Get default variant with highest stock
    default_variant = product.get_default_variant()

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

    if product.id in recently_viewed_ids:
        recently_viewed_ids.remove(product.id)
    recently_viewed_ids.insert(0, product.id)
    request.session['recently_viewed'] = recently_viewed_ids[:5]

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

    # Rebuild session tracking
    recent = request.session.get('recently_viewed', [])
    if product.id in recent:
        recent.remove(product.id)
    recent.insert(0, product.id)
    request.session['recently_viewed'] = recent[:5]

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

    
    variant_data = []
    for variant in all_variants:
        values = [v.value for v in variant.values.all()]
        variant_data.append({
            'values': [v.value.lower() for v in variant.values.all()],
            'stock': variant.stock
        })

    context = {
        'product': product,
        'cart_product_form': cart_product_form,
        'similar_products': similar_products,
        'reviews': reviews,
        'average_rating': average_rating,
        'review_form': review_form,
        'recently_viewed': recently_viewed,
        'variant_options': option_map,
        'all_variants': all_variants,
        'variant_data_json': json.dumps(variant_data), 
        'default_variant': all_variants.order_by('-stock').first(),
    }
    return render(request, 'shop/product_detail.html', context)



def category_detail(request, slug):
    category = get_object_or_404(Category, slug=slug)
    products = category.products.filter(available=True).prefetch_related('variants')

    for product in products:
        # Get the variant with the highest stock or first one as default
        default_variant = product.variants.order_by('-stock').first()
        product.default_variant = default_variant

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

        # If no selected values, return highest stock variant
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
