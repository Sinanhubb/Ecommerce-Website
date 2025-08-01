from django import forms
from .models import Address,User
import re

class AddressForm(forms.ModelForm):
    class Meta:
        model = Address
        fields = ['full_name', 'phone', 'address_line', 'city', 'postal_code', 'country']
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'address_line': forms.TextInput(attrs={'class': 'form-control'}),
            'city': forms.TextInput(attrs={'class': 'form-control'}),
            'postal_code': forms.TextInput(attrs={'class': 'form-control'}),
            'country': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def clean_phone(self):
        phone = self.cleaned_data['phone']
        if not re.match(r'^[6-9]\d{9}$', phone):
            raise forms.ValidationError("Enter a valid 10-digit Indian phone number.")
        return phone

    def clean_postal_code(self):
        code = self.cleaned_data['postal_code']
        if not re.match(r'^\d{6}$', code):
            raise forms.ValidationError("Enter a valid 6-digit postal code.")
        return code



class UserProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }

        def clean_email(self):
            email = self.cleaned_data['email']
            if User.objects.exclude(pk=self.instance.pk).filter(email=email).exists():
                raise forms.ValidationError("Email is already in use.")
            return email




