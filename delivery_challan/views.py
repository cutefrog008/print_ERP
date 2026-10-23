from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db import transaction
from django.db.models import Sum, Q, Count
from datetime import date
from decimal import Decimal
import calendar
from .models import DeliveryChallan, DeliveryChallanItem, DeliveryChallanAuditLog
from .forms import (
    ClientSelectForm,
    DeliveryChallanForm,
    JobSelectionForm,
    StatusUpdateForm,
    CancelChallanForm,
)
from clients.models import Client
from production.models import Job
from employees.models import Employee


def _admin_only(request):
    return request.user.role == 'admin'


def _view_allowed(request):
    return request.user.role in ('admin', 'manager')


def _snapshot_job(job):
    cost = Decimal('0.00')
    try:
        if hasattr(job, 'costing') and job.costing:
            cost = job.costing.grand_total
    except (AttributeError, ValueError, TypeError):
        pass
    return {
        'job': job,
        'job_number': job.job_number,
        'job_name': job.job_name,
        'job_date': job.date,
        'paper_size': job.paper_size,
        'paper_gsm': job.paper_gsm,
        'paper_type': job.paper_type,
        'quantity': job.number_of_sheets,
        'printing_color': job.printing_colors,
        'printing_type': job.get_printing_type_display(),
        'machine': job.machine or '',
        'operator': (
            f"{job.operator.user.first_name} {job.operator.user.last_name}".strip()
            if job.operator_id and hasattr(job.operator, 'user') else ''
        ),
        'manual_cost_snapshot': cost,
        'remarks': job.remarks or '',
    }


@login_required
def challan_list(request):
    if not _view_allowed(request):
        messages.error(request, 'You do not have permission to view Delivery Challans')
        return redirect('dashboard')

    challans = DeliveryChallan.objects.all().select_related('client', 'created_by').prefetch_related('items__job__costing')

    q = request.GET.get('q', '').strip()
    if q:
        challans = challans.filter(
            Q(challan_number__icontains=q) |
            Q(client__name__icontains=q) |
            Q(client__company__icontains=q)
        )

    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    if start_date and end_date:
        challans = challans.filter(challan_date__range=[start_date, end_date])
    elif start_date:
        challans = challans.filter(challan_date__gte=start_date)
    elif end_date:
        challans = challans.filter(challan_date__lte=end_date)

    client_id = request.GET.get('client')
    if client_id:
        challans = challans.filter(client_id=client_id)

    status = request.GET.get('status')
    if status:
        challans = challans.filter(status=status)

    clients = Client.objects.filter(status='active').order_by('name')
    today = date.today()

    return render(request, 'delivery_challan/challan_list.html', {
        'challans': challans,
        'clients': clients,
        'status_choices': DeliveryChallan.STATUS_CHOICES,
        'filters': {
            'q': q,
            'start_date': start_date or '',
            'end_date': end_date or '',
            'client': client_id or '',
            'status': status or '',
        },
        'today': today,
        'is_admin': _admin_only(request),
    })


@login_required
@transaction.atomic
def challan_create_step1(request):
    if not _admin_only(request):
        messages.error(request, 'Only Admin can create Delivery Challans')
        return redirect('delivery_challan:challan_list')

    if request.method == 'POST':
        form = ClientSelectForm(request.POST)
        if form.is_valid():
            client = form.cleaned_data['client']
            eligible = Job.objects.filter(
                client=client,
                delivery_challan__isnull=True,
                status__in=['costing_completed', 'ready_for_challan'],
            ).exists()
            if not eligible:
                messages.warning(
                    request,
                    f'No eligible jobs for {client.name}. Jobs must have costing completed and no existing challan.'
                )
                return redirect('delivery_challan:challan_create')
            return redirect('delivery_challan:challan_create_step2', client_id=client.pk)
    else:
        form = ClientSelectForm()

    eligible_clients = list(
        Job.objects.filter(
            delivery_challan__isnull=True,
            status__in=['costing_completed', 'ready_for_challan'],
        ).values_list('client_id', flat=True).distinct()
    )
    return render(request, 'delivery_challan/challan_create_step1.html', {
        'form': form,
        'eligible_clients_count': len(eligible_clients),
    })


@login_required
@transaction.atomic
def challan_create_step2(request, client_id):
    if not _admin_only(request):
        messages.error(request, 'Only Admin can create Delivery Challans')
        return redirect('delivery_challan:challan_list')

    client = get_object_or_404(Client, pk=client_id)

    eligible_qs = Job.objects.filter(
        client=client,
        delivery_challan__isnull=True,
        status__in=['costing_completed', 'ready_for_challan'],
    ).select_related('costing', 'operator', 'operator__user').order_by('-date', '-time')

    if not eligible_qs.exists():
        messages.warning(request, f'No eligible jobs found for {client.name}.')
        return redirect('delivery_challan:challan_create')

    if request.method == 'POST':
        challan_form = DeliveryChallanForm(request.POST, client=client)
        job_form = JobSelectionForm(request.POST, client=client)

        if challan_form.is_valid() and job_form.is_valid():
            selected_jobs = job_form.cleaned_data['selected_jobs']
            if not selected_jobs:
                messages.error(request, 'Please select at least one job.')
            else:
                challan = challan_form.save(commit=False)
                challan.client = client
                challan.challan_number = DeliveryChallan.generate_challan_number()
                challan.created_by = request.user
                challan.status = 'created'
                challan.save()

                for job in selected_jobs:
                    snap = _snapshot_job(job)
                    DeliveryChallanItem.objects.create(challan=challan, **snap)
                    job.delivery_challan = challan
                    if challan.status == 'completed':
                        job.dispatch_date = challan.challan_date
                        job.status = 'dispatched'
                    else:
                        job.dispatch_date = None
                        job.status = 'challan_created'
                    job.save()

                DeliveryChallanAuditLog.objects.create(
                    challan=challan,
                    action='created',
                    performed_by=request.user,
                    reason=f'Created with {selected_jobs.count()} job(s) from {client.name}'
                )

                messages.success(
                    request,
                    f'{challan.challan_number} created successfully with {selected_jobs.count()} job(s).'
                )
                return redirect('delivery_challan:challan_detail', pk=challan.pk)
        else:
            messages.error(request, 'Please fix the errors below.')
    else:
        challan_form = DeliveryChallanForm(client=client)
        job_form = JobSelectionForm(client=client)

    return render(request, 'delivery_challan/challan_create_step2.html', {
        'client': client,
        'challan_form': challan_form,
        'job_form': job_form,
        'eligible_jobs': eligible_qs,
    })


@login_required
def challan_detail(request, pk):
    if not _view_allowed(request):
        messages.error(request, 'Permission denied')
        return redirect('dashboard')

    challan = get_object_or_404(
        DeliveryChallan.objects.select_related('client', 'created_by').prefetch_related('items', 'items__job__costing', 'audit_logs', 'audit_logs__performed_by'),
        pk=pk
    )
    items = challan.items.all()
    audit_logs = challan.audit_logs.all()[:50]

    return render(request, 'delivery_challan/challan_detail.html', {
        'challan': challan,
        'items': items,
        'audit_logs': audit_logs,
        'is_admin': _admin_only(request),
        'can_edit': challan.status not in ('completed', 'cancelled'),
    })


@login_required
@transaction.atomic
def challan_edit(request, pk):
    if not _admin_only(request):
        messages.error(request, 'Only Admin can edit Delivery Challans')
        return redirect('delivery_challan:challan_list')

    challan = get_object_or_404(DeliveryChallan.objects.prefetch_related('items__job__costing'), pk=pk)
    if challan.status == 'completed':
        messages.error(request, 'Completed challans cannot be edited.')
        return redirect('delivery_challan:challan_detail', pk=pk)
    if challan.status == 'cancelled':
        messages.error(request, 'Cancelled challans cannot be edited.')
        return redirect('delivery_challan:challan_detail', pk=pk)

    if request.method == 'POST':
        form = DeliveryChallanForm(request.POST, instance=challan, client=challan.client)
        if form.is_valid():
            changed = []
            for field in form.changed_data:
                old = getattr(challan, field)
                new = form.cleaned_data[field]
                if old != new:
                    DeliveryChallanAuditLog.objects.create(
                        challan=challan,
                        action='edited',
                        field_name=field,
                        old_value=str(old) if old is not None else '',
                        new_value=str(new) if new is not None else '',
                        performed_by=request.user,
                    )
                    changed.append(field)
            form.save()
            if changed:
                messages.success(request, f'Challan updated ({", ".join(changed)}).')
            else:
                messages.info(request, 'No changes detected.')
            return redirect('delivery_challan:challan_detail', pk=pk)
    else:
        form = DeliveryChallanForm(instance=challan, client=challan.client)

    items = challan.items.all()
    return render(request, 'delivery_challan/challan_edit.html', {
        'challan': challan,
        'form': form,
        'items': items,
    })


@login_required
@transaction.atomic
def challan_add_jobs(request, pk):
    if not _admin_only(request):
        messages.error(request, 'Only Admin can edit Delivery Challans')
        return redirect('delivery_challan:challan_list')

    challan = get_object_or_404(DeliveryChallan.objects.prefetch_related('items__job__costing'), pk=pk)
    if challan.status in ('completed', 'cancelled'):
        messages.error(request, 'Cannot add jobs to completed/cancelled challan.')
        return redirect('delivery_challan:challan_detail', pk=pk)

    existing_job_ids = list(challan.items.values_list('job_id', flat=True))
    existing_job_ids = [j for j in existing_job_ids if j]

    if request.method == 'POST':
        form = JobSelectionForm(request.POST, client=challan.client, exclude_jobs=existing_job_ids)
        if form.is_valid():
            selected = form.cleaned_data['selected_jobs']
            if selected:
                for job in selected:
                    snap = _snapshot_job(job)
                    DeliveryChallanItem.objects.create(challan=challan, **snap)
                    job.delivery_challan = challan
                    if challan.status == 'completed':
                        job.dispatch_date = challan.challan_date
                        job.status = 'dispatched'
                    else:
                        job.dispatch_date = None
                        job.status = 'challan_created'
                    job.save()
                DeliveryChallanAuditLog.objects.create(
                    challan=challan,
                    action='job_added',
                    performed_by=request.user,
                    reason=f'Added {selected.count()} new job(s)'
                )
                messages.success(request, f'{selected.count()} job(s) added to challan.')
            else:
                messages.warning(request, 'No jobs selected.')
            return redirect('delivery_challan:challan_edit', pk=pk)
    else:
        form = JobSelectionForm(client=challan.client, exclude_jobs=existing_job_ids)

    eligible_qs = form.fields['selected_jobs'].queryset
    return render(request, 'delivery_challan/challan_add_jobs.html', {
        'challan': challan,
        'form': form,
        'eligible_jobs': eligible_qs,
    })


@login_required
@transaction.atomic
def challan_remove_job(request, pk, item_pk):
    if not _admin_only(request):
        messages.error(request, 'Only Admin can edit Delivery Challans')
        return redirect('delivery_challan:challan_list')

    challan = get_object_or_404(DeliveryChallan, pk=pk)
    if challan.status in ('completed', 'cancelled'):
        messages.error(request, 'Cannot modify completed/cancelled challan.')
        return redirect('delivery_challan:challan_detail', pk=pk)

    item = get_object_or_404(DeliveryChallanItem, pk=item_pk, challan=challan)
    job_id = item.job_id
    job_name = item.job_name

    item.delete()

    if job_id:
        try:
            job = Job.objects.get(pk=job_id)
            job.delivery_challan = None
            job.dispatch_date = None
            job.status = 'ready_for_challan'
            job.save()
        except Job.DoesNotExist:
            pass

    DeliveryChallanAuditLog.objects.create(
        challan=challan,
        action='job_removed',
        performed_by=request.user,
        reason=f'Removed job: {job_name}'
    )
    messages.success(request, f'Job "{job_name}" removed and returned to Ready for Challan.')

    if challan.items.count() == 0:
        messages.warning(request, 'Challan now has zero items. Consider adding jobs or cancelling it.')

    return redirect('delivery_challan:challan_edit', pk=pk)


@login_required
@transaction.atomic
def challan_status_update(request, pk):
    if not _admin_only(request):
        messages.error(request, 'Only Admin can change Challan status')
        return redirect('delivery_challan:challan_list')

    challan = get_object_or_404(DeliveryChallan, pk=pk)
    if challan.status == 'cancelled':
        messages.error(request, 'Cancelled challans cannot change status.')
        return redirect('delivery_challan:challan_detail', pk=pk)
    if challan.status == 'completed':
        messages.error(request, 'Completed challan is final.')
        return redirect('delivery_challan:challan_detail', pk=pk)

    if request.method == 'POST':
        form = StatusUpdateForm(request.POST, initial={'status': challan.status})
        if form.is_valid():
            new_status = form.cleaned_data['status']
            reason = form.cleaned_data.get('reason', '') or None
            old_status = challan.status

            if new_status != old_status:
                challan.status = new_status
                challan.save()

                if new_status == 'completed':
                    today = challan.challan_date or timezone.localdate()
                    challan.jobs.all().update(
                        status='dispatched',
                        dispatch_date=today,
                    )
                elif old_status == 'completed' and new_status == 'created':
                    challan.jobs.all().update(
                        status='ready_for_challan',
                        dispatch_date=None,
                    )

                DeliveryChallanAuditLog.objects.create(
                    challan=challan,
                    action='status_changed',
                    field_name='status',
                    old_value=old_status,
                    new_value=new_status,
                    reason=reason,
                    performed_by=request.user,
                )
                messages.success(
                    request,
                    f'Status changed from {old_status} '
                    f'to {challan.get_status_display()}'
                )
            else:
                messages.info(request, 'Status unchanged.')
            return redirect('delivery_challan:challan_detail', pk=pk)
    else:
        form = StatusUpdateForm(initial={'status': challan.status})

    return render(request, 'delivery_challan/challan_status.html', {
        'challan': challan,
        'form': form,
    })


@login_required
@transaction.atomic
def challan_print(request, pk):
    if not _view_allowed(request):
        messages.error(request, 'Permission denied')
        return redirect('dashboard')

    challan = get_object_or_404(
        DeliveryChallan.objects.select_related('client', 'created_by').prefetch_related('items', 'items__job__costing'),
        pk=pk
    )
    items = challan.items.all()

    if _admin_only(request):
        DeliveryChallanAuditLog.objects.create(
            challan=challan,
            action='printed',
            performed_by=request.user,
        )

    return render(request, 'delivery_challan/challan_print.html', {
        'challan': challan,
        'items': items,
    })


@login_required
@transaction.atomic
def challan_cancel(request, pk):
    if not _admin_only(request):
        messages.error(request, 'Only Admin can cancel Delivery Challans')
        return redirect('delivery_challan:challan_list')

    challan = get_object_or_404(DeliveryChallan, pk=pk)
    if challan.status == 'cancelled':
        messages.warning(request, 'Challan is already cancelled.')
        return redirect('delivery_challan:challan_detail', pk=pk)
    if challan.status == 'completed':
        messages.error(request, 'Completed challans cannot be cancelled.')
        return redirect('delivery_challan:challan_detail', pk=pk)

    if request.method == 'POST':
        form = CancelChallanForm(request.POST)
        if form.is_valid():
            old_status = challan.status
            reason = form.cleaned_data['reason']

            job_ids = list(challan.items.values_list('job_id', flat=True))
            job_ids = [j for j in job_ids if j]
            if job_ids:
                Job.objects.filter(pk__in=job_ids).update(
                    delivery_challan=None,
                    dispatch_date=None,
                    status='ready_for_challan',
                )

            challan.status = 'cancelled'
            challan.save()

            DeliveryChallanAuditLog.objects.create(
                challan=challan,
                action='cancelled',
                field_name='status',
                old_value=old_status,
                new_value='cancelled',
                reason=reason,
                performed_by=request.user,
            )
            messages.success(
                request,
                f'{challan.challan_number} cancelled. {len(job_ids)} job(s) returned to Ready for Challan.'
            )
            return redirect('delivery_challan:challan_detail', pk=pk)
    else:
        form = CancelChallanForm()

    items_count = challan.items.count()
    return render(request, 'delivery_challan/challan_cancel.html', {
        'challan': challan,
        'form': form,
        'items_count': items_count,
    })


@login_required
@transaction.atomic
def challan_delete(request, pk):
    if not _admin_only(request):
        messages.error(request, 'Only Admin can delete Delivery Challans')
        return redirect('delivery_challan:challan_list')

    challan = get_object_or_404(DeliveryChallan, pk=pk)
    client_id = challan.client_id

    if request.method == 'POST':
        job_ids = list(challan.items.values_list('job_id', flat=True))
        job_ids = [j for j in job_ids if j]

        challan_number = challan.challan_number

        if job_ids:
            Job.objects.filter(pk__in=job_ids).update(
                delivery_challan=None,
                dispatch_date=None,
                status='ready_for_challan',
            )

        challan.delete()

        messages.success(
            request,
            f'{challan_number} permanently deleted. {len(job_ids)} job(s) returned to Ready for Challan.'
        )
        return redirect('delivery_challan:challan_list')

    items_count = challan.items.count()
    return render(request, 'delivery_challan/challan_delete.html', {
        'challan': challan,
        'items_count': items_count,
    })


@login_required
def bulk_monthly_cleanup(request):
    if not _admin_only(request):
        messages.error(request, 'Only Admin can access Bulk Record Cleanup')
        return redirect('delivery_challan:challan_list')

    today = timezone.localdate()
    confirm = request.GET.get('confirm') == '1'

    year = request.POST.get('year') or request.GET.get('year')
    month = request.POST.get('month') or request.GET.get('month')

    try:
        year = int(year) if year else None
        month = int(month) if month else None
    except (ValueError, TypeError):
        year = None
        month = None

    months_options = []
    for m in range(1, 13):
        months_options.append((m, calendar.month_name[m]))

    min_year = today.year - 10
    max_year = today.year + 1
    years_options = list(range(max_year, min_year - 1, -1))

    context = {
        'months_options': months_options,
        'years_options': years_options,
        'selected_year': year,
        'selected_month': month,
        'preview': None,
        'confirm': confirm,
        'is_admin': True,
    }

    if year and month:
        try:
            first_day = date(year, month, 1)
            last_day_num = calendar.monthrange(year, month)[1]
            last_day = date(year, month, last_day_num)
        except ValueError:
            messages.error(request, 'Invalid month/year combination selected.')
            return render(request, 'delivery_challan/bulk_cleanup.html', context)

        preview = {
            'month_name': f"{calendar.month_name[month]} {year}",
            'first_day': first_day,
            'last_day': last_day,
        }

        challans_qs = DeliveryChallan.objects.filter(
            challan_date__gte=first_day,
            challan_date__lte=last_day,
        )
        jobs_created_qs = Job.objects.filter(
            date__gte=first_day,
            date__lte=last_day,
        )

        preview['challan_count'] = challans_qs.count()
        preview['challan_items_count'] = DeliveryChallanItem.objects.filter(challan__in=challans_qs).count()
        preview['challan_audit_count'] = DeliveryChallanAuditLog.objects.filter(challan__in=challans_qs).count()

        challan_total = Decimal('0.00')
        for ch in challans_qs.prefetch_related('items'):
            challan_total += sum((item.manual_cost or Decimal('0.00')) for item in ch.items.all())
        preview['challan_total'] = challan_total

        preview['jobs_count'] = jobs_created_qs.count()
        preview['jobs_quantity'] = jobs_created_qs.aggregate(tq=Sum('number_of_sheets'))['tq'] or 0
        preview['jobs_total'] = jobs_created_qs.filter(
            costing__isnull=False
        ).aggregate(t=Sum('costing__grand_total'))['t'] or Decimal('0.00')

        context['preview'] = preview

        if request.method == 'POST' and confirm:
            if year != int(request.POST.get('year', 0)) or month != int(request.POST.get('month', 0)):
                messages.error(request, 'Month/year mismatch. Please confirm your selection again.')
                return render(request, 'delivery_challan/bulk_cleanup.html', context)

            with transaction.atomic():
                challan_list = list(challans_qs.values_list('challan_number', flat=True))
                challan_ids = list(challans_qs.values_list('id', flat=True))

                DeliveryChallanItem.objects.filter(challan_id__in=challan_ids).delete()
                DeliveryChallanAuditLog.objects.filter(challan_id__in=challan_ids).delete()
                challans_qs.delete()

                job_ids_list = list(jobs_created_qs.values_list('id', flat=True))
                from production.models import JobAdditionalCharge, JobCosting, CostingAuditLog
                from billing.models import JobBilling
                job_costings = JobCosting.objects.filter(job_id__in=job_ids_list)
                costing_pks = list(job_costings.values_list('pk', flat=True))
                JobAdditionalCharge.objects.filter(job_costing_id__in=costing_pks).delete()
                CostingAuditLog.objects.filter(job_id__in=job_ids_list).delete()
                JobBilling.objects.filter(job_id__in=job_ids_list).delete()
                job_costings.delete()
                jobs_created_qs.delete()

                challan_n = len(challan_list)
                jobs_n = len(job_ids_list)
                messages.success(
                    request,
                    f"✅ Cleanup complete for {calendar.month_name[month]} {year}. "
                    f"Permanently deleted {challan_n} Delivery Challans and {jobs_n} Production Jobs."
                )
                return redirect('delivery_challan:bulk_monthly_cleanup')

    return render(request, 'delivery_challan/bulk_cleanup.html', context)
