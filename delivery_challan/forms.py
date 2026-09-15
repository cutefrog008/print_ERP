from django import forms
from .models import DeliveryChallan, DeliveryChallanItem
from clients.models import Client
from production.models import Job
from django.utils import timezone


class ClientSelectForm(forms.Form):
    client = forms.ModelChoiceField(
        queryset=Client.objects.filter(status='active').order_by('name'),
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Select Client',
        empty_label='--- Select a Client ---'
    )


class DeliveryChallanForm(forms.ModelForm):
    class Meta:
        model = DeliveryChallan
        fields = [
            'challan_date',
            'remarks',
        ]
        widgets = {
            'challan_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'remarks': forms.Textarea(attrs={'rows': 3, 'class': 'form-control', 'placeholder': 'Any remarks (optional)'}),
        }

    def __init__(self, *args, **kwargs):
        kwargs.pop('client', None)
        super().__init__(*args, **kwargs)
        if not self.initial.get('challan_date'):
            self.initial['challan_date'] = timezone.localdate()


class JobSelectionForm(forms.Form):
    selected_jobs = forms.ModelMultipleChoiceField(
        queryset=Job.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        required=True,
        label='Select Jobs to Add'
    )

    def __init__(self, *args, **kwargs):
        client = kwargs.pop('client', None)
        exclude_jobs = kwargs.pop('exclude_jobs', None)
        super().__init__(*args, **kwargs)
        if client:
            qs = Job.objects.filter(
                client=client,
                delivery_challan__isnull=True,
                status__in=['costing_completed', 'ready_for_challan']
            ).select_related('costing', 'operator', 'operator__user').order_by('-date', '-time')
            if exclude_jobs:
                qs = qs.exclude(pk__in=exclude_jobs)
            self.fields['selected_jobs'].queryset = qs


class StatusUpdateForm(forms.Form):
    STATUS_CHOICES = [
        ('created', 'Created'),
        ('completed', 'Completed'),
    ]
    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    reason = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 2, 'class': 'form-control', 'placeholder': 'Reason (optional)'}),
        label='Reason / Notes'
    )


class CancelChallanForm(forms.Form):
    reason = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 4, 'class': 'form-control', 'placeholder': 'Please provide reason for cancelling this challan...'}),
        label='Reason for Cancellation'
    )
