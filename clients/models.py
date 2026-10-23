from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone


class Client(models.Model):
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('archived', 'Archived'),
    )
    
    # Basic Information
    name = models.CharField(max_length=255, verbose_name="Client Name")
    company = models.CharField(max_length=255, blank=True, null=True, verbose_name="Company Name")
    contact_person = models.CharField(max_length=255, blank=True, null=True, verbose_name="Contact Person")
    mobile_number = models.CharField(max_length=20, blank=True, null=True, verbose_name="Mobile Number")
    whatsapp_number = models.CharField(max_length=20, blank=True, null=True, verbose_name="WhatsApp Number")
    email = models.EmailField(blank=True, null=True, verbose_name="Email")
    gst_number = models.CharField(max_length=50, blank=True, null=True, verbose_name="GST Number")
    pan_number = models.CharField(max_length=20, blank=True, null=True, verbose_name="PAN Number")
    address = models.TextField(blank=True, null=True, verbose_name="Address")
    city = models.CharField(max_length=100, blank=True, null=True, verbose_name="City")
    state = models.CharField(max_length=100, blank=True, null=True, verbose_name="State")
    pincode = models.CharField(max_length=20, blank=True, null=True, verbose_name="Pincode")
    notes = models.TextField(blank=True, null=True, verbose_name="Notes")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active', verbose_name="Status")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created At")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Updated At")
    
    # Pricing (only visible to Admin)
    color_1_rate = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="1 Color Rate")
    color_2_rate = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="2 Color Rate")
    color_3_rate = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="3 Color Rate")
    color_4_rate = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="4 Color Rate")
    front_back_extra = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Front & Back Extra Charge")
    plate_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Plate Charge")
    die_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Die Charge")
    packing_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Packing Charge")
    transport_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Transport Charge")
    lamination_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Lamination Charge")
    other_charges = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, blank=True, null=True, verbose_name="Other Charges")
    
    class Meta:
        db_table = 'clients'
        ordering = [Lower('name')]
    
    def __str__(self):
        return f"{self.name} - {self.company if self.company else ''}"
    
    def has_related_records(self):
        """Check if client has any related records that would prevent permanent deletion"""
        from production.models import Job
        job_count = self.jobs.count()
        return job_count > 0


class ClientAuditLog(models.Model):
    ACTION_CHOICES = (
        ('archived', 'Archived'),
        ('restored', 'Restored'),
        ('deleted', 'Deleted'),
    )
    
    client_name = models.CharField(max_length=255)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    reason = models.TextField(blank=True, null=True)
    performed_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, related_name='client_audit_logs')
    performed_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'client_audit_logs'
        ordering = ['-performed_at']
    
    def __str__(self):
        return f"{self.client_name} - {self.action} - {self.performed_at}"


class ClientPayment(models.Model):
    PAYMENT_MODE_CHOICES = (
        ('cash', 'Cash'),
        ('online', 'Online'),
        ('cheque', 'Cheque'),
        ('bank_transfer', 'Bank Transfer'),
    )
    
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_mode = models.CharField(max_length=20, choices=PAYMENT_MODE_CHOICES)
    payment_date = models.DateField()
    reference_number = models.CharField(max_length=100, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    received_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, related_name='client_payments_received')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'client_payments'
        ordering = ['-payment_date', '-created_at']
    
    def __str__(self):
        return f"{self.client.name} - ₹{self.amount} - {self.payment_date}"
