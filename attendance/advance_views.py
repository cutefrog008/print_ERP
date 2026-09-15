from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Q
from .models import EmployeeAdvanceTransaction
from employees.models import Employee
from .forms import AddAdvanceForm, RecordRepaymentForm, EditTransactionForm


@login_required
def advance_dashboard(request):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to view this page')
        return redirect('dashboard')
    
    # Get search/filter parameters
    search = request.GET.get('search', '')
    transaction_type = request.GET.get('transaction_type', '')
    
    # Calculate overall totals
    total_taken = EmployeeAdvanceTransaction.objects.filter(
        transaction_type='TAKEN'
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    total_returned = EmployeeAdvanceTransaction.objects.filter(
        transaction_type='REPAYMENT'
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    total_pending = total_taken - total_returned
    
    # Get employees with advances
    employees_with_advances = Employee.objects.filter(
        advance_transactions__isnull=False
    ).distinct()
    
    # Build employee summary
    employee_summaries = []
    for employee in employees_with_advances:
        taken = EmployeeAdvanceTransaction.objects.filter(
            employee=employee,
            transaction_type='TAKEN'
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        returned = EmployeeAdvanceTransaction.objects.filter(
            employee=employee,
            transaction_type='REPAYMENT'
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        pending = taken - returned
        
        if pending > 0 or taken > 0:
            employee_summaries.append({
                'employee': employee,
                'total_taken': taken,
                'total_returned': returned,
                'pending': pending
            })
    
    # Sort by pending amount (highest first)
    employee_summaries.sort(key=lambda x: x['pending'], reverse=True)
    
    # Filter by search
    if search:
        employee_summaries = [
            es for es in employee_summaries
            if search.lower() in es['employee'].user.get_full_name().lower()
        ]
    
    context = {
        'total_employees_with_advance': len(employee_summaries),
        'total_taken': total_taken,
        'total_returned': total_returned,
        'total_pending': total_pending,
        'employee_summaries': employee_summaries,
        'search': search,
        'transaction_type': transaction_type,
    }
    
    return render(request, 'employee_advances/dashboard.html', context)


@login_required
def employee_advance_detail(request, employee_id):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to view this page')
        return redirect('dashboard')
    
    employee = get_object_or_404(Employee, id=employee_id)
    
    # Get all transactions for this employee
    transactions = EmployeeAdvanceTransaction.objects.filter(
        employee=employee
    ).order_by('transaction_date', 'created_at')
    
    # Calculate totals
    total_taken = EmployeeAdvanceTransaction.objects.filter(
        employee=employee,
        transaction_type='TAKEN'
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    total_returned = EmployeeAdvanceTransaction.objects.filter(
        employee=employee,
        transaction_type='REPAYMENT'
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    pending = total_taken - total_returned
    
    # Calculate running balance for each transaction
    transactions_with_balance = []
    running_balance = 0
    for tx in transactions:
        if tx.transaction_type == 'TAKEN':
            running_balance += tx.amount
        elif tx.transaction_type == 'REPAYMENT':
            running_balance -= tx.amount
        transactions_with_balance.append({
            'transaction': tx,
            'balance_after': running_balance
        })
    
    # Reverse for display (newest first)
    transactions_with_balance.reverse()
    
    context = {
        'employee': employee,
        'transactions': transactions_with_balance,
        'total_taken': total_taken,
        'total_returned': total_returned,
        'pending': pending,
    }
    
    return render(request, 'employee_advances/employee_detail.html', context)


@login_required
def add_advance(request):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to view this page')
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = AddAdvanceForm(request.POST)
        if form.is_valid():
            form.save(user=request.user)
            messages.success(request, 'Advance added successfully')
            return redirect('advance_dashboard')
    else:
        form = AddAdvanceForm()
    
    return render(request, 'employee_advances/add_advance.html', {'form': form})


@login_required
def record_repayment(request):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to view this page')
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = RecordRepaymentForm(request.POST)
        if form.is_valid():
            form.save(user=request.user)
            messages.success(request, 'Repayment recorded successfully')
            return redirect('advance_dashboard')
    else:
        form = RecordRepaymentForm()
    
    return render(request, 'employee_advances/record_repayment.html', {'form': form})


@login_required
def edit_transaction(request, transaction_id):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to view this page')
        return redirect('dashboard')
    
    transaction = get_object_or_404(EmployeeAdvanceTransaction, id=transaction_id)
    
    if request.method == 'POST':
        form = EditTransactionForm(request.POST, instance=transaction)
        if form.is_valid():
            form.save()
            messages.success(request, 'Transaction updated successfully')
            return redirect('employee_advance_detail', employee_id=transaction.employee.id)
    else:
        form = EditTransactionForm(instance=transaction)
    
    return render(request, 'employee_advances/edit_transaction.html', {
        'form': form,
        'transaction': transaction
    })


@login_required
def delete_transaction(request, transaction_id):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to view this page')
        return redirect('dashboard')
    
    transaction = get_object_or_404(EmployeeAdvanceTransaction, id=transaction_id)
    employee_id = transaction.employee.id
    
    if request.method == 'POST':
        transaction.delete()
        messages.success(request, 'Transaction deleted successfully')
        return redirect('employee_advance_detail', employee_id=employee_id)
    
    return render(request, 'employee_advances/delete_confirm.html', {
        'transaction': transaction
    })
