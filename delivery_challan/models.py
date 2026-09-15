from django.db import models
from django.utils import timezone
from accounts.models import User
from clients.models import Client
from decimal import Decimal


class DeliveryChallan(models.Model):
    STATUS_CHOICES = (
        ('created', 'Created'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    )

    challan_number = models.CharField(max_length=50, unique=True, verbose_name='Challan Number')
    challan_date = models.DateField(default=timezone.localdate, verbose_name='Challan Date')
    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name='delivery_challans')
    remarks = models.TextField(blank=True, null=True, verbose_name='Remarks')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='created', verbose_name='Status')
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='created_challans')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'delivery_challans'
        ordering = ['-challan_date', '-challan_number']
        verbose_name = 'Delivery Challan'
        verbose_name_plural = 'Delivery Challans'

    def __str__(self):
        return f"{self.challan_number} - {self.client.name}"

    @property
    def total_quantity(self):
        return sum(item.quantity for item in self.items.all())

    @property
    def total_sheets(self):
        """Sum of all total_sheets (or quantity if total_sheets empty) across linked jobs"""
        total = 0
        for item in self.items.all():
            if item.job_id and hasattr(item.job, 'total_sheets') and item.job.total_sheets:
                total += int(item.job.total_sheets)
            else:
                total += int(item.quantity or 0)
        return total

    @property
    def total_printing(self):
        """Sum of each item's printing (single-side = 1× sheets, front-back = 2× sheets)"""
        return sum(item.total_printing for item in self.items.all())

    @property
    def total_cost(self):
        return sum((item.manual_cost or Decimal('0.00')) for item in self.items.all())

    @property
    def number_of_jobs(self):
        return self.items.count()

    @staticmethod
    def generate_challan_number():
        today = timezone.localdate()
        year = today.year
        prefix = f"DC-{year}-"
        last = DeliveryChallan.objects.filter(challan_number__startswith=prefix).order_by('challan_number').last()
        if last:
            try:
                seq = int(last.challan_number.split('-')[-1]) + 1
            except (ValueError, IndexError):
                seq = 1
        else:
            seq = 1
        return f"{prefix}{seq:04d}"


class DeliveryChallanItem(models.Model):
    challan = models.ForeignKey(DeliveryChallan, on_delete=models.CASCADE, related_name='items')
    job = models.ForeignKey('production.Job', on_delete=models.SET_NULL, null=True, blank=True, related_name='challan_items')
    job_number = models.CharField(max_length=50, blank=True, null=True, verbose_name='Job Number')
    job_name = models.CharField(max_length=255, verbose_name='Job Name')
    job_date = models.DateField(blank=True, null=True, verbose_name='Job Date')
    paper_size = models.CharField(max_length=100, blank=True, null=True, verbose_name='Paper Size')
    paper_gsm = models.IntegerField(blank=True, null=True, verbose_name='Paper GSM')
    paper_type = models.CharField(max_length=100, blank=True, null=True, verbose_name='Paper Type')
    quantity = models.IntegerField(verbose_name='Quantity (Sheets)')
    printing_color = models.IntegerField(blank=True, null=True, verbose_name='Printing Colors')
    printing_type = models.CharField(max_length=50, blank=True, null=True, verbose_name='Printing Type')
    machine = models.CharField(max_length=100, blank=True, null=True, verbose_name='Machine')
    operator = models.CharField(max_length=255, blank=True, null=True, verbose_name='Operator')
    manual_cost_snapshot = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name='Cost (Snapshot)')
    remarks = models.TextField(blank=True, null=True, verbose_name='Remarks')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'delivery_challan_items'
        ordering = ['challan', 'id']
        verbose_name = 'Delivery Challan Item'
        verbose_name_plural = 'Delivery Challan Items'

    def __str__(self):
        return f"{self.job_name} ({self.challan.challan_number})"

    @property
    def printing_color_display(self):
        if self.printing_color:
            return f"{self.printing_color} Color"
        return ""

    @property
    def manual_cost(self):
        if self.job_id:
            try:
                if hasattr(self.job, '_costing_cache'):
                    costing = self.job._costing_cache
                else:
                    costing = getattr(self.job, 'costing', None)
                if costing:
                    return costing.grand_total
            except:
                pass
        if self.manual_cost_snapshot and self.manual_cost_snapshot > 0:
            return self.manual_cost_snapshot
        return Decimal('0.00')

    @property
    def total_sheets(self):
        if self.job_id and self.job and self.job.total_sheets:
            try:
                return int(self.job.total_sheets)
            except (TypeError, ValueError):
                pass
        return int(self.quantity or 0)

    @property
    def printing_multiplier(self):
        """Returns 2 for Front & Back (double-sided), 1 for Single Side"""
        pt = (self.printing_type or "").strip().lower()
        if pt in ('front_back', 'front & back', 'double', 'double_side', 'duplex'):
            return 2
        return 1

    @property
    def total_printing(self):
        return self.total_sheets * self.printing_multiplier


class DeliveryChallanAuditLog(models.Model):
    ACTION_CHOICES = (
        ('created', 'Challan Created'),
        ('edited', 'Challan Edited'),
        ('printed', 'Challan Printed'),
        ('cancelled', 'Challan Cancelled'),
        ('status_changed', 'Status Changed'),
        ('job_added', 'Job Added'),
        ('job_removed', 'Job Removed'),
    )

    challan = models.ForeignKey(DeliveryChallan, on_delete=models.CASCADE, related_name='audit_logs')
    action = models.CharField(max_length=30, choices=ACTION_CHOICES)
    field_name = models.CharField(max_length=255, blank=True, null=True)
    old_value = models.TextField(blank=True, null=True)
    new_value = models.TextField(blank=True, null=True)
    reason = models.TextField(blank=True, null=True, verbose_name='Reason')
    performed_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='challan_audit_logs')
    date = models.DateField(default=timezone.localdate)
    time = models.TimeField(default=timezone.localtime)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'delivery_challan_audit_logs'
        ordering = ['-created_at']
        verbose_name = 'Delivery Challan Audit Log'
        verbose_name_plural = 'Delivery Challan Audit Logs'

    def __str__(self):
        return f"{self.challan.challan_number} - {self.get_action_display()} - {self.created_at}"
