from django import forms
from shop.models import Product, ProductVariant,VariantOption,VariantValue

from django import forms
from shop.models import Product, ProductVariant, VariantOption, VariantValue

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
