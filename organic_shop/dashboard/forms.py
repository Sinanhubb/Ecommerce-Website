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
# shop/forms.py

class ProductVariantForm(forms.ModelForm):
    class Meta:
        model = ProductVariant
        fields = ['price', 'discount_price', 'stock', 'image']
        widgets = {
            "price": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "discount_price": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "stock": forms.NumberInput(attrs={"class": "form-control"}),
            "image": forms.ClearableFileInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.option_fields = []

        # Get all available option types (e.g., Color, Size)
        options = VariantOption.objects.all()

        for option in options:
            field_name = f'option_{option.pk}'
            self.fields[field_name] = forms.ModelChoiceField(
                label=option.name,
                queryset=VariantValue.objects.filter(option=option),
                # ---- CHANGE 1: Make the field NOT required ----
                required=False,
                # ---- CHANGE 2: Add a user-friendly empty label ----
                empty_label=f"Select {option.name}...",
                widget=forms.Select(attrs={'class': 'form-select'})
            )
            self.option_fields.append(field_name)

            if self.instance and self.instance.pk:
                initial_value = self.instance.values.filter(option=option).first()
                if initial_value:
                    self.fields[field_name].initial = initial_value

    def get_option_fields(self):
        """Helper method to pass dynamic fields to the template."""
        return [self[field] for field in self.option_fields]

    def get_static_fields(self):
        """Helper for static fields."""
        static_field_names = ['price', 'discount_price', 'stock', 'image', 'id', 'DELETE']
        return [self[field] for field in static_field_names if field in self.fields]

    def clean(self):
        cleaned_data = super().clean()
        price = cleaned_data.get('price')
        discount_price = cleaned_data.get('discount_price')

        if discount_price and price and discount_price >= price:
            self.add_error('discount_price', "Discount price must be lower than the regular price.")

        # ---- CHANGE 3: Gather ONLY the selected values ----
        selected_values = []
        for field_name in self.option_fields:
            # Only append if a value was actually selected
            if cleaned_data.get(field_name):
                selected_values.append(cleaned_data[field_name])
        
        # ---- CHANGE 4: Ensure at least one option is chosen for a variant ----
        # If the form is not being deleted and has no selected options, it's invalid.
        if not self.cleaned_data.get("DELETE") and not selected_values:
            raise forms.ValidationError(
                "Each variant must have at least one option (e.g., a Color or Size) selected."
            )

        # Store them for the formset to use
        cleaned_data['values'] = selected_values
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        
        if commit:
            instance.save()

        if 'values' in self.cleaned_data:
            instance.values.set(self.cleaned_data['values'])
            if commit:
                self.save_m2m()

        return instance

# -----------------------
# UPDATED Product Variant Formset
# -----------------------
class CustomProductVariantFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return

        seen = []
        for form in self.forms:
            if not hasattr(form, "cleaned_data") or form.cleaned_data.get("DELETE"):
                continue

            # 'values' is now populated by the form's clean method
            values = form.cleaned_data.get("values")
            if values:
                value_ids = tuple(sorted(v.pk for v in values))
                if value_ids in seen:
                    raise forms.ValidationError(
                        
                    )
                seen.append(value_ids)


ProductVariantFormSet = inlineformset_factory(
    Product,
    ProductVariant,
    form=ProductVariantForm,
    formset=CustomProductVariantFormSet,
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
        fields = ['name', 'image','is_active']
        exclude = ['slug']
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "e.g., Electronics, Clothing"}),
            "image": forms.ClearableFileInput(attrs={"accept": "image/*"}),
        }