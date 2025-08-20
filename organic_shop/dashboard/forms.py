from django import forms
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory, BaseInlineFormSet

from shop.models import (
    Product, ProductVariant, VariantOption, VariantValue,
    Category, Review
)
from accounts.models import Order, OrderItem, PromoCode


# -----------------------
# Helper mixins
# -----------------------
class BootstrapFormMixin:
    """Add Bootstrap classes to all form fields automatically"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for _, field in self.fields.items():
            if not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault("class", "form-control")
            else:
                field.widget.attrs.setdefault("class", "form-check-input")


# -----------------------
# Product Form
# -----------------------
class ProductForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Product
        exclude = ['slug', 'views', 'sold_count']
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Enter product name"}),
            "description": forms.Textarea(attrs={"rows": 4, "placeholder": "Describe the product features"}),
            "category": forms.Select(attrs={"class": "form-select"}),
            "image": forms.ClearableFileInput(attrs={"accept": "image/*"}),
        }
        help_texts = {
            "name": "Choose a descriptive name that customers will recognize",
            "description": "Provide detailed information to help customers decide",
            "image": "Recommended: 800x800px JPG, PNG, WEBP",
        }

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if name and len(name) < 5:
            raise ValidationError("Product name must be at least 5 characters long")
        return name


# -----------------------
# Product Variant Form
# -----------------------
from django import forms
from django.forms.models import BaseInlineFormSet, inlineformset_factory
from shop.models import Product, ProductVariant, VariantValue


# -----------------------
# Product Variant Form
# -----------------------
class ProductVariantForm(forms.ModelForm):
    class Meta:
        model = ProductVariant
        fields = ['price', 'discount_price', 'stock', 'image', 'values']
        widgets = {
            "price": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "discount_price": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "stock": forms.NumberInput(attrs={"class": "form-control"}),
            "image": forms.ClearableFileInput(attrs={"class": "form-control"}),
            "values": forms.SelectMultiple(attrs={"class": "form-control"}),
        }

    def clean(self):
        cleaned_data = super().clean()
        values = cleaned_data.get('values')
        product = cleaned_data.get('product')
        price = cleaned_data.get('price')
        discount_price = cleaned_data.get('discount_price')

        # --- Discount price validation ---
        if discount_price and price:
            if discount_price >= price:
                raise forms.ValidationError(
                    "Discount price must be lower than the regular price."
                )

        # --- Ensure only one value per option ---
        if values:
            option_ids = [v.option_id for v in values]
            duplicates = [opt for opt in set(option_ids) if option_ids.count(opt) > 1]
            if duplicates:
                option_names = VariantValue.objects.filter(option_id__in=duplicates).values_list(
                    'option__name', flat=True
                ).distinct()
                raise forms.ValidationError(
                    f"Select only one value per option. Multiple selections found for: {', '.join(option_names)}."
                )

        # --- Prevent duplicate variant against DB ---
        if product and product.pk and values:
            existing_variants = ProductVariant.objects.filter(product=product)
            for variant in existing_variants:
                if variant.pk == self.instance.pk:
                    continue
                if set(variant.values.all()) == set(values):
                    raise forms.ValidationError(
                        "This variant combination already exists for the selected product."
                    )

        return cleaned_data


# -----------------------
# Product Variant Formset
# -----------------------
class ProductVariantFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()

        seen = []
        for form in self.forms:
            if not hasattr(form, "cleaned_data"):
                continue
            if form.cleaned_data and not form.cleaned_data.get("DELETE"):
                values = form.cleaned_data.get("values")
                if values:
                    # Convert to sorted tuple of IDs (order doesn't matter)
                    value_ids = tuple(sorted(v.pk for v in values))
                    if value_ids in seen:
                        raise forms.ValidationError(
                            "Duplicate variant combination detected within this product."
                        )
                    seen.append(value_ids)


ProductVariantFormSet = inlineformset_factory(
    Product,
    ProductVariant,
    form=ProductVariantForm,
    formset=ProductVariantFormSet,
    extra=1,
    can_delete=True,
    can_delete_extra=True,
)



# -----------------------
# Orders
# -----------------------
class OrderForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Order
        fields = ['status', 'payment_method', 'is_paid', 'promo_code']
        widgets = {
            "status": forms.Select(attrs={"class": "form-select"}),
            "payment_method": forms.Select(attrs={"class": "form-select"}),
            "is_paid": forms.CheckboxInput(),
            "promo_code": forms.Select(attrs={"class": "form-select"}),
        }


class OrderItemForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = OrderItem
        fields = ['product', 'variant', 'price', 'quantity']
        widgets = {
            "product": forms.Select(attrs={"class": "form-select", "onchange": "updateVariants(this)"}),
            "variant": forms.Select(attrs={"class": "form-select"}),
            "price": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "quantity": forms.NumberInput(attrs={"min": "1"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'product' in self.data:
            try:
                pid = int(self.data.get('product'))
                self.fields['variant'].queryset = ProductVariant.objects.filter(product_id=pid)
            except (ValueError, TypeError):
                pass
        elif self.instance.pk:
            self.fields['variant'].queryset = self.instance.product.variants.all()
        else:
            self.fields['variant'].queryset = ProductVariant.objects.none()


# -----------------------
# Promo Codes
# -----------------------
class PromoCodeForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = PromoCode
        fields = ["code", "discount_percentage", "start_date", "end_date", "usage_limit", "active"]
        widgets = {
            "code": forms.TextInput(attrs={"placeholder": "e.g., SUMMER25"}),
            "discount_percentage": forms.NumberInput(attrs={"step": "0.01", "min": "0", "max": "100"}),
            "start_date": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "end_date": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "usage_limit": forms.NumberInput(attrs={"min": "0"}),
            "active": forms.CheckboxInput(),
        }

    def clean(self):
        cleaned = super().clean()
        start, end, discount = cleaned.get("start_date"), cleaned.get("end_date"), cleaned.get("discount_percentage")

        if discount and (discount <= 0 or discount > 100):
            raise ValidationError("Discount must be between 0 and 100")

        if start and end and start >= end:
            raise ValidationError("End date must be after start date")

        return cleaned

    def clean_code(self):
        code = self.cleaned_data.get('code')
        return code.upper() if code else code


# -----------------------
# Reviews
# -----------------------
class ReviewForm(BootstrapFormMixin, forms.ModelForm):
    RATING_CHOICES = [(i, f"{i} star{'s' if i > 1 else ''}") for i in range(1, 6)]
    rating = forms.ChoiceField(
        choices=RATING_CHOICES,
        widget=forms.RadioSelect(),
        initial=5
    )

    class Meta:
        model = Review
        fields = ['product', 'user', 'rating', 'comment']
        widgets = {
            "comment": forms.Textarea(attrs={"rows": 4, "placeholder": "Share your experience"}),
        }


# -----------------------
# Categories
# -----------------------
class CategoryForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Category
        fields = '__all__'
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "e.g., Electronics, Clothing"}),
            "slug": forms.TextInput(attrs={"placeholder": "e.g., electronics, clothing"}),
            "image": forms.ClearableFileInput(attrs={"accept": "image/*"}),
        }

    def clean_slug(self):
        slug = self.cleaned_data.get('slug')
        if not slug:
            name = self.cleaned_data.get('name')
            if name:
                slug = name.lower().replace(' ', '-')
        return slug
