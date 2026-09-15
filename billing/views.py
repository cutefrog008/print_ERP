from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db import transaction
from .models import Invoice, Payment, JobBilling, InvoiceItem, InvoiceAuditLog
from production.models import Job
from clients.models import Client
from .forms import InvoiceForm, PaymentForm, JobBillingForm, InvoiceItemForm


@login_required
def invoice_list(request):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to view this page')
        return redirect('dashboard')
    invoices = Invoice.objects.all()
    return render(request, 'billing/invoice_list.html', {'invoices': invoices})


@login_required
@transaction.atomic
def invoice_create(request):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to view this page')
        return redirect('dashboard')
    if request.method == 'POST':
        form = InvoiceForm(request.POST)
        if form.is_valid():
            invoice = form.save(commit=False)
            invoice.created_by = request.user
            invoice.invoice_number = f"INV-{timezone.now().year}-{Invoice.objects.count() + 1:04d}"
            invoice.save()
            messages.success(request, 'Invoice created successfully')
            return redirect('invoice_detail', pk=invoice.pk)
    else:
        form = InvoiceForm()
    return render(request, 'billing/invoice_form.html', {'form': form, 'is_edit': False})


@login_required
@transaction.atomic
def invoice_update(request, pk):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to view this page')
        return redirect('dashboard')
    invoice = get_object_or_404(Invoice, pk=pk)
    if request.method == 'POST':
        form = InvoiceForm(request.POST, instance=invoice)
        if form.is_valid():
            # Track changes for audit log
            changed_fields = []
            for field in form.changed_data:
                old_value = getattr(invoice, field)
                new_value = form.cleaned_data[field]
                if old_value != new_value:
                    InvoiceAuditLog.objects.create(
                        invoice=invoice,
                        edited_by=request.user,
                        field=field,
                        old_value=str(old_value),
                        new_value=str(new_value),
                    )
            # Save invoice
            form.save()
            # Recalculate totals
            invoice.calculate_totals()
            messages.success(request, 'Invoice updated successfully')
            return redirect('invoice_detail', pk=invoice.pk)
    else:
        form = InvoiceForm(instance=invoice)
    return render(request, 'billing/invoice_form.html', {'form': form, 'is_edit': True, 'invoice': invoice})


@login_required
def invoice_detail(request, pk):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to view this page')
        return redirect('dashboard')
    invoice = get_object_or_404(Invoice, pk=pk)
    items = invoice.items.all()
    payments = invoice.payments.all()
    audit_logs = invoice.audit_logs.all()
    return render(request, 'billing/invoice_detail.html', {
        'invoice': invoice,
        'items': items,
        'payments': payments,
        'audit_logs': audit_logs,
    })


@login_required
@transaction.atomic
def invoice_item_add(request, invoice_pk):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to view this page')
        return redirect('dashboard')
    invoice = get_object_or_404(Invoice, pk=invoice_pk)
    if request.method == 'POST':
        form = InvoiceItemForm(request.POST)
        if form.is_valid():
            item = form.save(commit=False)
            item.invoice = invoice
            
            # If a job is selected, pull manual costing from the job
            if item.job and hasattr(item.job, 'costing'):
                costing = item.job.costing
                item.paper_cost = costing.paper_cost
                item.printing_cost = costing.printing_cost
                item.plate_cost = costing.plate_cost
                item.additional_charges = sum(charge.amount for charge in costing.additional_charges.all())
                # Set rate to grand_total if not provided
                if not item.rate:
                    item.rate = costing.grand_total
            
            item.save()
            invoice.calculate_totals()
            messages.success(request, 'Item added successfully')
            return redirect('invoice_detail', pk=invoice_pk)
    else:
        form = InvoiceItemForm()
    return render(request, 'billing/invoice_item_form.html', {'form': form, 'invoice': invoice})


@login_required
@transaction.atomic
def invoice_item_update(request, invoice_pk, item_pk):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to view this page')
        return redirect('dashboard')
    invoice = get_object_or_404(Invoice, pk=invoice_pk)
    item = get_object_or_404(InvoiceItem, pk=item_pk, invoice=invoice)
    if request.method == 'POST':
        form = InvoiceItemForm(request.POST, instance=item)
        if form.is_valid():
            form.save()
            invoice.calculate_totals()
            messages.success(request, 'Item updated successfully')
            return redirect('invoice_detail', pk=invoice_pk)
    else:
        form = InvoiceItemForm(instance=item)
    return render(request, 'billing/invoice_item_form.html', {'form': form, 'invoice': invoice, 'item': item})


@login_required
@transaction.atomic
def invoice_item_delete(request, invoice_pk, item_pk):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to view this page')
        return redirect('dashboard')
    invoice = get_object_or_404(Invoice, pk=invoice_pk)
    item = get_object_or_404(InvoiceItem, pk=item_pk, invoice=invoice)
    item.delete()
    invoice.calculate_totals()
    messages.success(request, 'Item deleted successfully')
    return redirect('invoice_detail', pk=invoice_pk)


@login_required
@transaction.atomic
def payment_create(request, invoice_pk):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to view this page')
        return redirect('dashboard')
    invoice = get_object_or_404(Invoice, pk=invoice_pk)
    if request.method == 'POST':
        form = PaymentForm(request.POST)
        if form.is_valid():
            payment = form.save(commit=False)
            payment.invoice = invoice
            payment.received_by = request.user
            payment.save()
            invoice.paid_amount += payment.amount
            if invoice.paid_amount >= invoice.total_amount:
                invoice.status = 'paid'
            elif invoice.paid_amount > 0:
                invoice.status = 'partial'
            invoice.save()
            messages.success(request, 'Payment recorded successfully')
            return redirect('invoice_detail', pk=invoice.pk)
    else:
        form = PaymentForm()
    return render(request, 'billing/payment_form.html', {'form': form, 'invoice': invoice})


@login_required
@transaction.atomic
def job_billing_create(request, job_pk):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to view this page')
        return redirect('dashboard')
    job = get_object_or_404(Job, pk=job_pk)
    if hasattr(job, 'billing'):
        messages.warning(request, 'Job already has billing')
        return redirect('job_list')
    if request.method == 'POST':
        form = JobBillingForm(request.POST)
        if form.is_valid():
            billing = form.save(commit=False)
            billing.job = job
            billing.calculated_by = request.user
            billing.calculated_at = timezone.now()
            billing.total_charge = (
                billing.color_charge +
                billing.front_back_charge +
                billing.plate_charge +
                billing.packing_charge +
                billing.transport_charge +
                billing.lamination_charge +
                billing.die_charge +
                (billing.other_charges or 0)
            )
            billing.save()
            messages.success(request, 'Job billing calculated successfully')
            return redirect('job_list')
    else:
        initial = {
            'color_charge': job.client.color_1_rate if job.printing_colors == 1 else
                            job.client.color_2_rate if job.printing_colors == 2 else
                            job.client.color_3_rate if job.printing_colors == 3 else
                            job.client.color_4_rate,
            'front_back_charge': job.client.front_back_extra if job.printing_type == 'front_back' else 0,
            'plate_charge': job.client.plate_charge,
            'packing_charge': job.client.packing_charge,
            'transport_charge': job.client.transport_charge,
            'lamination_charge': job.client.lamination_charge,
            'die_charge': job.client.die_charge,
            'other_charges': job.client.other_charges,
        }
        form = JobBillingForm(initial=initial)
    return render(request, 'billing/job_billing_form.html', {'form': form, 'job': job})
