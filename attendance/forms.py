from django import forms
from django.utils import timezone
from django.db.models import Sum
from .models import Attendance, EmployeeAdvanceTransaction
from employees.models import Employee


class AttendanceForm(forms.ModelForm):
    employees = forms.ModelMultipleChoiceField(
        queryset=Employee.objects.filter(status='active'),
        widget=forms.CheckboxSelectMultiple,
        required=True,
        label="Select Employees"
    )

    class Meta:
        model = Attendance
        fields = ['date', 'time', 'in_time', 'out_time', 'status', 'remarks']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'in_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'out_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'remarks': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['date'].initial = timezone.localdate()
        self.fields['time'].initial = timezone.localtime().time()
        self.fields['in_time'].initial = '09:00'
        self.fields['out_time'].initial = '17:30'


class AddAdvanceForm(forms.ModelForm):
    class Meta:
        model = EmployeeAdvanceTransaction
        fields = ['employee', 'amount', 'transaction_date', 'remarks']
        widgets = {
            'transaction_date': forms.DateInput(attrs={'type': 'date'}),
            'remarks': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['transaction_date'].initial = timezone.localdate()
    
    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount <= 0:
            raise forms.ValidationError('Amount must be greater than 0.')
        return amount
    
    def save(self, commit=True, user=None):
        instance = super().save(commit=False)
        instance.transaction_type = 'TAKEN'
        if user:
            instance.created_by = user
        if commit:
            instance.save()
        return instance


class RecordRepaymentForm(forms.ModelForm):
    class Meta:
        model = EmployeeAdvanceTransaction
        fields = ['employee', 'amount', 'transaction_date', 'remarks']
        widgets = {
            'transaction_date': forms.DateInput(attrs={'type': 'date'}),
            'remarks': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['transaction_date'].initial = timezone.localdate()
    
    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount <= 0:
            raise forms.ValidationError('Amount must be greater than 0.')
        return amount
    
    def clean(self):
        cleaned_data = super().clean()
        employee = cleaned_data.get('employee')
        amount = cleaned_data.get('amount')
        
        if employee and amount:
            # Calculate current pending balance
            taken = EmployeeAdvanceTransaction.objects.filter(
                employee=employee,
                transaction_type='TAKEN'
            ).aggregate(total=Sum('amount'))['total'] or 0
            
            returned = EmployeeAdvanceTransaction.objects.filter(
                employee=employee,
                transaction_type='REPAYMENT'
            ).aggregate(total=Sum('amount'))['total'] or 0
            
            pending = taken - returned
            
            if amount > pending:
                raise forms.ValidationError(
                    f'Repayment amount cannot be greater than the current pending advance of ₹{pending}.'
                )
        
        return cleaned_data
    
    def save(self, commit=True, user=None):
        instance = super().save(commit=False)
        instance.transaction_type = 'REPAYMENT'
        if user:
            instance.created_by = user
        if commit:
            instance.save()
        return instance


class EditTransactionForm(forms.ModelForm):
    class Meta:
        model = EmployeeAdvanceTransaction
        fields = ['amount', 'transaction_date', 'remarks']
        widgets = {
            'transaction_date': forms.DateInput(attrs={'type': 'date'}),
            'remarks': forms.Textarea(attrs={'rows': 3}),
        }
    
    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount <= 0:
            raise forms.ValidationError('Amount must be greater than 0.')
        return amount
    
    def clean(self):
        cleaned_data = super().clean()
        amount = cleaned_data.get('amount')
        instance = self.instance
        
        if amount and instance.transaction_type == 'REPAYMENT':
            # Calculate pending balance excluding this transaction
            employee = instance.employee
            taken = EmployeeAdvanceTransaction.objects.filter(
                employee=employee,
                transaction_type='TAKEN'
            ).aggregate(total=Sum('amount'))['total'] or 0
            
            returned = EmployeeAdvanceTransaction.objects.filter(
                employee=employee,
                transaction_type='REPAYMENT'
            ).exclude(id=instance.id).aggregate(total=Sum('amount'))['total'] or 0
            
            pending = taken - returned
            
            if amount > pending:
                raise forms.ValidationError(
                    f'Repayment amount cannot be greater than the current pending advance of ₹{pending}.'
                )
        
        return cleaned_data
