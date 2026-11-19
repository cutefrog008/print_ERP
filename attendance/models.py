from django.db import models
from accounts.models import User
from employees.models import Employee
from datetime import timedelta


class Attendance(models.Model):
    STATUS_CHOICES = (
        ('present', 'Present'),
        ('leave', 'Leave'),
    )
    
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='attendances')
    date = models.DateField()
    time = models.TimeField()
    in_time = models.TimeField(default='09:00')
    out_time = models.TimeField(default='17:30')
    total_time = models.DurationField(blank=True, null=True, help_text="Total working hours")
    overtime = models.DurationField(blank=True, null=True, help_text="Overtime hours (beyond 8:30)")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='present')
    marked_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='marked_attendances')
    remarks = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'attendance'
        ordering = ['-date', '-time']
        unique_together = ('employee', 'date')
    
    def is_non_working_day(self):
        """A Sunday or a recorded public holiday."""
        if self.date.weekday() == 6:  # Sunday
            return True
        return Holiday.objects.filter(date=self.date).exists()

    def calculate_working_hours(self):
        """Calculate total working hours and overtime.

        On a non-working day (Sunday or public holiday) every hour worked
        counts as overtime (no 8h30m standard deduction), so time-and-a-half /
        full-overtime rules can be applied downstream.
        """
        if self.in_time and self.out_time:
            from datetime import datetime
            in_datetime = datetime.combine(self.date, self.in_time)
            out_datetime = datetime.combine(self.date, self.out_time)

            # Handle overnight shifts (if out_time is earlier than in_time)
            if out_datetime < in_datetime:
                out_datetime += timedelta(days=1)

            self.total_time = out_datetime - in_datetime

            if self.is_non_working_day():
                # Everything worked on a Sunday/holiday is overtime.
                self.overtime = self.total_time
            else:
                standard_hours = timedelta(hours=8, minutes=30)
                if self.total_time > standard_hours:
                    self.overtime = self.total_time - standard_hours
                else:
                    self.overtime = timedelta(0)

    def save(self, *args, **kwargs):
        self.calculate_working_hours()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.employee} - {self.date} - {self.status}"


class Holiday(models.Model):
    """Public holiday dates used by attendance logic.

    Adding a date here marks it as a non-working day for attendance: working
    hours count as full overtime and the date is excluded from leave totals.
    """
    date = models.DateField(unique=True)
    name = models.CharField(max_length=100)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_holidays')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'holidays'
        ordering = ['date']

    def __str__(self):
        return f"{self.name} ({self.date})"


class EmployeeAdvanceTransaction(models.Model):
    TRANSACTION_TYPE_CHOICES = (
        ('TAKEN', 'Advance Taken'),
        ('REPAYMENT', 'Repayment'),
    )
    
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name='advance_transactions')
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPE_CHOICES, verbose_name="Transaction Type")
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Amount")
    transaction_date = models.DateField(verbose_name="Transaction Date")
    remarks = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='created_advance_transactions')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'employee_advance_transactions'
        ordering = ['-transaction_date', '-created_at']
        indexes = [
            models.Index(fields=['employee']),
            models.Index(fields=['transaction_date']),
            models.Index(fields=['transaction_type']),
        ]
    
    def __str__(self):
        return f"{self.employee} - {self.get_transaction_type_display()} - ₹{self.amount} - {self.transaction_date}"
    
    @property
    def balance_after_transaction(self):
        """Calculate balance after this transaction"""
        from django.db.models import Sum
        transactions = EmployeeAdvanceTransaction.objects.filter(
            employee=self.employee,
            transaction_date__lte=self.transaction_date
        ).order_by('transaction_date', 'created_at')
        
        balance = 0
        for tx in transactions:
            if tx.transaction_type == 'TAKEN':
                balance += tx.amount
            elif tx.transaction_type == 'REPAYMENT':
                balance -= tx.amount
            if tx.id == self.id:
                break
        return balance
