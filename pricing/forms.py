from django import forms
from .models import PaperPricing, PrintingPricing, PlatePricing, AdditionalCharge


class PaperPricingForm(forms.ModelForm):
    class Meta:
        model = PaperPricing
        fields = '__all__'
        widgets = {
            'client': forms.Select(attrs={'class': 'form-select'}),
            'paper_size': forms.Select(attrs={'class': 'form-select'}),
            'paper_size_custom': forms.TextInput(attrs={'class': 'form-control'}),
            'paper_gsm': forms.Select(attrs={'class': 'form-select'}),
            'paper_gsm_custom': forms.NumberInput(attrs={'class': 'form-control'}),
            'paper_type': forms.Select(attrs={'class': 'form-select'}),
            'paper_type_custom': forms.TextInput(attrs={'class': 'form-control'}),
            'quantity_min': forms.NumberInput(attrs={'class': 'form-control'}),
            'quantity_max': forms.NumberInput(attrs={'class': 'form-control'}),
            'price_per_sheet': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }


class PrintingPricingForm(forms.ModelForm):
    class Meta:
        model = PrintingPricing
        fields = '__all__'
        widgets = {
            'client': forms.Select(attrs={'class': 'form-select'}),
            'colors': forms.Select(attrs={'class': 'form-select'}),
            'quantity_min': forms.NumberInput(attrs={'class': 'form-control'}),
            'quantity_max': forms.NumberInput(attrs={'class': 'form-control'}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'minimum_charge': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }


class PlatePricingForm(forms.ModelForm):
    class Meta:
        model = PlatePricing
        fields = '__all__'
        widgets = {
            'client': forms.Select(attrs={'class': 'form-select'}),
            'colors': forms.Select(attrs={'class': 'form-select'}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }


class AdditionalChargeForm(forms.ModelForm):
    class Meta:
        model = AdditionalCharge
        fields = '__all__'
        widgets = {
            'client': forms.Select(attrs={'class': 'form-select'}),
            'name': forms.Select(attrs={'class': 'form-select'}),
            'name_custom': forms.TextInput(attrs={'class': 'form-control'}),
            'charge_type': forms.Select(attrs={'class': 'form-select'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
