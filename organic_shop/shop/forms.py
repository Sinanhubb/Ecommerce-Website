from django import forms
from .models import CartItem,Review

class CartAddProductForm(forms.Form):
    quantity = forms.IntegerField(
        min_value=1,
        max_value=20,
        widget=forms.NumberInput(attrs={
            'class': 'form-control border-dark-subtle input-number quantity',
            'value': '1'
        })
    )
    update = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.HiddenInput
    )

class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ['rating', 'comment']
        widgets = {
            'rating': forms.Select(choices=[(i, f"{i} Star") for i in range(1, 6)]),
            'comment': forms.Textarea(attrs={'rows': 3}),
        }
