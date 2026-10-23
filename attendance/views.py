from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from datetime import date, timedelta
from .models import Attendance
from employees.models import Employee
from .forms import AttendanceForm
from django.db import transaction


@login_required
def attendance_list(request):
    if request.user.role not in ['admin', 'manager']:
        messages.error(request, 'You do not have permission to view this page')
        return redirect('dashboard')

    employee_id = request.GET.get('employee')
    month = request.GET.get('month')
    year = request.GET.get('year')

    today = date.today()
    try:
        month = int(month) if month else today.month
        if month < 1 or month > 12:
            month = today.month
    except (ValueError, TypeError):
        month = today.month
    try:
        year = int(year) if year else today.year
        if year < 2000 or year > 2100:
            year = today.year
    except (ValueError, TypeError):
        year = today.year

    from calendar import monthrange
    start_date = date(year, month, 1)
    end_date = date(year, month, monthrange(year, month)[1])

    attendances = Attendance.objects.filter(date__range=[start_date, end_date]).order_by('-date')

    selected_employee = None
    total_overtime = None
    total_leave_days = None
    if employee_id:
        try:
            employee_id = int(employee_id)
        except (ValueError, TypeError):
            employee_id = None
        if employee_id:
            attendances = attendances.filter(employee_id=employee_id)
            try:
                selected_employee = Employee.objects.get(id=employee_id)
            except Employee.DoesNotExist:
                selected_employee = None

            total_overtime = timedelta(0)
            for attendance in attendances:
                if attendance.overtime:
                    total_overtime += attendance.overtime

            total_leave_days = attendances.filter(status='leave').count()

    employees = Employee.objects.filter(status='active')

    month_options = []
    for i in range(12):
        month_date = today.replace(day=1) - timedelta(days=i*30)
        month_options.append({
            'month': month_date.month,
            'year': month_date.year,
            'label': month_date.strftime('%B %Y')
        })

    return render(request, 'attendance/attendance_list.html', {
        'attendances': attendances,
        'employees': employees,
        'selected_employee': selected_employee,
        'month_options': month_options,
        'selected_month': int(month),
        'selected_year': int(year),
        'start_date': start_date,
        'end_date': end_date,
        'total_overtime': total_overtime,
        'total_leave_days': total_leave_days
    })


@login_required
def attendance_create(request):
    if request.user.role not in ['admin', 'manager']:
        messages.error(request, 'You do not have permission to view this page')
        return redirect('dashboard')
    if request.method == 'POST':
        form = AttendanceForm(request.POST)
        if form.is_valid():
            attendance = form.save(commit=False)
            attendance.marked_by = request.user
            attendance.save()
            messages.success(request, 'Attendance marked successfully')
            return redirect('attendance_list')
    else:
        form = AttendanceForm()
    return render(request, 'attendance/attendance_form.html', {'form': form})


@login_required
def my_attendance(request):
    if request.user.role != 'employee' or not hasattr(request.user, 'employee_profile'):
        messages.error(request, 'You do not have permission to view this page')
        return redirect('dashboard')
    employee = request.user.employee_profile

    month = request.GET.get('month')
    year = request.GET.get('year')

    today = date.today()
    try:
        month = int(month) if month else today.month
        if month < 1 or month > 12:
            month = today.month
    except (ValueError, TypeError):
        month = today.month
    try:
        year = int(year) if year else today.year
        if year < 2000 or year > 2100:
            year = today.year
    except (ValueError, TypeError):
        year = today.year

    from calendar import monthrange
    start_date = date(year, month, 1)
    end_date = date(year, month, monthrange(year, month)[1])

    attendances = Attendance.objects.filter(
        employee=employee,
        date__range=[start_date, end_date]
    ).order_by('-date')

    month_options = []
    for i in range(12):
        month_date = today.replace(day=1) - timedelta(days=i*30)
        month_options.append({
            'month': month_date.month,
            'year': month_date.year,
            'label': month_date.strftime('%B %Y')
        })

    return render(request, 'attendance/my_attendance.html', {
        'attendances': attendances,
        'month_options': month_options,
        'selected_month': int(month),
        'selected_year': int(year),
        'start_date': start_date,
        'end_date': end_date
    })


@login_required
@transaction.atomic
def attendance_delete_month(request):
    if request.user.role != 'admin':
        messages.error(request, 'Only admin can delete attendance records')
        return redirect('attendance_list')

    def _parse_int(val, default=None, min_val=None, max_val=None):
        try:
            v = int(val)
            if min_val is not None and v < min_val:
                return default
            if max_val is not None and v > max_val:
                return default
            return v
        except (ValueError, TypeError):
            return default

    if request.method == 'POST':
        employee_id = _parse_int(request.POST.get('employee_id'))
        month = _parse_int(request.POST.get('month'), min_val=1, max_val=12)
        year = _parse_int(request.POST.get('year'), min_val=2000, max_val=2100)

        if not employee_id or not month or not year:
            messages.error(request, 'Invalid parameters')
            return redirect('attendance_list')

        employee = get_object_or_404(Employee, id=employee_id)

        from calendar import monthrange
        start_date = date(year, month, 1)
        end_date = date(year, month, monthrange(year, month)[1])

        attendances_to_delete = Attendance.objects.filter(
            employee=employee,
            date__range=[start_date, end_date]
        )
        count = attendances_to_delete.count()

        if count == 0:
            messages.warning(request, f'No attendance records found for {employee.user.get_full_name()} in {month}/{year}')
            return redirect('attendance_list')

        attendances_to_delete.delete()

        messages.success(request, f'Successfully deleted {count} attendance records for {employee.user.get_full_name()} in {month}/{year}')
        return redirect('attendance_list')

    employee_id = _parse_int(request.GET.get('employee'))
    month = _parse_int(request.GET.get('month'), min_val=1, max_val=12)
    year = _parse_int(request.GET.get('year'), min_val=2000, max_val=2100)

    if not employee_id or not month or not year:
        messages.error(request, 'Invalid parameters')
        return redirect('attendance_list')

    employee = get_object_or_404(Employee, id=employee_id)

    from calendar import monthrange
    start_date = date(year, month, 1)
    end_date = date(year, month, monthrange(year, month)[1])

    attendances_to_delete = Attendance.objects.filter(
        employee=employee,
        date__range=[start_date, end_date]
    )
    count = attendances_to_delete.count()

    if count == 0:
        messages.warning(request, f'No attendance records found for {employee.user.get_full_name()} in {month}/{year}')
        return redirect('attendance_list')

    return render(request, 'attendance/attendance_delete_confirm.html', {
        'employee': employee,
        'month': month,
        'year': year,
        'count': count,
        'start_date': start_date,
        'end_date': end_date
    })
