from decimal import Decimal
from django.db import transaction, models
from .models import PaperPricing, PrintingPricing, PlatePricing, AdditionalCharge


class PricingService:
    """
    Service class for automatic pricing calculations based on client-specific pricing rules.
    All pricing logic is centralized here for easy maintenance and future changes.
    """
    
    @staticmethod
    def calculate_job_cost(job, save=True):
        """
        Calculate total cost for a job based on client pricing rules.
        
        Args:
            job: Job instance
            save: Whether to save the calculated costs to the job instance
            
        Returns:
            dict: Breakdown of costs
        """
        from production.models import Job
        
        breakdown = {
            'paper_cost': Decimal('0.00'),
            'printing_cost': Decimal('0.00'),
            'plate_cost': Decimal('0.00'),
            'additional_charges_total': Decimal('0.00'),
            'additional_charges_breakdown': [],
            'total_cost': Decimal('0.00'),
            'pricing_found': True,
            'missing_pricing': []
        }
        
        # 1. Calculate Paper Cost
        paper_cost, paper_pricing = PricingService._calculate_paper_cost(job)
        breakdown['paper_cost'] = paper_cost
        if not paper_pricing:
            breakdown['pricing_found'] = False
            breakdown['missing_pricing'].append('Paper pricing')
        
        # 2. Calculate Printing Cost
        printing_cost, printing_pricing = PricingService._calculate_printing_cost(job)
        breakdown['printing_cost'] = printing_cost
        if not printing_pricing:
            breakdown['pricing_found'] = False
            breakdown['missing_pricing'].append('Printing pricing')
        
        # 3. Calculate Plate Cost
        plate_cost, plate_pricing = PricingService._calculate_plate_cost(job)
        breakdown['plate_cost'] = plate_cost
        if not plate_pricing:
            breakdown['pricing_found'] = False
            breakdown['missing_pricing'].append('Plate pricing')
        
        # 4. Calculate Additional Charges
        additional_charges = PricingService._calculate_additional_charges(job)
        breakdown['additional_charges_total'] = additional_charges['total']
        breakdown['additional_charges_breakdown'] = additional_charges['breakdown']
        
        # 5. Calculate Total
        breakdown['total_cost'] = (
            breakdown['paper_cost'] + 
            breakdown['printing_cost'] + 
            breakdown['plate_cost'] + 
            breakdown['additional_charges_total']
        )
        
        # Save to job if requested
        if save:
            job.paper_cost = breakdown['paper_cost']
            job.printing_cost = breakdown['printing_cost']
            job.plate_cost = breakdown['plate_cost']
            job.additional_charges_total = breakdown['additional_charges_total']
            job.total_cost = breakdown['total_cost']
            job.save()
        
        return breakdown
    
    @staticmethod
    def _calculate_paper_cost(job):
        """Calculate paper cost based on paper pricing rules."""
        from decimal import Decimal
        
        # Normalize paper size for matching
        paper_size = job.paper_size.lower().replace(' ', '').replace('x', 'x')
        
        # Try to find matching paper pricing
        paper_pricing = PaperPricing.objects.filter(
            client=job.client,
            paper_size=paper_size,
            paper_gsm=job.paper_gsm,
            paper_type=job.paper_type.lower(),
            quantity_min__lte=job.number_of_sheets
        ).filter(
            models.Q(quantity_max__gte=job.number_of_sheets) | models.Q(quantity_max__isnull=True)
        ).first()
        
        if paper_pricing:
            cost = paper_pricing.price_per_sheet * Decimal(str(job.number_of_sheets))
            return cost, paper_pricing
        
        return Decimal('0.00'), None
    
    @staticmethod
    def _calculate_printing_cost(job):
        """Calculate printing cost based on printing pricing rules."""
        from decimal import Decimal
        from django.db import models
        
        # Find matching printing pricing
        printing_pricing = PrintingPricing.objects.filter(
            client=job.client,
            colors=job.printing_colors,
            quantity_min__lte=job.number_of_sheets
        ).filter(
            models.Q(quantity_max__gte=job.number_of_sheets) | models.Q(quantity_max__isnull=True)
        ).first()
        
        if printing_pricing:
            cost = printing_pricing.price
            
            # Apply front/back doubling
            if job.printing_type == 'front_back':
                cost = cost * Decimal('2')
            
            # Apply minimum charge
            if printing_pricing.minimum_charge > 0 and cost < printing_pricing.minimum_charge:
                cost = printing_pricing.minimum_charge
            
            return cost, printing_pricing
        
        return Decimal('0.00'), None
    
    @staticmethod
    def _calculate_plate_cost(job):
        """Calculate plate cost based on plate pricing rules."""
        plate_pricing = PlatePricing.objects.filter(
            client=job.client,
            colors=job.printing_colors
        ).first()
        
        if plate_pricing:
            return plate_pricing.price, plate_pricing
        
        return Decimal('0.00'), None
    
    @staticmethod
    def _calculate_additional_charges(job):
        """Calculate additional charges based on client's active additional charges."""
        from decimal import Decimal
        
        additional_charges = AdditionalCharge.objects.filter(
            client=job.client,
            is_active=True
        )
        
        total = Decimal('0.00')
        breakdown = []
        
        for charge in additional_charges:
            charge_amount = charge.amount
            
            # Calculate based on charge type
            if charge.charge_type == 'per_sheet':
                charge_amount = charge.amount * Decimal(str(job.number_of_sheets))
            elif charge.charge_type == 'per_piece':
                # Assuming 1 piece = 1 sheet for now
                charge_amount = charge.amount * Decimal(str(job.number_of_sheets))
            # For fixed, use the amount as-is
            
            total += charge_amount
            breakdown.append({
                'name': charge.name_custom if charge.name == 'other' else charge.get_name_display(),
                'type': charge.get_charge_type_display(),
                'amount': charge_amount
            })
        
        return {'total': total, 'breakdown': breakdown}
    
    @staticmethod
    def check_pricing_completeness(client):
        """
        Check if a client has complete pricing configuration.
        
        Returns:
            dict: Status of pricing configuration
        """
        status = {
            'complete': True,
            'missing': []
        }
        
        # Check paper pricing
        paper_count = PaperPricing.objects.filter(client=client).count()
        if paper_count == 0:
            status['complete'] = False
            status['missing'].append('Paper Pricing')
        
        # Check printing pricing
        printing_count = PrintingPricing.objects.filter(client=client).count()
        if printing_count == 0:
            status['complete'] = False
            status['missing'].append('Printing Pricing')
        
        # Check plate pricing
        plate_count = PlatePricing.objects.filter(client=client).count()
        if plate_count == 0:
            status['complete'] = False
            status['missing'].append('Plate Pricing')
        
        return status
    
    @staticmethod
    def record_pricing_change(instance, field_name, old_value, new_value, user):
        """
        Record pricing changes to history.
        
        Args:
            instance: The model instance being changed
            field_name: Name of the field being changed
            old_value: Old value of the field
            new_value: New value of the field
            user: User making the change
        """
        from .models import PricingHistory
        
        # Determine model type
        model_type_map = {
            'PaperPricing': 'paper_pricing',
            'PrintingPricing': 'printing_pricing',
            'PlatePricing': 'plate_pricing',
            'AdditionalCharge': 'additional_charge',
        }
        
        model_type = model_type_map.get(instance.__class__.__name__)
        
        if model_type and old_value != new_value:
            PricingHistory.objects.create(
                client=instance.client,
                model_type=model_type,
                model_id=instance.pk,
                field_name=field_name,
                old_value=str(old_value) if old_value is not None else '',
                new_value=str(new_value) if new_value is not None else '',
                changed_by=user
            )
