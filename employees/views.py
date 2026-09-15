from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.hashers import make_password
from .models import Employee
from accounts.models import User
from .forms import EmployeeForm


@login_required
def employee_list(request):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to view this page')
        return redirect('dashboard')
    employees = Employee.objects.all()
    return render(request, 'employees/employee_list.html', {'employees': employees})


@login_required
def employee_create(request):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to view this page')
        return redirect('dashboard')
    if request.method == 'POST':
        form = EmployeeForm(request.POST, request.FILES)
        if form.is_valid():
            employee = form.save(commit=False)
            password = form.cleaned_data.get('password')
            email = form.cleaned_data.get('email') or ''
            email = email.strip()
            user = User.objects.create_user(
                username=form.cleaned_data['username'],
                password=password,
                first_name=form.cleaned_data['first_name'],
                last_name=form.cleaned_data['last_name'],
                role=form.cleaned_data['role'],
                email=email if email else ''
            )
            employee.user = user
            employee.save()
            messages.success(request, 'Employee created successfully')
            return redirect('employee_list')
    else:
        form = EmployeeForm()
    return render(request, 'employees/employee_form.html', {'form': form})


@login_required
def employee_update(request, pk):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to view this page')
        return redirect('dashboard')
    employee = get_object_or_404(Employee, pk=pk)
    if request.method == 'POST':
        form = EmployeeForm(request.POST, request.FILES, instance=employee)
        if form.is_valid():
            employee = form.save(commit=False)
            user = employee.user
            user.username = form.cleaned_data['username']
            user.first_name = form.cleaned_data['first_name']
            user.last_name = form.cleaned_data['last_name']
            user.role = form.cleaned_data['role']
            email = form.cleaned_data.get('email') or ''
            email = email.strip()
            if email:
                user.email = email
            password = form.cleaned_data.get('password')
            if password:
                user.password = make_password(password)
            user.save()
            employee.save()
            messages.success(request, 'Employee updated successfully')
            return redirect('employee_list')
    else:
        initial = {
            'username': employee.user.username,
            'first_name': employee.user.first_name,
            'last_name': employee.user.last_name,
            'email': employee.user.email,
            'role': employee.user.role
        }
        form = EmployeeForm(instance=employee, initial=initial)
    return render(request, 'employees/employee_form.html', {'form': form})


@login_required
def employee_delete(request, pk):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to view this page')
        return redirect('dashboard')
    employee = get_object_or_404(Employee, pk=pk)
    if request.method == 'POST':
        # Delete the associated User
        employee.user.delete()
        messages.success(request, 'Employee deleted successfully')
        return redirect('employee_list')
    return render(request, 'employees/employee_confirm_delete.html', {'employee': employee})
