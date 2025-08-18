from django import forms
from shop.models import Product, ProductVariant,VariantOption,VariantValue

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            'name',
            'slug',
            'category',
            'description',
            'price',
            'discount_price',
            'stock',
            'available',
            'is_featured',
            'image',
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
        }

from django import forms
from shop.models import ProductVariant, VariantValue

class ProductVariantForm(forms.ModelForm):
    values = forms.ModelMultipleChoiceField(
        queryset=VariantValue.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=True,
        label="Variant Options",
        help_text="Select exactly one value per option (e.g. one Color, one Size)."
    )

    class Meta:
        model = ProductVariant
        fields = ['product', 'values', 'sku', 'price', 'discount_price', 'stock', 'image']

    def clean(self):
        cleaned_data = super().clean()
        values = cleaned_data.get('values')

        if values:
            option_ids = [v.option_id for v in values]
            # Check if any VariantOption has more than one VariantValue selected
            duplicates = [option_id for option_id in set(option_ids) if option_ids.count(option_id) > 1]
            if duplicates:
                # Get names of the VariantOptions with multiple values selected
                option_names = VariantValue.objects.filter(option_id__in=duplicates).values_list('option__name', flat=True).distinct()
                raise forms.ValidationError(
                    f"Select only one value per option. Multiple selections found for: {', '.join(option_names)}."
                )

        # Also keep your duplicate variant check (optional)
        product = cleaned_data.get('product')
        if product and values:
            existing_variants = ProductVariant.objects.filter(product=product)
            for variant in existing_variants:
                if variant.pk == self.instance.pk:
                    continue
                if set(variant.values.all()) == set(values):
                    raise forms.ValidationError(
                        "This variant combination already exists for the selected product."
                    )
        return cleaned_data
from django import forms
from accounts.models import Order, OrderItem

class OrderForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ['status', 'payment_method', 'is_paid', 'promo_code']


class OrderItemForm(forms.ModelForm):
    class Meta:
        model = OrderItem
        fields = ['product', 'variant', 'price', 'quantity']



from accounts.models import PromoCode

class PromoCodeForm(forms.ModelForm):
    class Meta:
        model = PromoCode
        fields = ["code", "discount_percentage", "start_date", "end_date", "usage_limit", "active"]
        widgets = {
            "start_date": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "end_date": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }

from shop.models import Review

class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ['product', 'user', 'rating', 'comment']
