from decimal import Decimal
from django.db import transaction, models
from .models import PaperPricing, PrintingPricing, PlatePricing, AdditionalCharge


class PricingService:
    """
    Service class for automatic pricing calculations based on client-specific pricing rules.
    All pricing logic is centralized here for easy maintenance and future changes.
    """
    
    @staticmethod
    def calculate_job_cost(job, costing_instance=None, save=False, user=None):
        """
        Calculate total cost for a job based on client pricing rules.

        Args:
            job: Job instance
            costing_instance: Optional existing JobCosting instance to populate.
                If None and save=True, a new JobCosting will be created.
            save: Whether to save the calculated costs to a JobCosting instance
            user: User creating the costing (required if save=True and no costing_instance with created_by)

        Returns:
            dict: Breakdown of costs
        """
        from production.models import JobCosting

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

        paper_cost, paper_pricing = PricingService._calculate_paper_cost(job)
        breakdown['paper_cost'] = paper_cost
        if not paper_pricing:
            breakdown['pricing_found'] = False
            breakdown['missing_pricing'].append('Paper pricing')

        printing_cost, printing_pricing = PricingService._calculate_printing_cost(job)
        breakdown['printing_cost'] = printing_cost
        if not printing_pricing:
            breakdown['pricing_found'] = False
            breakdown['missing_pricing'].append('Printing pricing')

        plate_cost, plate_pricing = PricingService._calculate_plate_cost(job)
        breakdown['plate_cost'] = plate_cost
        if not plate_pricing:
            breakdown['pricing_found'] = False
            breakdown['missing_pricing'].append('Plate pricing')

        additional_charges = PricingService._calculate_additional_charges(job)
        breakdown['additional_charges_total'] = additional_charges['total']
        breakdown['additional_charges_breakdown'] = additional_charges['breakdown']

        breakdown['total_cost'] = (
            breakdown['paper_cost'] +
            breakdown['printing_cost'] +
            breakdown['plate_cost'] +
            breakdown['additional_charges_total']
        )

        if save:
            if costing_instance is None:
                costing_instance = JobCosting(job=job)
            costing_instance.paper_cost = breakdown['paper_cost']
            costing_instance.printing_cost = breakdown['printing_cost']
            costing_instance.plate_cost = breakdown['plate_cost']
            costing_instance.die_charge = Decimal('0.00')
            costing_instance.lamination_charge = Decimal('0.00')
            costing_instance.packing_charge = Decimal('0.00')
            costing_instance.transport_charge = Decimal('0.00')
            for entry in additional_charges['breakdown']:
                name_lower = entry['name'].lower() if entry['name'] else ''
                amt = Decimal(str(entry['amount']))
                if 'die' in name_lower:
                    costing_instance.die_charge += amt
                elif 'laminat' in name_lower:
                    costing_instance.lamination_charge += amt
                elif 'pack' in name_lower:
                    costing_instance.packing_charge += amt
                elif 'transport' in name_lower:
                    costing_instance.transport_charge += amt
            if user is not None and not getattr(costing_instance, 'created_by_id', None):
                costing_instance.created_by = user
            costing_instance.calculate_total()
            costing_instance.save()
            breakdown['costing_instance'] = costing_instance

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
