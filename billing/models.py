from django.db import models
from django.utils import timezone
from clients.models import Client
from production.models import Job
from accounts.models import User


class Invoice(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('final', 'Final'),
        ('paid', 'Paid'),
        ('partial', 'Partially Paid'),
        ('cancelled', 'Cancelled'),
    ]

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='invoices')
    invoice_number = models.CharField(max_length=100, unique=True)
    date = models.DateField(auto_now_add=True)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    gst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    gst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    remarks = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_invoices')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'invoices'
        ordering = ['-date', '-invoice_number']

    def __str__(self):
        return f"{self.invoice_number} - {self.client.name}"

    @property
    def outstanding_amount(self):
        return self.total_amount - self.paid_amount

    def calculate_totals(self):
        subtotal = sum(item.total for item in self.items.all())
        self.subtotal = subtotal
        self.gst_amount = (subtotal * self.gst_rate) / 100
        self.total_amount = self.subtotal + self.gst_amount
        self.save()


class InvoiceItem(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='items')
    job = models.ForeignKey(Job, on_delete=models.SET_NULL, null=True, blank=True, related_name='invoice_items')
    description = models.CharField(max_length=255)
    quantity = models.IntegerField(default=1)
    rate = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    paper_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, blank=True)
    printing_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, blank=True)
    plate_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, blank=True)
    additional_charges = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, blank=True)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'invoice_items'

    def __str__(self):
        return f"{self.description} - {self.invoice.invoice_number}"

    def save(self, *args, **kwargs):
        self.total = self.quantity * self.rate
        super().save(*args, **kwargs)


class InvoiceAuditLog(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='audit_logs')
    edited_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='invoice_edits')
    date = models.DateField(default=timezone.localdate)
    time = models.TimeField(default=timezone.localtime)
    field = models.CharField(max_length=255)
    old_value = models.TextField(blank=True, null=True)
    new_value = models.TextField(blank=True, null=True)
    reason = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'invoice_audit_logs'
        ordering = ['-date', '-time']

    def __str__(self):
        return f"{self.invoice.invoice_number} - {self.edited_by} - {self.date}"


class JobBilling(models.Model):
    job = models.OneToOneField(Job, on_delete=models.CASCADE, related_name='billing')
    color_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    front_back_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    plate_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    packing_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    transport_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    lamination_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    die_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    other_charges = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, blank=True, null=True)
    total_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    calculated_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='calculated_billings', blank=True, null=True)
    calculated_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'job_billings'
        ordering = ['-created_at']

    def __str__(self):
        return f"Billing for {self.job.job_name}"


class Payment(models.Model):
    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Cash'),
        ('upi', 'UPI'),
        ('bank', 'Bank Transfer'),
        ('cheque', 'Cheque'),
    ]

    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    date = models.DateField(auto_now_add=True)
    transaction_id = models.CharField(max_length=255, blank=True, null=True)
    remarks = models.TextField(blank=True, null=True)
    received_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_payments')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'payments'
        ordering = ['-date']

    def __str__(self):
        return f"Payment {self.amount} for {self.invoice.invoice_number}"
