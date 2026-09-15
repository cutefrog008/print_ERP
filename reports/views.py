from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from datetime import date, timedelta
from production.models import Job
from attendance.models import Attendance
from employees.models import Employee
from clients.models import Client


@login_required
def report_list(request):
    if request.user.role == 'employee':
        messages.error(request, 'You do not have permission to view this page')
        return redirect('dashboard')
    return render(request, 'reports/report_list.html')


@login_required
def production_report(request):
    if request.user.role == 'employee':
        messages.error(request, 'You do not have permission to view this page')
        return redirect('dashboard')
    start_date = request.GET.get('start_date', date.today() - timedelta(days=30))
    end_date = request.GET.get('end_date', date.today())
    jobs = Job.objects.filter(date__range=[start_date, end_date])
    total_sheets = sum(job.number_of_sheets for job in jobs)
    return render(request, 'reports/production_report.html', {
        'jobs': jobs,
        'total_sheets': total_sheets,
        'start_date': start_date,
        'end_date': end_date
    })


@login_required
def attendance_report(request):
    if request.user.role == 'employee':
        messages.error(request, 'You do not have permission to view this page')
        return redirect('dashboard')
    
    # Get filter parameters
    employee_id = request.GET.get('employee')
    month = request.GET.get('month')
    year = request.GET.get('year')
    
    # Default to current month
    today = date.today()
    if not month:
        month = today.month
    if not year:
        year = today.year
    
    # Build date range for the selected month
    from calendar import monthrange
    start_date = date(int(year), int(month), 1)
    end_date = date(int(year), int(month), monthrange(int(year), int(month))[1])
    
    # Filter attendances
    attendances = Attendance.objects.filter(date__range=[start_date, end_date])
    
    # Filter by employee if selected
    selected_employee = None
    if employee_id:
        attendances = attendances.filter(employee_id=employee_id)
        selected_employee = Employee.objects.get(id=employee_id)
    
    # Calculate month-wise overtime
    from datetime import timedelta
    total_overtime = timedelta(0)
    for attendance in attendances:
        if attendance.overtime:
            total_overtime += attendance.overtime
    
    # Convert overtime to hours and minutes for display
    total_overtime_hours = total_overtime.total_seconds() / 3600
    
    # Calculate total leave days
    total_leave_days = attendances.filter(status='leave').count()
    
    # Calculate advance totals for the selected employee and month
    from attendance.models import Advance
    total_advance_taken = 0
    total_advance_returned = 0
    total_advance_pending = 0
    
    if selected_employee:
        # Advances taken in the selected month
        month_advances = Advance.objects.filter(
            employee=selected_employee,
            date__range=[start_date, end_date]
        )
        total_advance_taken = sum(adv.amount for adv in month_advances)
        total_advance_returned = sum(adv.return_amount for adv in month_advances)
        
        # Calculate pending advances (including carry-forward from previous months)
        # Get all advances for this employee up to the end of selected month
        all_advances = Advance.objects.filter(
            employee=selected_employee,
            date__lte=end_date
        )
        total_advance_pending = sum(adv.pending_amount for adv in all_advances)
    
    # Get all employees for the dropdown
    employees = Employee.objects.filter(status='active')
    
    # Generate month options (last 12 months + current)
    from datetime import datetime
    month_options = []
    for i in range(12):
        month_date = today.replace(day=1) - timedelta(days=i*30)
        month_options.append({
            'month': month_date.month,
            'year': month_date.year,
            'label': month_date.strftime('%B %Y')
        })
    
    return render(request, 'reports/attendance_report.html', {
        'attendances': attendances,
        'employees': employees,
        'selected_employee': selected_employee,
        'month_options': month_options,
        'selected_month': int(month),
        'selected_year': int(year),
        'start_date': start_date,
        'end_date': end_date,
        'total_overtime': total_overtime,
        'total_overtime_hours': total_overtime_hours,
        'total_leave_days': total_leave_days,
        'total_advance_taken': total_advance_taken,
        'total_advance_returned': total_advance_returned,
        'total_advance_pending': total_advance_pending
    })


@login_required
def client_report(request):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to view this page')
        return redirect('dashboard')
    clients = Client.objects.all()
    client_data = []
    for client in clients:
        jobs = client.jobs.all()
        total_jobs = jobs.count()
        total_sheets = sum(job.number_of_sheets for job in jobs)
        client_data.append({
            'client': client,
            'total_jobs': total_jobs,
            'total_sheets': total_sheets
        })
    return render(request, 'reports/client_report.html', {'client_data': client_data})


@login_required
def employee_productivity_report(request):
    if request.user.role == 'employee':
        messages.error(request, 'You do not have permission to view this page')
        return redirect('dashboard')
    employees = Employee.objects.filter(status='active')
    employee_data = []
    for emp in employees:
        jobs = Job.objects.filter(operator=emp)
        total_jobs = jobs.count()
        total_sheets = sum(job.number_of_sheets for job in jobs)
        employee_data.append({
            'employee': emp,
            'total_jobs': total_jobs,
            'total_sheets': total_sheets
        })
    return render(request, 'reports/employee_productivity_report.html', {'employee_data': employee_data})
