from django import forms
from .models import Client, ClientPayment


class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = '__all__'
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'company': forms.TextInput(attrs={'class': 'form-control'}),
            'contact_person': forms.TextInput(attrs={'class': 'form-control'}),
            'mobile_number': forms.TextInput(attrs={'class': 'form-control'}),
            'whatsapp_number': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'gst_number': forms.TextInput(attrs={'class': 'form-control'}),
            'pan_number': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'city': forms.TextInput(attrs={'class': 'form-control'}),
            'state': forms.TextInput(attrs={'class': 'form-control'}),
            'pincode': forms.TextInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'color_1_rate': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'color_2_rate': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'color_3_rate': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'color_4_rate': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'front_back_extra': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'plate_charge': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'die_charge': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'packing_charge': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'transport_charge': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'lamination_charge': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'other_charges': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }


class ClientPaymentForm(forms.ModelForm):
    class Meta:
        model = ClientPayment
        fields = ['client', 'amount', 'payment_mode', 'payment_date', 'reference_number', 'notes']
        widgets = {
            'client': forms.Select(attrs={'class': 'form-select'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'Enter amount'}),
            'payment_mode': forms.Select(attrs={'class': 'form-select'}),
            'payment_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'reference_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Reference number (optional)'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control', 'placeholder': 'Notes (optional)'}),
        }
