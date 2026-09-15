from django.urls import path
from . import views
from . import advance_views

urlpatterns = [
    path('', views.attendance_list, name='attendance_list'),
    path('create/', views.attendance_create, name='attendance_create'),
    path('my/', views.my_attendance, name='my_attendance'),
    path('delete-month/', views.attendance_delete_month, name='attendance_delete_month'),
]

# Employee Advance URLs — mounted under /attendance/advance/
urlpatterns += [
    path('advance/', advance_views.advance_dashboard, name='advance_dashboard'),
    path('advance/employee/<int:employee_id>/', advance_views.employee_advance_detail, name='employee_advance_detail'),
    path('advance/add/', advance_views.add_advance, name='add_advance'),
    path('advance/repayment/', advance_views.record_repayment, name='record_repayment'),
    path('advance/transaction/<int:transaction_id>/edit/', advance_views.edit_transaction, name='edit_transaction'),
    path('advance/transaction/<int:transaction_id>/delete/', advance_views.delete_transaction, name='delete_transaction'),
]
