from django import forms
from django.forms import formset_factory
from .models import Job, JobCosting, JobAdditionalCharge


class JobForm(forms.ModelForm):
    PAPER_SIZE_SELECT_CHOICES = Job.PAPER_SIZE_CHOICES + (('custom', 'Custom...'),)
    PAPER_GSM_SELECT_CHOICES = Job.PAPER_GSM_CHOICES + (('custom', 'Custom...'),)
    PAPER_TYPE_SELECT_CHOICES = Job.PAPER_TYPE_CHOICES + (('custom', 'Custom...'),)

    paper_size_select = forms.ChoiceField(
        choices=PAPER_SIZE_SELECT_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select', 'data-toggle-field': 'paper_size_custom'})
    )
    paper_size_custom = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter custom size (e.g. 14x20)'})
    )

    paper_gsm_select = forms.ChoiceField(
        choices=PAPER_GSM_SELECT_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select', 'data-toggle-field': 'paper_gsm_custom'})
    )
    paper_gsm_custom = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Enter custom GSM (e.g. 150)'})
    )

    paper_type_select = forms.ChoiceField(
        choices=PAPER_TYPE_SELECT_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select', 'data-toggle-field': 'paper_type_custom'})
    )
    paper_type_custom = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter custom paper type'})
    )

    class Meta:
        model = Job
        fields = ['client', 'job_name', 'number_of_sheets', 'printing_colors', 'printing_type', 'total_sheets', 'machine', 'operator', 'remarks']
        widgets = {
            'client': forms.Select(attrs={'class': 'form-select'}),
            'job_name': forms.TextInput(attrs={'class': 'form-control'}),
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

        # Employees log jobs under their own name: pre-fill and lock the operator
        if not instance or not instance.pk:
            if self.user and self.user.role == 'employee':
                profile = getattr(self.user, 'employee_profile', None)
                if profile:
                    self.fields['operator'].initial = profile
                    self.fields['operator'].disabled = True
        elif instance and instance.operator:
            # If editing, and it's an employee, they shouldn't change the operator either
            if self.user and self.user.role == 'employee':
                self.fields['operator'].disabled = True

        preset_sizes = [c[0] for c in Job.PAPER_SIZE_CHOICES]
        preset_gsms = [str(c[0]) for c in Job.PAPER_GSM_CHOICES]
        preset_types = [c[0] for c in Job.PAPER_TYPE_CHOICES]

        if instance and instance.pk:
            if instance.paper_size in preset_sizes:
                self.fields['paper_size_select'].initial = instance.paper_size
            else:
                self.fields['paper_size_select'].initial = 'custom'
                self.fields['paper_size_custom'].initial = instance.paper_size

            if str(instance.paper_gsm) in preset_gsms:
                self.fields['paper_gsm_select'].initial = str(instance.paper_gsm)
            else:
                self.fields['paper_gsm_select'].initial = 'custom'
                self.fields['paper_gsm_custom'].initial = instance.paper_gsm

            if instance.paper_type in preset_types:
                self.fields['paper_type_select'].initial = instance.paper_type
            else:
                self.fields['paper_type_select'].initial = 'custom'
                self.fields['paper_type_custom'].initial = instance.paper_type

            self.fields['status'] = forms.ChoiceField(
                choices=Job.STATUS_CHOICES,
                widget=forms.Select(attrs={'class': 'form-select'})
            )
        else:
            self.fields['paper_size_select'].initial = preset_sizes[0] if preset_sizes else ''
            self.fields['paper_gsm_select'].initial = preset_gsms[0] if preset_gsms else ''
            self.fields['paper_type_select'].initial = preset_types[0] if preset_types else ''

    def clean(self):
        cleaned_data = super().clean()

        paper_size_sel = cleaned_data.get('paper_size_select')
        paper_size_cust = cleaned_data.get('paper_size_custom')
        if paper_size_sel == 'custom':
            if not paper_size_cust:
                self.add_error('paper_size_custom', 'Please enter custom paper size.')
            else:
                cleaned_data['paper_size'] = paper_size_cust.strip()
        elif paper_size_sel:
            cleaned_data['paper_size'] = paper_size_sel
        else:
            self.add_error('paper_size_select', 'Please select or enter paper size.')

        paper_gsm_sel = cleaned_data.get('paper_gsm_select')
        paper_gsm_cust = cleaned_data.get('paper_gsm_custom')
        if paper_gsm_sel == 'custom':
            if paper_gsm_cust is None:
                self.add_error('paper_gsm_custom', 'Please enter custom paper GSM.')
            else:
                cleaned_data['paper_gsm'] = paper_gsm_cust
        elif paper_gsm_sel and paper_gsm_sel != 'custom':
            try:
                cleaned_data['paper_gsm'] = int(paper_gsm_sel)
            except (ValueError, TypeError):
                self.add_error('paper_gsm_select', 'Invalid GSM value.')
        else:
            self.add_error('paper_gsm_select', 'Please select or enter paper GSM.')

        paper_type_sel = cleaned_data.get('paper_type_select')
        paper_type_cust = cleaned_data.get('paper_type_custom')
        if paper_type_sel == 'custom':
            if not paper_type_cust:
                self.add_error('paper_type_custom', 'Please enter custom paper type.')
            else:
                cleaned_data['paper_type'] = paper_type_cust.strip()
        elif paper_type_sel:
            cleaned_data['paper_type'] = paper_type_sel
        else:
            self.add_error('paper_type_select', 'Please select or enter paper type.')

        return cleaned_data

    def save(self, commit=True):
        job = super().save(commit=False)
        job.paper_size = self.cleaned_data['paper_size']
        job.paper_gsm = self.cleaned_data['paper_gsm']
        job.paper_type = self.cleaned_data['paper_type']
        if commit:
            job.save()
        return job


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
