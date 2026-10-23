from django.db import models
from django.utils import timezone
from accounts.models import User
from clients.models import Client
from employees.models import Employee


class Job(models.Model):
    COLOR_CHOICES = (
        (1, '1 Color'),
        (2, '2 Colors'),
        (3, '3 Colors'),
        (4, '4 Colors'),
        (5, '5 Colors'),
    )

    PRINTING_TYPE_CHOICES = (
        ('single', 'Single Side'),
        ('lotpot', 'Lotpot'),
        ('P+P', 'P+P'),
        ('S+P', 'S+P'),
    )

    STATUS_CHOICES = (
        ('pending_costing', 'Add Price'),
        ('costing_completed', 'Costing Completed'),
        ('ready_for_challan', 'Create Challan'),
        ('challan_created', 'Challan Created'),
        ('dispatched', 'Dispatched'),
        ('cancelled', 'Cancelled'),
    )

    PAPER_SIZE_CHOICES = (
        ('11.5x18', '11.5x18'),
        ('12x18', '12x18'),
        ('12.5x18', '12.5x18'),
        ('12x23', '12x23'),
        ('12x25', '12x25'),
        ('13x19', '13x19'),
        ('14x22', '14x22'),
        ('15x20', '15x20'),
        ('18x22', '18x22'),
        ('18x23', '18x23'),
        ('18x25', '18x25'),
        ('20x30', '20x30'),
    )

    PAPER_GSM_CHOICES = (
        (54, '54'),
        (58, '58'),
        (64, '64'),
        (70, '70'),
        (75, '75'),
        (80, '80'),
        (90, '90'),
        (100, '100'),
        (120, '120'),
        (128, '128'),
        (170, '170'),
        (210, '210'),
        (250, '250'),
        (300, '300'),
        (350, '350'),
    )

    PAPER_TYPE_CHOICES = (
        ('Art Paper', 'Art Paper'),
        ('Matte', 'Matte'),
        ('Maflito', 'Maflito'),
        ('Gum Sheet', 'Gum Sheet'),
        ('Art Card', 'Art Card'),
        ('Duplex', 'Duplex'),
        ('SBS', 'SBS'),
    )

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='jobs')
    job_name = models.CharField(max_length=255, blank=True, default="")
    paper_size = models.CharField(max_length=100)
    paper_gsm = models.IntegerField()
    paper_type = models.CharField(max_length=100)
    number_of_sheets = models.IntegerField()
    printing_colors = models.IntegerField(choices=COLOR_CHOICES)
    printing_type = models.CharField(max_length=20, choices=PRINTING_TYPE_CHOICES)
    total_sheets = models.IntegerField(blank=True, null=True, verbose_name='Total Sheets')
    machine = models.CharField(max_length=100, blank=True, null=True, verbose_name='Machine')
    operator = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='jobs')
    remarks = models.TextField(blank=True, null=True)
    date = models.DateField(auto_now_add=True)
    time = models.TimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_jobs')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending_costing')
    delivery_challan = models.ForeignKey(
        'delivery_challan.DeliveryChallan',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='jobs'
    )
    dispatch_date = models.DateField(null=True, blank=True, verbose_name='Dispatch Date')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'jobs'
        ordering = ['-date', '-time']

    def __str__(self):
        return f"JOB-{self.id:04d} {self.job_name} - {self.client.name}"

    @property
    def job_number(self):
        return f"JOB-{self.id:04d}"

    @property
    def manual_cost(self):
        if hasattr(self, 'costing'):
            return self.costing.grand_total
        return None

    @property
    def is_eligible_for_challan(self):
        has_costing = hasattr(self, 'costing')
        return self.status in ('costing_completed', 'ready_for_challan') and has_costing and self.delivery_challan_id is None


class JobAdditionalCharge(models.Model):
    job_costing = models.ForeignKey('JobCosting', on_delete=models.CASCADE, related_name='additional_charges')
    label = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'job_additional_charges'

    def __str__(self):
        return f"{self.label} - ₹{self.amount}"


class JobCosting(models.Model):
    job = models.OneToOneField(Job, on_delete=models.CASCADE, related_name='costing')
    paper_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    printing_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    plate_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    die_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    lamination_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    packing_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    transport_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    grand_total = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    remarks = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_costings')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'job_costings'
        ordering = ['-created_at']

    def calculate_total(self):
        # Calculate subtotal (main charges)
        subtotal = (
            self.paper_cost +
            self.printing_cost +
            self.plate_cost +
            self.die_charge +
            self.lamination_charge +
            self.packing_charge +
            self.transport_charge
        )
        
        # Add additional charges (only if instance is saved)
        if self.pk:
            for charge in self.additional_charges.all():
                subtotal += charge.amount
        
        # Calculate grand total
        self.grand_total = subtotal
        
        return self.grand_total

    def save(self, *args, **kwargs):
        # Save first to get primary key
        super().save(*args, **kwargs)
        # Recalculate after save to include additional charges
        self.calculate_total()
        # Save again to update grand total with additional charges
        super().save(update_fields=['grand_total'])

    def __str__(self):
        return f"Costing for {self.job.job_name} - ₹{self.grand_total}"


class CostingAuditLog(models.Model):
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='costing_audit_logs')
    field_name = models.CharField(max_length=255)
    old_value = models.TextField(blank=True, null=True)
    new_value = models.TextField(blank=True, null=True)
    reason = models.TextField(blank=True, null=True)
    changed_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='costing_changes')
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'costing_audit_logs'
        ordering = ['-changed_at']

    def __str__(self):
        return f"{self.job.job_name} - {self.field_name} - {self.changed_at}"
