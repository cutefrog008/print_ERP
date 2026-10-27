from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Q
from datetime import date
from .models import Client, ClientAuditLog, ClientPayment
from .forms import ClientForm, ClientPaymentForm


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

    # Clients that still have at least one job NOT yet on a delivery challan.
    # Creating a challan links the job to it, so the client drops out of this
    # tab; creating another job for that client brings it back.
    clients_with_jobs = clients.annotate(
        pending_job_count=Count('jobs', filter=Q(jobs__delivery_challan__isnull=True))
    ).filter(pending_job_count__gt=0)

    return render(request, 'clients/client_list.html', {
        'clients': clients,
        'clients_with_jobs': clients_with_jobs,
        'status_filter': status_filter,
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

    new_jobs = all_jobs.filter(delivery_challan__isnull=True).order_by('-date', '-time')
    history_jobs = all_jobs.filter(delivery_challan__isnull=False).order_by('-date', '-time')

    challans = client.delivery_challans.all().select_related('created_by').prefetch_related('items')
    payments = client.payments.all().select_related('received_by')
    total_received = sum(payment.amount for payment in payments)
    
    # Calculate total billable amount from delivery challans
    total_billable = sum(challan.total_cost for challan in challans)
    
    pending_amount = total_billable - total_received
    
    today = date.today()
    return render(request, 'clients/client_detail.html', {
        'client': client,
        'jobs': all_jobs,
        'new_jobs': new_jobs,
        'history_jobs': history_jobs,
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
