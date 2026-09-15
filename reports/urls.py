from django.urls import path
from . import views

urlpatterns = [
    path('', views.report_list, name='report_list'),
    path('production/', views.production_report, name='production_report'),
    path('attendance/', views.attendance_report, name='attendance_report'),
    path('clients/', views.client_report, name='client_report'),
    path('employee-productivity/', views.employee_productivity_report, name='employee_productivity_report'),
]
