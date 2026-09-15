from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from datetime import date, timedelta
from clients.models import Client
from employees.models import Employee
from attendance.models import Attendance
from production.models import Job
from delivery_challan.models import DeliveryChallan


def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect('dashboard')
        else:
            messages.error(request, 'Invalid username or password')
    return render(request, 'login.html')


def logout_view(request):
    logout(request)
    return redirect('login')


@login_required
def dashboard_view(request):
    today = date.today()
    context = {}

    if request.user.role == 'admin':
        today_jobs_qs = Job.objects.filter(date=today)
        context['today_jobs'] = today_jobs_qs.count()
        context['today_sheets'] = sum(job.number_of_sheets for job in today_jobs_qs) or 0
        context['today_clients'] = Client.objects.filter(status='active').count()
        context['employees_present'] = Attendance.objects.filter(date=today, status='present').count()
        context['pending_costing'] = Job.objects.filter(status='pending_costing').count()
        context['ready_for_challan'] = Job.objects.filter(
            status__in=['costing_completed', 'ready_for_challan'],
            delivery_challan__isnull=True,
        ).count()

        today_challans = DeliveryChallan.objects.filter(challan_date=today)
        context['today_challans'] = today_challans.count()
        context['dispatched_today'] = today_challans.filter(status='completed').count()
        context['delivered_today'] = today_challans.filter(status='completed').count()
        context['cancelled_challans'] = DeliveryChallan.objects.filter(status='cancelled').count()

        last_7_days = today - timedelta(days=7)
        context['weekly_jobs'] = Job.objects.filter(date__gte=last_7_days).count()
        context['weekly_sheets'] = sum(
            job.number_of_sheets for job in Job.objects.filter(date__gte=last_7_days)
        ) or 0
        context['today_date'] = today

    elif request.user.role == 'manager':
        context['today_attendance'] = Attendance.objects.filter(date=today).count()
        context['today_jobs'] = Job.objects.filter(date=today).count()
        context['employees_working'] = Employee.objects.filter(status='active').count()
        context['pending_costing'] = Job.objects.filter(status='pending_costing').count()
        context['ready_for_challan'] = Job.objects.filter(
            status__in=['costing_completed', 'ready_for_challan'],
            delivery_challan__isnull=True,
        ).count()
        context['today_challans'] = DeliveryChallan.objects.filter(challan_date=today).count()
        context['dispatched_today'] = DeliveryChallan.objects.filter(
            challan_date=today, status='completed'
        ).count()
        context['today_date'] = today

    elif request.user.role == 'employee':
        if hasattr(request.user, 'employee_profile'):
            employee = request.user.employee_profile
            employee_jobs = Job.objects.filter(date=today, operator=employee)
            context['today_jobs'] = employee_jobs.count()
            context['today_sheets'] = sum(job.number_of_sheets for job in employee_jobs) or 0
            context['today_date'] = today

    return render(request, 'dashboard.html', context)
