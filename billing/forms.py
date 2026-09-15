from django import forms
from .models import Invoice, Payment, JobBilling, InvoiceItem


class InvoiceForm(forms.ModelForm):
    class Meta:
        model = Invoice
        fields = ['client', 'status', 'gst_rate', 'remarks']
        widgets = {
            'client': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'gst_rate': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'remarks': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }


class InvoiceItemForm(forms.ModelForm):
    class Meta:
        model = InvoiceItem
        fields = ['job', 'description', 'quantity', 'rate', 'paper_cost', 'printing_cost', 'plate_cost', 'additional_charges']
        widgets = {
            'job': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.TextInput(attrs={'class': 'form-control'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'rate': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'paper_cost': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'printing_cost': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'plate_cost': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'additional_charges': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }


class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ['amount', 'payment_method', 'transaction_id', 'remarks']
        widgets = {
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'payment_method': forms.Select(attrs={'class': 'form-select'}),
            'transaction_id': forms.TextInput(attrs={'class': 'form-control'}),
            'remarks': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }


class JobBillingForm(forms.ModelForm):
    class Meta:
        model = JobBilling
        fields = ['color_charge', 'front_back_charge', 'plate_charge', 'packing_charge', 'transport_charge', 'lamination_charge', 'die_charge', 'other_charges']
        widgets = {
            'color_charge': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'front_back_charge': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'plate_charge': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'packing_charge': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'transport_charge': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'lamination_charge': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'die_charge': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'other_charges': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }
