from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.urls import reverse
from datetime import date, timedelta, datetime
from .models import Attendance, Holiday
from employees.models import Employee
from .forms import AttendanceForm, AttendanceEditForm, HolidayForm
from django.db import transaction


@login_required
def attendance_list(request):
    if request.user.role not in ['admin', 'manager']:
        messages.error(request, 'You do not have permission to view this page')
        return redirect('dashboard')

    employee_id = request.GET.get('employee')
    date_param = request.GET.get('date')
    month_param = request.GET.get('month')
    year_param = request.GET.get('year')

    today = date.today()

    # When an employee is selected we show a full month (with leave/overtime totals).
    # Otherwise we show a single day for all employees.
    is_employee_view = bool(employee_id)

    selected_employee = None
    total_overtime = None
    total_leave_days = None
    filter_date = today
    month_start = None
    month_end = None

    if is_employee_view:
        try:
            employee_id = int(employee_id)
        except (ValueError, TypeError):
            employee_id = None
        if employee_id:
            try:
                selected_employee = Employee.objects.get(id=employee_id)
            except Employee.DoesNotExist:
                selected_employee = None

            if selected_employee:
                try:
                    sel_month = int(month_param) if month_param else today.month
                    if sel_month < 1 or sel_month > 12:
                        sel_month = today.month
                except (ValueError, TypeError):
                    sel_month = today.month
                try:
                    sel_year = int(year_param) if year_param else today.year
                    if sel_year < 2000 or sel_year > 2100:
                        sel_year = today.year
                except (ValueError, TypeError):
                    sel_year = today.year

                from calendar import monthrange
                month_start = date(sel_year, sel_month, 1)
                month_end = date(sel_year, sel_month, monthrange(sel_year, sel_month)[1])

                attendances = Attendance.objects.filter(
                    employee_id=employee_id,
                    date__range=[month_start, month_end],
                ).order_by('-date')

                total_overtime = timedelta(0)
                for attendance in attendances:
                    if attendance.overtime:
                        total_overtime += attendance.overtime
                # Leave/Absent days only count on actual working days
                # (Sundays and public holidays are excluded).
                holiday_set = set(
                    Holiday.objects.filter(
                        date__range=[month_start, month_end]
                    ).values_list('date', flat=True)
                )
                total_leave_days = sum(
                    1 for a in attendances
                    if a.status == 'leave'
                    and a.date.weekday() != 6
                    and a.date not in holiday_set
                )
            else:
                # employee id was invalid
                is_employee_view = False

    if not is_employee_view:
        # All employees, single-day view.
        try:
            filter_date = datetime.strptime(date_param, '%Y-%m-%d').date() if date_param else today
        except (ValueError, TypeError):
            filter_date = today

        attendances = Attendance.objects.filter(date=filter_date).order_by(
            '-date', 'employee__user__first_name'
        )

        from calendar import monthrange
        month_start = date(filter_date.year, filter_date.month, 1)
        month_end = date(filter_date.year, filter_date.month, monthrange(filter_date.year, filter_date.month)[1])

    employees = Employee.objects.filter(status='active')

    month_options = []
    for i in range(12):
        month_date = today.replace(day=1) - timedelta(days=i * 30)
        month_options.append({
            'month': month_date.month,
            'year': month_date.year,
            'label': month_date.strftime('%B %Y'),
        })

    return render(request, 'attendance/attendance_list.html', {
        'attendances': attendances,
        'employees': employees,
        'selected_employee': selected_employee,
        'is_employee_view': is_employee_view,
        'filter_date': filter_date,
        'is_today': filter_date == today,
        'month_start': month_start,
        'month_end': month_end,
        'selected_month': month_start.month,
        'selected_year': month_start.year,
        'month_options': month_options,
        'total_overtime': total_overtime,
        'total_leave_days': total_leave_days,
    })


@login_required
@transaction.atomic
def attendance_create(request):
    if request.user.role not in ['admin', 'manager']:
        messages.error(request, 'You do not have permission to view this page')
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = AttendanceForm(request.POST)
        if form.is_valid():
            employees = form.cleaned_data.get('employees')
            attendance_date = form.cleaned_data.get('date')
            
            success_count = 0
            skipped_count = 0
            
            for employee in employees:
                # Check if attendance already exists for this employee and date
                if Attendance.objects.filter(employee=employee, date=attendance_date).exists():
                    skipped_count += 1
                    continue
                
                attendance = Attendance(
                    employee=employee,
                    date=attendance_date,
                    time=form.cleaned_data.get('time'),
                    in_time=form.cleaned_data.get('in_time'),
                    out_time=form.cleaned_data.get('out_time'),
                    status=form.cleaned_data.get('status'),
                    remarks=form.cleaned_data.get('remarks'),
                    marked_by=request.user
                )
                attendance.save()
                success_count += 1
            
            if success_count > 0:
                msg = f'Attendance marked successfully for {success_count} employee(s).'
                if skipped_count > 0:
                    msg += f' Skipped {skipped_count} employee(s) who already had records for this date.'
                messages.success(request, msg)
            elif skipped_count > 0:
                messages.warning(request, f'No records created. All {skipped_count} selected employee(s) already have records for this date.')
            
            return redirect('attendance_list')
    else:
        form = AttendanceForm()
    return render(request, 'attendance/attendance_form.html', {
        'form': form,
    })


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
def attendance_edit(request, pk):
    if request.user.role != 'admin':
        messages.error(request, 'Only admin can edit attendance records')
        return redirect('attendance_list')

    attendance = get_object_or_404(Attendance, pk=pk)

    if request.method == 'POST':
        form = AttendanceEditForm(request.POST, instance=attendance)
        if form.is_valid():
            form.save()
            messages.success(request, 'Attendance updated successfully')
            return redirect(_attendance_list_return_url(request))
    else:
        form = AttendanceEditForm(instance=attendance)

    return render(request, 'attendance/attendance_edit.html', {
        'form': form,
        'attendance': attendance,
    })


@login_required
def attendance_delete(request, pk):
    if request.user.role != 'admin':
        messages.error(request, 'Only admin can delete attendance records')
        return redirect('attendance_list')

    attendance = get_object_or_404(Attendance, pk=pk)

    if request.method == 'POST':
        employee_name = attendance.employee.user.get_full_name()
        attendance_date = attendance.date
        attendance.delete()
        messages.success(request, f'Attendance record for {employee_name} on {attendance_date} deleted successfully')
        return redirect(_attendance_list_return_url(request))

    return redirect('attendance_list')


def _attendance_list_return_url(request):
    """Send the admin back to the same filtered attendance view they came from."""
    params = request.GET.urlencode()
    url = reverse('attendance_list')
    return f'{url}?{params}' if params else url


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


@login_required
def holiday_list(request):
    if request.user.role != 'admin':
        messages.error(request, 'Only admin can manage holidays')
        return redirect('dashboard')

    holidays = Holiday.objects.all().order_by('-date')

    if request.method == 'POST':
        form = HolidayForm(request.POST)
        if form.is_valid():
            holiday = form.save(commit=False)
            holiday.created_by = request.user
            holiday.save()
            messages.success(request, f'Holiday "{holiday.name}" added for {holiday.date}')
            return redirect('holiday_list')
    else:
        form = HolidayForm()

    return render(request, 'attendance/holiday_list.html', {
        'holidays': holidays,
        'form': form,
    })


@login_required
def holiday_delete(request, pk):
    if request.user.role != 'admin':
        messages.error(request, 'Only admin can delete holidays')
        return redirect('dashboard')

    holiday = get_object_or_404(Holiday, pk=pk)
    if request.method == 'POST':
        name = holiday.name
        holiday.delete()
        messages.success(request, f'Holiday "{name}" removed')
    return redirect('holiday_list')
