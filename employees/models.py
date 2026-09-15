from django.db import models
from accounts.models import User


class Employee(models.Model):
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    )
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='employee_profile')
    photo = models.ImageField(upload_to='employee_photos/', blank=True, null=True, verbose_name="Photo")
    phone = models.CharField(max_length=20, verbose_name="Phone")
    email = models.EmailField(blank=True, null=True, verbose_name="Email")
    address = models.TextField(blank=True, null=True, verbose_name="Address")
    joining_date = models.DateField(verbose_name="Joining Date")
    emergency_contact = models.CharField(max_length=20, blank=True, null=True, verbose_name="Emergency Contact")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active', verbose_name="Status")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created At")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Updated At")
    
    class Meta:
        db_table = 'employees'
        ordering = ['user__first_name', 'user__last_name']
    
    def __str__(self):
        return f"{self.user.get_full_name()}"
