from django import forms
from django.forms import formset_factory
from .models import Job, JobCosting, JobAdditionalCharge


class JobForm(forms.ModelForm):
    class Meta:
        model = Job
        fields = ['client', 'job_name', 'paper_size', 'paper_gsm', 'paper_type', 'number_of_sheets', 'printing_colors', 'printing_type', 'total_sheets', 'machine', 'operator', 'remarks']
        widgets = {
            'client': forms.Select(attrs={'class': 'form-select'}),
            'job_name': forms.TextInput(attrs={'class': 'form-control'}),
            'paper_size': forms.TextInput(attrs={'class': 'form-control', 'list': 'paper_size_options'}),
            'paper_gsm': forms.NumberInput(attrs={'class': 'form-control', 'list': 'paper_gsm_options'}),
            'paper_type': forms.TextInput(attrs={'class': 'form-control', 'list': 'paper_type_options'}),
            'number_of_sheets': forms.NumberInput(attrs={'class': 'form-control', 'id': 'id_number_of_sheets'}),
            'printing_colors': forms.Select(attrs={'class': 'form-select'}),
            'printing_type': forms.Select(attrs={'class': 'form-select', 'id': 'id_printing_type'}),
            'total_sheets': forms.NumberInput(attrs={'class': 'form-control', 'readonly': True, 'id': 'id_total_sheets'}),
            'machine': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Heidelberg, Offset 1, etc.'}),
            'operator': forms.Select(attrs={'class': 'form-select'}),
            'remarks': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        instance = kwargs.get('instance', None)
        super().__init__(*args, **kwargs)

        if instance and instance.pk:
            self.fields['status'] = forms.ChoiceField(
                choices=Job.STATUS_CHOICES,
                widget=forms.Select(attrs={'class': 'form-select'})
            )


class JobCostingForm(forms.ModelForm):
    class Meta:
        model = JobCosting
        fields = ['paper_cost', 'printing_cost', 'plate_cost', 'die_charge', 'lamination_charge', 'packing_charge', 'transport_charge', 'remarks']
        widgets = {
            'paper_cost': forms.NumberInput(attrs={'class': 'form-control'}),
            'printing_cost': forms.NumberInput(attrs={'class': 'form-control'}),
            'plate_cost': forms.NumberInput(attrs={'class': 'form-control'}),
            'die_charge': forms.NumberInput(attrs={'class': 'form-control'}),
            'lamination_charge': forms.NumberInput(attrs={'class': 'form-control'}),
            'packing_charge': forms.NumberInput(attrs={'class': 'form-control'}),
            'transport_charge': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'remarks': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }


class JobAdditionalChargeForm(forms.ModelForm):
    class Meta:
        model = JobAdditionalCharge
        fields = ['label', 'amount']
        widgets = {
            'label': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Charge name'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'Amount'}),
        }


JobAdditionalChargeFormSet = formset_factory(JobAdditionalChargeForm, extra=3, can_delete=True)
