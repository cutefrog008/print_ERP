from django.db import models
from django.core.exceptions import ValidationError
from clients.models import Client


class PaperPricing(models.Model):
    PAPER_SIZE_CHOICES = (
        ('23x18', '23 x 18'),
        ('23x36', '23 x 36'),
        ('20x30', '20 x 30'),
        ('25x36', '25 x 36'),
        ('custom', 'Custom'),
    )
    
    PAPER_GSM_CHOICES = (
        (70, '70 GSM'),
        (80, '80 GSM'),
        (90, '90 GSM'),
        (100, '100 GSM'),
        (130, '130 GSM'),
        (170, '170 GSM'),
        (220, '220 GSM'),
        (250, '250 GSM'),
        (300, '300 GSM'),
        (350, '350 GSM'),
    )
    
    PAPER_TYPE_CHOICES = (
        ('maplitho', 'Maplitho'),
        ('art_paper', 'Art Paper'),
        ('gloss', 'Gloss Paper'),
        ('matt', 'Matt Paper'),
        ('duplex', 'Duplex'),
        ('kraft', 'Kraft'),
        ('sticker', 'Sticker'),
        ('other', 'Other'),
    )
    
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='paper_pricing')
    paper_size = models.CharField(max_length=20, choices=PAPER_SIZE_CHOICES, verbose_name="Paper Size")
    paper_size_custom = models.CharField(max_length=50, blank=True, null=True, verbose_name="Custom Size")
    paper_gsm = models.IntegerField(choices=PAPER_GSM_CHOICES, verbose_name="Paper GSM")
    paper_gsm_custom = models.IntegerField(blank=True, null=True, verbose_name="Custom GSM")
    paper_type = models.CharField(max_length=20, choices=PAPER_TYPE_CHOICES, verbose_name="Paper Type")
    paper_type_custom = models.CharField(max_length=50, blank=True, null=True, verbose_name="Custom Type")
    quantity_min = models.IntegerField(verbose_name="Minimum Quantity")
    quantity_max = models.IntegerField(blank=True, null=True, verbose_name="Maximum Quantity (leave blank for unlimited)")
    price_per_sheet = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Price per Sheet")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'paper_pricing'
        verbose_name = 'Paper Pricing'
        verbose_name_plural = 'Paper Pricing'
        ordering = ['client', 'paper_size', 'paper_gsm', 'paper_type', 'quantity_min']
        unique_together = ['client', 'paper_size', 'paper_size_custom', 'paper_gsm', 'paper_gsm_custom', 
                          'paper_type', 'paper_type_custom', 'quantity_min']
    
    def clean(self):
        if self.paper_size == 'custom' and not self.paper_size_custom:
            raise ValidationError({'paper_size_custom': 'Custom size is required when "Custom" is selected.'})
        if self.paper_type == 'other' and not self.paper_type_custom:
            raise ValidationError({'paper_type_custom': 'Custom type is required when "Other" is selected.'})

        if self.quantity_max is not None and self.quantity_max < self.quantity_min:
            raise ValidationError('Maximum quantity must be greater than or equal to minimum quantity.')

        overlapping = PaperPricing.objects.filter(
            client=self.client,
            paper_size=self.paper_size,
            paper_size_custom=self.paper_size_custom,
            paper_gsm=self.paper_gsm if not self.paper_gsm_custom else self.paper_gsm_custom,
            paper_type=self.paper_type,
            paper_type_custom=self.paper_type_custom
        ).exclude(pk=self.pk)

        for pricing in overlapping:
            self_max = self.quantity_max if self.quantity_max is not None else float('inf')
            pricing_max = pricing.quantity_max if pricing.quantity_max is not None else float('inf')
            if self.quantity_min <= pricing_max and self_max >= pricing.quantity_min:
                raise ValidationError('This quantity range overlaps with an existing pricing rule.')
    
    def __str__(self):
        size = self.paper_size_custom if self.paper_size == 'custom' else self.get_paper_size_display()
        gsm = self.paper_gsm_custom if self.paper_gsm_custom else self.paper_gsm
        ptype = self.paper_type_custom if self.paper_type == 'other' else self.get_paper_type_display()
        qty_range = f"{self.quantity_min}-{self.quantity_max}" if self.quantity_max else f"{self.quantity_min}+"
        return f"{self.client.name} - {size} - {gsm} GSM - {ptype} - {qty_range} - ₹{self.price_per_sheet}"


class PrintingPricing(models.Model):
    COLOR_CHOICES = (
        (1, '1 Color'),
        (2, '2 Colors'),
        (3, '3 Colors'),
        (4, '4 Colors'),
    )
    
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='printing_pricing')
    colors = models.IntegerField(choices=COLOR_CHOICES, verbose_name="Number of Colors")
    quantity_min = models.IntegerField(verbose_name="Minimum Quantity")
    quantity_max = models.IntegerField(blank=True, null=True, verbose_name="Maximum Quantity (leave blank for unlimited)")
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Printing Charge")
    minimum_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, 
                                          verbose_name="Minimum Charge (0 for no minimum)")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'printing_pricing'
        verbose_name = 'Printing Pricing'
        verbose_name_plural = 'Printing Pricing'
        ordering = ['client', 'colors', 'quantity_min']
        unique_together = ['client', 'colors', 'quantity_min']
    
    def clean(self):
        if self.quantity_max is not None and self.quantity_max < self.quantity_min:
            raise ValidationError('Maximum quantity must be greater than or equal to minimum quantity.')

        overlapping = PrintingPricing.objects.filter(
            client=self.client,
            colors=self.colors
        ).exclude(pk=self.pk)

        for pricing in overlapping:
            self_max = self.quantity_max if self.quantity_max is not None else float('inf')
            pricing_max = pricing.quantity_max if pricing.quantity_max is not None else float('inf')
            if self.quantity_min <= pricing_max and self_max >= pricing.quantity_min:
                raise ValidationError('This quantity range overlaps with an existing pricing rule.')
    
    def __str__(self):
        qty_range = f"{self.quantity_min}-{self.quantity_max}" if self.quantity_max else f"{self.quantity_min}+"
        return f"{self.client.name} - {self.colors} Color - {qty_range} - ₹{self.price} (Min: ₹{self.minimum_charge})"


class PlatePricing(models.Model):
    COLOR_CHOICES = (
        (1, '1 Color'),
        (2, '2 Colors'),
        (3, '3 Colors'),
        (4, '4 Colors'),
    )
    
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='plate_pricing')
    colors = models.IntegerField(choices=COLOR_CHOICES, verbose_name="Number of Colors")
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Plate Charge")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'plate_pricing'
        verbose_name = 'Plate Pricing'
        verbose_name_plural = 'Plate Pricing'
        ordering = ['client', 'colors']
        unique_together = ['client', 'colors']
    
    def __str__(self):
        return f"{self.client.name} - {self.colors} Color Plate - ₹{self.price}"


class AdditionalCharge(models.Model):
    CHARGE_TYPE_CHOICES = (
        ('fixed', 'Fixed Amount'),
        ('per_piece', 'Per Piece'),
        ('per_sheet', 'Per Sheet'),
    )
    
    COMMON_CHARGES = (
        ('die_charge', 'Die Charge'),
        ('lamination', 'Lamination'),
        ('uv', 'UV'),
        ('foiling', 'Foiling'),
        ('packing', 'Packing'),
        ('transportation', 'Transportation'),
        ('numbering', 'Numbering'),
        ('perforation', 'Perforation'),
        ('embossing', 'Embossing'),
        ('spot_uv', 'Spot UV'),
        ('binding', 'Binding'),
        ('other', 'Other'),
    )
    
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='additional_charges')
    name = models.CharField(max_length=100, choices=COMMON_CHARGES, verbose_name="Charge Name")
    name_custom = models.CharField(max_length=100, blank=True, null=True, verbose_name="Custom Charge Name")
    charge_type = models.CharField(max_length=20, choices=CHARGE_TYPE_CHOICES, verbose_name="Charge Type")
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Amount")
    is_active = models.BooleanField(default=True, verbose_name="Active")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'additional_charges'
        verbose_name = 'Additional Charge'
        verbose_name_plural = 'Additional Charges'
        ordering = ['client', 'name']
    
    def clean(self):
        if self.name == 'other' and not self.name_custom:
            raise ValidationError({'name_custom': 'Custom charge name is required when "Other" is selected.'})
    
    def __str__(self):
        name = self.name_custom if self.name == 'other' else self.get_name_display()
        return f"{self.client.name} - {name} ({self.get_charge_type_display()}) - ₹{self.amount}"


class PricingHistory(models.Model):
    MODEL_CHOICES = (
        ('paper_pricing', 'Paper Pricing'),
        ('printing_pricing', 'Printing Pricing'),
        ('plate_pricing', 'Plate Pricing'),
        ('additional_charge', 'Additional Charge'),
    )
    
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='pricing_history')
    model_type = models.CharField(max_length=50, choices=MODEL_CHOICES)
    model_id = models.IntegerField()
    field_name = models.CharField(max_length=100)
    old_value = models.TextField(blank=True, null=True)
    new_value = models.TextField(blank=True, null=True)
    changed_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, related_name='pricing_changes')
    changed_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'pricing_history'
        verbose_name = 'Pricing History'
        verbose_name_plural = 'Pricing History'
        ordering = ['-changed_at']
    
    def __str__(self):
        return f"{self.client.name} - {self.model_type} - {self.field_name} - {self.changed_at}"
