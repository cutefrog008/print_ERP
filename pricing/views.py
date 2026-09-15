from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from clients.models import Client
from .models import PaperPricing, PrintingPricing, PlatePricing, AdditionalCharge, PricingHistory
from .forms import PaperPricingForm, PrintingPricingForm, PlatePricingForm, AdditionalChargeForm
from .services import PricingService


@login_required
def client_pricing_config(request, client_id):
    """Main pricing configuration page for a client."""
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to view this page')
        return redirect('dashboard')
    
    client = get_object_or_404(Client, pk=client_id)
    
    # Check pricing completeness
    pricing_status = PricingService.check_pricing_completeness(client)
    
    # Get all pricing for this client
    paper_pricing = PaperPricing.objects.filter(client=client)
    printing_pricing = PrintingPricing.objects.filter(client=client)
    plate_pricing = PlatePricing.objects.filter(client=client)
    additional_charges = AdditionalCharge.objects.filter(client=client)
    
    context = {
        'client': client,
        'pricing_status': pricing_status,
        'paper_pricing': paper_pricing,
        'printing_pricing': printing_pricing,
        'plate_pricing': plate_pricing,
        'additional_charges': additional_charges,
    }
    
    return render(request, 'pricing/client_pricing_config.html', context)


# Paper Pricing Views
@login_required
def paper_pricing_list(request, client_id):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to view this page')
        return redirect('dashboard')
    
    client = get_object_or_404(Client, pk=client_id)
    paper_pricing = PaperPricing.objects.filter(client=client)
    
    return render(request, 'pricing/paper_pricing_list.html', {
        'client': client,
        'paper_pricing': paper_pricing
    })


@login_required
def paper_pricing_create(request, client_id):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to view this page')
        return redirect('dashboard')
    
    client = get_object_or_404(Client, pk=client_id)
    
    if request.method == 'POST':
        form = PaperPricingForm(request.POST)
        if form.is_valid():
            pricing = form.save(commit=False)
            pricing.client = client
            pricing.save()
            messages.success(request, 'Paper pricing created successfully')
            return redirect('paper_pricing_list', client_id=client_id)
    else:
        form = PaperPricingForm(initial={'client': client})
    
    return render(request, 'pricing/paper_pricing_form.html', {
        'form': form,
        'client': client,
        'is_edit': False
    })


@login_required
def paper_pricing_update(request, client_id, pk):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to view this page')
        return redirect('dashboard')
    
    client = get_object_or_404(Client, pk=client_id)
    pricing = get_object_or_404(PaperPricing, pk=pk, client=client)
    
    if request.method == 'POST':
        form = PaperPricingForm(request.POST, instance=pricing)
        if form.is_valid():
            # Record changes
            old_values = {
                'price_per_sheet': pricing.price_per_sheet,
                'quantity_min': pricing.quantity_min,
                'quantity_max': pricing.quantity_max,
            }
            
            updated_pricing = form.save()
            
            # Record pricing history
            for field, old_value in old_values.items():
                new_value = getattr(updated_pricing, field)
                if old_value != new_value:
                    PricingService.record_pricing_change(
                        updated_pricing, field, old_value, new_value, request.user
                    )
            
            messages.success(request, 'Paper pricing updated successfully')
            return redirect('paper_pricing_list', client_id=client_id)
    else:
        form = PaperPricingForm(instance=pricing)
    
    return render(request, 'pricing/paper_pricing_form.html', {
        'form': form,
        'client': client,
        'is_edit': True
    })


@login_required
def paper_pricing_delete(request, client_id, pk):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to view this page')
        return redirect('dashboard')
    
    client = get_object_or_404(Client, pk=client_id)
    pricing = get_object_or_404(PaperPricing, pk=pk, client=client)
    
    if request.method == 'POST':
        pricing.delete()
        messages.success(request, 'Paper pricing deleted successfully')
        return redirect('paper_pricing_list', client_id=client_id)
    
    return render(request, 'pricing/paper_pricing_delete.html', {
        'pricing': pricing,
        'client': client
    })


# Printing Pricing Views
@login_required
def printing_pricing_list(request, client_id):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to view this page')
        return redirect('dashboard')
    
    client = get_object_or_404(Client, pk=client_id)
    printing_pricing = PrintingPricing.objects.filter(client=client)
    
    return render(request, 'pricing/printing_pricing_list.html', {
        'client': client,
        'printing_pricing': printing_pricing
    })


@login_required
def printing_pricing_create(request, client_id):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to view this page')
        return redirect('dashboard')
    
    client = get_object_or_404(Client, pk=client_id)
    
    if request.method == 'POST':
        form = PrintingPricingForm(request.POST)
        if form.is_valid():
            pricing = form.save(commit=False)
            pricing.client = client
            pricing.save()
            messages.success(request, 'Printing pricing created successfully')
            return redirect('printing_pricing_list', client_id=client_id)
    else:
        form = PrintingPricingForm(initial={'client': client})
    
    return render(request, 'pricing/printing_pricing_form.html', {
        'form': form,
        'client': client,
        'is_edit': False
    })


@login_required
def printing_pricing_update(request, client_id, pk):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to view this page')
        return redirect('dashboard')
    
    client = get_object_or_404(Client, pk=client_id)
    pricing = get_object_or_404(PrintingPricing, pk=pk, client=client)
    
    if request.method == 'POST':
        form = PrintingPricingForm(request.POST, instance=pricing)
        if form.is_valid():
            # Record changes
            old_values = {
                'price': pricing.price,
                'minimum_charge': pricing.minimum_charge,
                'quantity_min': pricing.quantity_min,
                'quantity_max': pricing.quantity_max,
            }
            
            updated_pricing = form.save()
            
            # Record pricing history
            for field, old_value in old_values.items():
                new_value = getattr(updated_pricing, field)
                if old_value != new_value:
                    PricingService.record_pricing_change(
                        updated_pricing, field, old_value, new_value, request.user
                    )
            
            messages.success(request, 'Printing pricing updated successfully')
            return redirect('printing_pricing_list', client_id=client_id)
    else:
        form = PrintingPricingForm(instance=pricing)
    
    return render(request, 'pricing/printing_pricing_form.html', {
        'form': form,
        'client': client,
        'is_edit': True
    })


@login_required
def printing_pricing_delete(request, client_id, pk):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to view this page')
        return redirect('dashboard')
    
    client = get_object_or_404(Client, pk=client_id)
    pricing = get_object_or_404(PrintingPricing, pk=pk, client=client)
    
    if request.method == 'POST':
        pricing.delete()
        messages.success(request, 'Printing pricing deleted successfully')
        return redirect('printing_pricing_list', client_id=client_id)
    
    return render(request, 'pricing/printing_pricing_delete.html', {
        'pricing': pricing,
        'client': client
    })


# Plate Pricing Views
@login_required
def plate_pricing_list(request, client_id):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to view this page')
        return redirect('dashboard')
    
    client = get_object_or_404(Client, pk=client_id)
    plate_pricing = PlatePricing.objects.filter(client=client)
    
    return render(request, 'pricing/plate_pricing_list.html', {
        'client': client,
        'plate_pricing': plate_pricing
    })


@login_required
def plate_pricing_create(request, client_id):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to view this page')
        return redirect('dashboard')
    
    client = get_object_or_404(Client, pk=client_id)
    
    if request.method == 'POST':
        form = PlatePricingForm(request.POST)
        if form.is_valid():
            pricing = form.save(commit=False)
            pricing.client = client
            pricing.save()
            messages.success(request, 'Plate pricing created successfully')
            return redirect('plate_pricing_list', client_id=client_id)
    else:
        form = PlatePricingForm(initial={'client': client})
    
    return render(request, 'pricing/plate_pricing_form.html', {
        'form': form,
        'client': client,
        'is_edit': False
    })


@login_required
def plate_pricing_update(request, client_id, pk):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to view this page')
        return redirect('dashboard')
    
    client = get_object_or_404(Client, pk=client_id)
    pricing = get_object_or_404(PlatePricing, pk=pk, client=client)
    
    if request.method == 'POST':
        form = PlatePricingForm(request.POST, instance=pricing)
        if form.is_valid():
            # Record changes
            old_value = pricing.price
            updated_pricing = form.save()
            
            # Record pricing history
            if old_value != updated_pricing.price:
                PricingService.record_pricing_change(
                    updated_pricing, 'price', old_value, updated_pricing.price, request.user
                )
            
            messages.success(request, 'Plate pricing updated successfully')
            return redirect('plate_pricing_list', client_id=client_id)
    else:
        form = PlatePricingForm(instance=pricing)
    
    return render(request, 'pricing/plate_pricing_form.html', {
        'form': form,
        'client': client,
        'is_edit': True
    })


@login_required
def plate_pricing_delete(request, client_id, pk):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to view this page')
        return redirect('dashboard')
    
    client = get_object_or_404(Client, pk=client_id)
    pricing = get_object_or_404(PlatePricing, pk=pk, client=client)
    
    if request.method == 'POST':
        pricing.delete()
        messages.success(request, 'Plate pricing deleted successfully')
        return redirect('plate_pricing_list', client_id=client_id)
    
    return render(request, 'pricing/plate_pricing_delete.html', {
        'pricing': pricing,
        'client': client
    })


# Additional Charges Views
@login_required
def additional_charges_list(request, client_id):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to view this page')
        return redirect('dashboard')
    
    client = get_object_or_404(Client, pk=client_id)
    additional_charges = AdditionalCharge.objects.filter(client=client)
    
    return render(request, 'pricing/additional_charges_list.html', {
        'client': client,
        'additional_charges': additional_charges
    })


@login_required
def additional_charge_create(request, client_id):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to view this page')
        return redirect('dashboard')
    
    client = get_object_or_404(Client, pk=client_id)
    
    if request.method == 'POST':
        form = AdditionalChargeForm(request.POST)
        if form.is_valid():
            charge = form.save(commit=False)
            charge.client = client
            charge.save()
            messages.success(request, 'Additional charge created successfully')
            return redirect('additional_charges_list', client_id=client_id)
    else:
        form = AdditionalChargeForm(initial={'client': client})
    
    return render(request, 'pricing/additional_charge_form.html', {
        'form': form,
        'client': client,
        'is_edit': False
    })


@login_required
def additional_charge_update(request, client_id, pk):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to view this page')
        return redirect('dashboard')
    
    client = get_object_or_404(Client, pk=client_id)
    charge = get_object_or_404(AdditionalCharge, pk=pk, client=client)
    
    if request.method == 'POST':
        form = AdditionalChargeForm(request.POST, instance=charge)
        if form.is_valid():
            # Record changes
            old_values = {
                'amount': charge.amount,
                'charge_type': charge.charge_type,
                'is_active': charge.is_active,
            }
            
            updated_charge = form.save()
            
            # Record pricing history
            for field, old_value in old_values.items():
                new_value = getattr(updated_charge, field)
                if old_value != new_value:
                    PricingService.record_pricing_change(
                        updated_charge, field, old_value, new_value, request.user
                    )
            
            messages.success(request, 'Additional charge updated successfully')
            return redirect('additional_charges_list', client_id=client_id)
    else:
        form = AdditionalChargeForm(instance=charge)
    
    return render(request, 'pricing/additional_charge_form.html', {
        'form': form,
        'client': client,
        'is_edit': True
    })


@login_required
def additional_charge_delete(request, client_id, pk):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to view this page')
        return redirect('dashboard')
    
    client = get_object_or_404(Client, pk=client_id)
    charge = get_object_or_404(AdditionalCharge, pk=pk, client=client)
    
    if request.method == 'POST':
        charge.delete()
        messages.success(request, 'Additional charge deleted successfully')
        return redirect('additional_charges_list', client_id=client_id)
    
    return render(request, 'pricing/additional_charge_delete.html', {
        'charge': charge,
        'client': client
    })


# Pricing History View
@login_required
def pricing_history(request, client_id):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to view this page')
        return redirect('dashboard')
    
    client = get_object_or_404(Client, pk=client_id)
    history = PricingHistory.objects.filter(client=client).order_by('-changed_at')
    
    return render(request, 'pricing/pricing_history.html', {
        'client': client,
        'history': history
    })
