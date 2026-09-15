from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import date
from accounts.models import User
from clients.models import Client
from employees.models import Employee
from production.models import Machine, Job


class Command(BaseCommand):
    help = 'Creates sample data for the printing ERP'

    def handle(self, *args, **kwargs):
        # Create admin user
        admin_user, created = User.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'admin@example.com',
                'first_name': 'Admin',
                'last_name': 'User',
                'role': 'admin'
            }
        )
        if created:
            admin_user.set_password('admin123')
            admin_user.save()
            self.stdout.write(self.style.SUCCESS('Admin user created successfully'))
        
        # Create manager user
        manager_user, created = User.objects.get_or_create(
            username='manager',
            defaults={
                'email': 'manager@example.com',
                'first_name': 'Manager',
                'last_name': 'User',
                'role': 'manager'
            }
        )
        if created:
            manager_user.set_password('manager123')
            manager_user.save()
            self.stdout.write(self.style.SUCCESS('Manager user created successfully'))
        
        # Create manager employee profile
        manager_employee, _ = Employee.objects.get_or_create(
            user=manager_user,
            defaults={
                'phone': '9876543210',
                'email': 'manager@example.com',
                'joining_date': date(2023, 1, 1),
                'status': 'active'
            }
        )
        
        # Create employee users
        employee1_user, created = User.objects.get_or_create(
            username='employee1',
            defaults={
                'email': 'employee1@example.com',
                'first_name': 'John',
                'last_name': 'Doe',
                'role': 'employee'
            }
        )
        if created:
            employee1_user.set_password('employee123')
            employee1_user.save()
            self.stdout.write(self.style.SUCCESS('Employee 1 created successfully'))
        
        employee1, _ = Employee.objects.get_or_create(
            user=employee1_user,
            defaults={
                'phone': '9876543211',
                'email': 'employee1@example.com',
                'joining_date': date(2023, 6, 1),
                'status': 'active'
            }
        )
        
        employee2_user, created = User.objects.get_or_create(
            username='employee2',
            defaults={
                'email': 'employee2@example.com',
                'first_name': 'Jane',
                'last_name': 'Smith',
                'role': 'employee'
            }
        )
        if created:
            employee2_user.set_password('employee123')
            employee2_user.save()
            self.stdout.write(self.style.SUCCESS('Employee 2 created successfully'))
        
        employee2, _ = Employee.objects.get_or_create(
            user=employee2_user,
            defaults={
                'phone': '9876543212',
                'email': 'employee2@example.com',
                'joining_date': date(2023, 8, 1),
                'status': 'active'
            }
        )
        
        # Create clients
        client1, _ = Client.objects.get_or_create(
            name='ABC Corporation',
            defaults={
                'company': 'ABC Corp',
                'contact_person': 'John Smith',
                'mobile_number': '0123456789',
                'whatsapp_number': '0123456789',
                'email': 'info@abccorp.com',
                'gst_number': '12ABCDE1234F1Z5',
                'pan_number': 'ABCDE1234F',
                'address': '123 Main St, City',
                'city': 'Mumbai',
                'state': 'Maharashtra',
                'pincode': '400001',
                'status': 'active',
                'color_1_rate': 2.0,
                'color_2_rate': 3.5,
                'color_3_rate': 5.0,
                'color_4_rate': 6.5,
                'front_back_extra': 1.0,
                'plate_charge': 50.0,
                'packing_charge': 20.0,
                'transport_charge': 30.0,
                'lamination_charge': 1.5
            }
        )
        
        client2, _ = Client.objects.get_or_create(
            name='XYZ Enterprises',
            defaults={
                'company': 'XYZ Ent',
                'contact_person': 'Jane Doe',
                'mobile_number': '0987654321',
                'whatsapp_number': '0987654321',
                'email': 'contact@xyz.com',
                'status': 'active',
                'color_1_rate': 1.8,
                'color_2_rate': 3.2,
                'color_3_rate': 4.8,
                'color_4_rate': 6.0,
                'front_back_extra': 0.9,
                'plate_charge': 45.0,
                'packing_charge': 18.0,
                'transport_charge': 25.0,
                'lamination_charge': 1.2
            }
        )
        
        # Create machines
        machine1, _ = Machine.objects.get_or_create(
            name='Heidelberg Speedmaster',
            defaults={'status': 'idle'}
        )
        machine2, _ = Machine.objects.get_or_create(
            name='Komori Lithrone',
            defaults={'status': 'idle'}
        )
        
        # Create sample jobs
        job1, _ = Job.objects.get_or_create(
            client=client1,
            job_name='Brochure Printing',
            defaults={
                'paper_size': 'A4',
                'paper_gsm': 170,
                'paper_type': 'Glossy',
                'number_of_sheets': 500,
                'printing_colors': 4,
                'printing_type': 'single',
                'machine': machine1,
                'operator': employee1,
                'date': date.today(),
                'time': timezone.now().time(),
                'created_by': admin_user,
                'status': 'in_progress'
            }
        )
        
        job2, _ = Job.objects.get_or_create(
            client=client2,
            job_name='Business Cards',
            defaults={
                'paper_size': 'A3',
                'paper_gsm': 300,
                'paper_type': 'Matte',
                'number_of_sheets': 1000,
                'printing_colors': 2,
                'printing_type': 'front_back',
                'machine': machine2,
                'operator': employee2,
                'date': date.today(),
                'time': timezone.now().time(),
                'created_by': manager_user,
                'status': 'pending'
            }
        )
        
        self.stdout.write(self.style.SUCCESS('Sample data created successfully'))
