from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from datetime import date
from .models import Job, JobCosting, JobAdditionalCharge, CostingAuditLog
from .forms import JobForm, JobCostingForm, JobAdditionalChargeForm, JobAdditionalChargeFormSet


@login_required
def job_list(request):
    today = date.today()
    if request.user.role == 'employee':
        if not hasattr(request.user, 'employee_profile'):
            messages.error(request, 'Permission denied')
            return redirect('dashboard')
        jobs = Job.objects.filter(date=today, operator=request.user.employee_profile)
    else:
        selected_date = today
        raw_date = request.GET.get('date')
        if raw_date:
            try:
                from datetime import datetime
                selected_date = datetime.strptime(raw_date, '%Y-%m-%d').date()
            except (ValueError, TypeError):
                selected_date = today
        jobs = Job.objects.filter(date=selected_date)
    return render(request, 'production/job_list.html', {'jobs': jobs, 'today': today})


@login_required
def job_create(request):
    if request.method == 'POST':
        form = JobForm(request.POST, user=request.user)
        if form.is_valid():
            job = form.save(commit=False)
            job.created_by = request.user
            job.status = 'pending_costing'
            job.save()
            messages.success(request, 'Job created successfully')
            return redirect('job_list')
    else:
        form = JobForm(user=request.user)
    return render(request, 'production/job_form.html', {'form': form})


@login_required
def job_update(request, pk):
    job = get_object_or_404(Job, pk=pk)
    today = date.today()
    if job.date != today and request.user.role != 'admin':
        messages.error(request, 'This job is locked. Only admin can edit old jobs.')
        return redirect('job_list')
    
    # Get client_pk from query params to redirect back to client detail
    client_pk = request.GET.get('client_pk')
    
    if request.method == 'POST':
        form = JobForm(request.POST, instance=job, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Job updated successfully')
            if client_pk:
                return redirect('client_detail', pk=client_pk)
            return redirect('job_list')
    else:
        form = JobForm(instance=job, user=request.user)
    return render(request, 'production/job_form.html', {'form': form, 'job': job, 'client_pk': client_pk})


@login_required
def job_cancel(request, pk):
    if request.user.role != 'admin':
        messages.error(request, 'Only admin can cancel jobs')
        return redirect('job_list')
    job = get_object_or_404(Job, pk=pk)
    job.status = 'cancelled'
    job.save()
    messages.success(request, 'Job cancelled successfully')
    return redirect('job_list')


@login_required
def job_delete(request, pk):
    if request.user.role != 'admin':
        messages.error(request, 'Only admin can delete jobs')
        return redirect('job_list')
    job = get_object_or_404(Job, pk=pk)
    if request.method == 'POST':
        job.delete()
        messages.success(request, 'Job deleted successfully')
        return redirect('job_list')
    return render(request, 'production/job_delete.html', {'job': job})


@login_required
def job_detail(request, pk):
    job = get_object_or_404(Job, pk=pk)
    costing = getattr(job, 'costing', None)
    return render(request, 'production/job_detail.html', {'job': job, 'costing': costing})


@login_required
@transaction.atomic
def job_costing_create(request, pk):
    if request.user.role != 'admin':
        messages.error(request, 'Only admin can add costing')
        return redirect('job_list')
    job = get_object_or_404(Job, pk=pk)
    if hasattr(job, 'costing'):
        messages.warning(request, 'Costing already exists for this job')
        return redirect('job_costing_update', pk=pk)

    # Get client_pk from query params to redirect back to client detail
    client_pk = request.GET.get('client_pk')

    if request.method == 'POST':
        form = JobCostingForm(request.POST)
        formset = JobAdditionalChargeFormSet(request.POST, prefix='charges')
        if form.is_valid() and formset.is_valid():
            costing = form.save(commit=False)
            costing.job = job
            costing.created_by = request.user
            costing.save()

            for charge_form in formset:
                if charge_form.cleaned_data and not charge_form.cleaned_data.get('DELETE'):
                    charge = charge_form.save(commit=False)
                    charge.job_costing = costing
                    charge.save()

            job.status = 'ready_for_challan'
            job.save()

            messages.success(request, 'Costing added successfully - Job is now Ready for Challan')
            if client_pk:
                return redirect('client_detail', pk=client_pk)
            return redirect('job_detail', pk=pk)
    else:
        form = JobCostingForm()
        formset = JobAdditionalChargeFormSet(prefix='charges')

    return render(request, 'production/job_costing_form.html', {'form': form, 'formset': formset, 'job': job, 'is_edit': False, 'client_pk': client_pk})


@login_required
@transaction.atomic
def job_costing_update(request, pk):
    if request.user.role != 'admin':
        messages.error(request, 'Only admin can edit costing')
        return redirect('job_list')
    job = get_object_or_404(Job, pk=pk)
    costing = get_object_or_404(JobCosting, job=job)

    # Get client_pk from query params to redirect back to client detail
    client_pk = request.GET.get('client_pk')

    if request.method == 'POST':
        form = JobCostingForm(request.POST, instance=costing)
        formset = JobAdditionalChargeFormSet(request.POST, prefix='charges')
        if form.is_valid() and formset.is_valid():
            for field in form.changed_data:
                old_value = getattr(costing, field)
                new_value = form.cleaned_data[field]
                if old_value != new_value:
                    CostingAuditLog.objects.create(
                        job=job,
                        field_name=field,
                        old_value=str(old_value),
                        new_value=str(new_value),
                        changed_by=request.user
                    )

            form.save()

            # Delete all existing additional charges
            costing.additional_charges.all().delete()
            
            # Add new additional charges from formset
            for charge_form in formset:
                if charge_form.cleaned_data and not charge_form.cleaned_data.get('DELETE'):
                    charge = charge_form.save(commit=False)
                    charge.job_costing = costing
                    charge.save()

            if job.status == 'pending_costing':
                job.status = 'ready_for_challan'
                job.save()

            messages.success(request, 'Costing updated successfully')
            if client_pk:
                return redirect('client_detail', pk=client_pk)
            return redirect('job_detail', pk=pk)
    else:
        form = JobCostingForm(instance=costing)
        # Initialize formset with existing charges
        initial_data = [{'label': charge.label, 'amount': charge.amount} for charge in costing.additional_charges.all()]
        formset = JobAdditionalChargeFormSet(initial=initial_data, prefix='charges')

    return render(request, 'production/job_costing_form.html', {'form': form, 'formset': formset, 'job': job, 'is_edit': True, 'costing': costing, 'client_pk': client_pk})


@login_required
@transaction.atomic
def job_additional_charge_add(request, pk):
    if request.user.role != 'admin':
        messages.error(request, 'Only admin can add charges')
        return redirect('job_list')
    job = get_object_or_404(Job, pk=pk)
    costing = get_object_or_404(JobCosting, job=job)

    if request.method == 'POST':
        form = JobAdditionalChargeForm(request.POST)
        if form.is_valid():
            charge = form.save(commit=False)
            charge.job_costing = costing
            charge.save()

            costing.save()

            messages.success(request, 'Additional charge added successfully')
            return redirect('job_costing_update', pk=pk)
    else:
        form = JobAdditionalChargeForm()

    return render(request, 'production/job_additional_charge_form.html', {'form': form, 'job': job, 'costing': costing})


@login_required
@transaction.atomic
def job_additional_charge_delete(request, pk, charge_pk):
    if request.user.role != 'admin':
        messages.error(request, 'Only admin can delete charges')
        return redirect('job_list')
    job = get_object_or_404(Job, pk=pk)
    costing = get_object_or_404(JobCosting, job=job)
    charge = get_object_or_404(JobAdditionalCharge, pk=charge_pk, job_costing=costing)

    charge.delete()
    costing.save()

    messages.success(request, 'Additional charge deleted successfully')
    return redirect('job_costing_update', pk=pk)
