from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Q, Sum, Case, When, F, Value, OuterRef, Subquery, DecimalField
from django.db.models.functions import Coalesce
from decimal import Decimal
from datetime import date, datetime
from .models import Client, ClientAuditLog, ClientPayment
from delivery_challan.models import DeliveryChallanItem
from .forms import ClientForm, ClientPaymentForm
from production.models import Job


def _resolve_month_filter(request, job_months):
    """Work out which month the job lists should show.

    Jobs are shown month by month and default to the current month. A bad or
    unknown 'month' value falls back to the current month instead of failing.
    'all' means no month restriction.
    """
    today = date.today()
    month_param = request.GET.get('month')
    filter_year, filter_month = today.year, today.month
    selected_month = 'all'

    if month_param != 'all':
        if month_param:
            try:
                year_str, month_str = month_param.split('-')
                filter_year, filter_month = int(year_str), int(month_str)
                if not 1 <= filter_month <= 12:
                    raise ValueError
            except (ValueError, AttributeError):
                filter_year, filter_month = today.year, today.month
        selected_month = f'{filter_year:04d}-{filter_month:02d}'

    # Months offered in the filter: every month with jobs (newest first), plus
    # the current month so it can always be picked.
    month_options = [
        {'value': job_month.strftime('%Y-%m'), 'label': job_month.strftime('%B %Y')}
        for job_month in job_months
    ]
    offered_months = [option['value'] for option in month_options]
    current_month_value = today.strftime('%Y-%m')
    if current_month_value not in offered_months:
        month_options.insert(0, {
            'value': current_month_value,
            'label': today.strftime('%B %Y'),
        })
        offered_months.insert(0, current_month_value)

    # A month typed straight into the URL still needs a label and an entry in
    # the dropdown, otherwise it would look like 'All Months' is selected.
    if selected_month != 'all' and selected_month not in offered_months:
        month_options.append({
            'value': selected_month,
            'label': datetime.strptime(selected_month, '%Y-%m').strftime('%B %Y'),
        })

    return {
        'selected_month': selected_month,
        'filter_year': filter_year,
        'filter_month': filter_month,
        'month_options': month_options,
        'current_month_value': current_month_value,
        'selected_month_label': next(
            (option['label'] for option in month_options if option['value'] == selected_month),
            'All Months',
        ),
    }


@login_required
def client_list(request):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to view this page')
        return redirect('dashboard')
    
    status_filter = request.GET.get('status', 'active')
    if status_filter == 'all':
        clients = Client.objects.all()
    else:
        clients = Client.objects.filter(status=status_filter)

    # Free-text search by name, company or mobile number.
    search_query = request.GET.get('q', '').strip()
    if search_query:
        clients = clients.filter(
            Q(name__icontains=search_query)
            | Q(company__icontains=search_query)
            | Q(mobile_number__icontains=search_query)
        )

    # The Jobs / Ready for Challan / Main Challan tabs are shown month by month.
    month_filter = _resolve_month_filter(
        request, Job.objects.dates('date', 'month', order='DESC')
    )
    selected_month = month_filter['selected_month']

    if selected_month != 'all':
        month_q = Q(
            jobs__date__year=month_filter['filter_year'],
            jobs__date__month=month_filter['filter_month'],
        )
    else:
        month_q = Q()

    # Three job states, based on costing + delivery challan:
    #   - Jobs tab              : no costing, no challan (just created)
    #   - Ready for Challan     : costing added, no challan yet
    #   - Main Challan          : delivery challan created
    new_jobs_q = month_q & Q(jobs__costing__isnull=True, jobs__delivery_challan__isnull=True)
    ready_q = month_q & Q(jobs__costing__isnull=False, jobs__delivery_challan__isnull=True)
    challan_q = month_q & Q(jobs__delivery_challan__isnull=False)

    # Amount billed to a client = sum of each challan item's cost, mirroring
    # DeliveryChallanItem.manual_cost: the linked job's costing grand total,
    # falling back to the stored snapshot.
    item_cost = Case(
        When(job__costing__grand_total__isnull=False, then=F('job__costing__grand_total')),
        When(manual_cost_snapshot__gt=0, then=F('manual_cost_snapshot')),
        default=Value(Decimal('0.00')),
        output_field=DecimalField(max_digits=14, decimal_places=2),
    )
    billable_per_client = (
        DeliveryChallanItem.objects
        .filter(challan__client=OuterRef('pk'))
        .values('challan__client')
        .annotate(total=Sum(item_cost))
        .values('total')
    )
    received_per_client = (
        ClientPayment.objects
        .filter(client=OuterRef('pk'))
        .values('client')
        .annotate(total=Sum('amount'))
        .values('total')
    )
    money_field = DecimalField(max_digits=14, decimal_places=2)

    clients_annotated = clients.annotate(
        new_job_count=Count('jobs', filter=new_jobs_q, distinct=True),
        ready_job_count=Count('jobs', filter=ready_q, distinct=True),
        challan_job_count=Count('jobs', filter=challan_q, distinct=True),
        total_billable=Coalesce(
            Subquery(billable_per_client, output_field=money_field),
            Value(Decimal('0.00')),
        ),
        total_received=Coalesce(
            Subquery(received_per_client, output_field=money_field),
            Value(Decimal('0.00')),
        ),
    )

    clients_with_new_jobs = clients_annotated.filter(new_job_count__gt=0)
    clients_ready_for_challan = clients_annotated.filter(ready_job_count__gt=0)
    # A client stays on the Main Challan tab only while they still owe money
    # (billed amount greater than what has been received). Once all dues are
    # cleared they drop off this tab, but remain on the Clients list and their
    # profile page.
    clients_on_challan = clients_annotated.filter(
        challan_job_count__gt=0,
        total_billable__gt=F('total_received'),
    )

    return render(request, 'clients/client_list.html', {
        'clients': clients,
        'clients_with_new_jobs': clients_with_new_jobs,
        'clients_ready_for_challan': clients_ready_for_challan,
        'clients_on_challan': clients_on_challan,
        'status_filter': status_filter,
        'month_options': month_filter['month_options'],
        'selected_month': selected_month,
        'selected_month_label': month_filter['selected_month_label'],
        'current_month_value': month_filter['current_month_value'],
        'active_tab': request.GET.get('tab', 'clients'),
        'search_query': search_query,
    })


@login_required
def client_create(request):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to view this page')
        return redirect('dashboard')
    if request.method == 'POST':
        form = ClientForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Client created successfully')
            return redirect('client_list')
    else:
        form = ClientForm()
    return render(request, 'clients/client_form.html', {'form': form})


@login_required
def client_update(request, pk):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to view this page')
        return redirect('dashboard')
    client = get_object_or_404(Client, pk=pk)
    if request.method == 'POST':
        form = ClientForm(request.POST, instance=client)
        if form.is_valid():
            form.save()
            messages.success(request, 'Client updated successfully')
            return redirect('client_detail', pk=pk)
    else:
        form = ClientForm(instance=client)
    return render(request, 'clients/client_form.html', {'form': form})


@login_required
def client_detail(request, pk):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to view this page')
        return redirect('dashboard')
    client = get_object_or_404(Client, pk=pk)
    all_jobs = client.jobs.all().select_related('operator', 'operator__user', 'delivery_challan')

    today = date.today()

    # Jobs are shown month by month. Without a filter we show the current month.
    month_filter = _resolve_month_filter(request, all_jobs.dates('date', 'month', order='DESC'))
    selected_month = month_filter['selected_month']
    filter_year = month_filter['filter_year']
    filter_month = month_filter['filter_month']

    if selected_month == 'all':
        month_jobs = all_jobs
    else:
        month_jobs = all_jobs.filter(date__year=filter_year, date__month=filter_month)

    # Three exclusive job states, mirroring the Clients page tabs:
    #   latest  : no costing, no challan (just created)
    #   ready   : costing added, no challan yet
    #   history : challan created
    latest_jobs = month_jobs.filter(
        costing__isnull=True, delivery_challan__isnull=True
    ).order_by('-date', '-time')
    ready_jobs = month_jobs.filter(
        costing__isnull=False, delivery_challan__isnull=True
    ).order_by('-date', '-time')
    history_jobs = month_jobs.filter(
        delivery_challan__isnull=False
    ).order_by('-date', '-time')

    challans = client.delivery_challans.all().select_related('created_by').prefetch_related('items')
    payments = client.payments.all().select_related('received_by')
    total_received = sum(payment.amount for payment in payments)
    
    # Calculate total billable amount from delivery challans
    total_billable = sum(challan.total_cost for challan in challans)
    
    pending_amount = total_billable - total_received

    return render(request, 'clients/client_detail.html', {
        'client': client,
        'jobs': all_jobs,
        'latest_jobs': latest_jobs,
        'ready_jobs': ready_jobs,
        'history_jobs': history_jobs,
        'month_options': month_filter['month_options'],
        'selected_month': selected_month,
        'selected_month_label': month_filter['selected_month_label'],
        'current_month_value': month_filter['current_month_value'],
        'active_subtab': request.GET.get('subtab', 'latest'),
        'challans': challans,
        'payments': payments,
        'total_received': total_received,
        'total_billable': total_billable,
        'pending_amount': pending_amount,
        'today': today,
    })


@login_required
@transaction.atomic
def client_delete(request, pk):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to view this page')
        return redirect('dashboard')
    client = get_object_or_404(Client, pk=pk)
    if request.method == 'POST':
        # Check if client has related records
        if client.has_related_records():
            messages.error(request, 'Unable to delete because this client is linked with production records. Please archive the client instead.')
            return redirect('client_detail', pk=pk)
        
        # No related records, safe to delete permanently
        client_name = client.name
        client.delete()
        
        # Log the deletion
        ClientAuditLog.objects.create(
            client_name=client_name,
            action='deleted',
            performed_by=request.user
        )
        
        messages.success(request, 'Client deleted successfully')
        return redirect('client_list')
    return render(request, 'clients/client_delete.html', {'client': client, 'has_related_records': client.has_related_records()})


@login_required
@transaction.atomic
def client_archive(request, pk):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to view this page')
        return redirect('dashboard')
    client = get_object_or_404(Client, pk=pk)
    if request.method == 'POST':
        if client.status == 'archived':
            messages.warning(request, 'Client is already archived')
            return redirect('client_detail', pk=pk)
        
        client.status = 'archived'
        client.save()
        
        # Log the archive action
        ClientAuditLog.objects.create(
            client_name=client.name,
            action='archived',
            performed_by=request.user
        )
        
        messages.success(request, 'Client has been archived successfully')
        return redirect('client_list')
    return render(request, 'clients/client_archive.html', {'client': client})


@login_required
@transaction.atomic
def client_restore(request, pk):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to view this page')
        return redirect('dashboard')
    client = get_object_or_404(Client, pk=pk)
    if request.method == 'POST':
        if client.status == 'active':
            messages.warning(request, 'Client is already active')
            return redirect('client_detail', pk=pk)
        
        client.status = 'active'
        client.save()
        
        # Log the restore action
        ClientAuditLog.objects.create(
            client_name=client.name,
            action='restored',
            performed_by=request.user
        )
        
        messages.success(request, 'Client has been restored successfully')
        return redirect('client_list')
    return render(request, 'clients/client_restore.html', {'client': client})


@login_required
def client_payment_create(request, client_pk):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to view this page')
        return redirect('dashboard')
    client = get_object_or_404(Client, pk=client_pk)
    if request.method == 'POST':
        form = ClientPaymentForm(request.POST)
        if form.is_valid():
            payment = form.save(commit=False)
            payment.client = client
            payment.received_by = request.user
            payment.save()
            messages.success(request, 'Payment recorded successfully')
            return redirect('client_detail', pk=client_pk)
    else:
        form = ClientPaymentForm(initial={'client': client, 'payment_date': date.today()})
    return render(request, 'clients/client_payment_form.html', {'form': form, 'client': client})


@login_required
def client_payment_update(request, pk):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to view this page')
        return redirect('dashboard')
    payment = get_object_or_404(ClientPayment, pk=pk)
    if request.method == 'POST':
        form = ClientPaymentForm(request.POST, instance=payment)
        if form.is_valid():
            form.save()
            messages.success(request, 'Payment updated successfully')
            return redirect('client_detail', pk=payment.client.pk)
    else:
        form = ClientPaymentForm(instance=payment)
    return render(request, 'clients/client_payment_form.html', {'form': form, 'client': payment.client, 'is_edit': True})


@login_required
def client_payment_delete(request, pk):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to view this page')
        return redirect('dashboard')
    payment = get_object_or_404(ClientPayment, pk=pk)
    client_pk = payment.client.pk
    if request.method == 'POST':
        payment.delete()
        messages.success(request, 'Payment deleted successfully')
        return redirect('client_detail', pk=client_pk)
    return render(request, 'clients/client_payment_delete.html', {'payment': payment, 'client': payment.client})
