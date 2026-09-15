from django.urls import path
from . import views

urlpatterns = [
    path('', views.job_list, name='job_list'),
    path('create/', views.job_create, name='job_create'),
    path('detail/<int:pk>/', views.job_detail, name='job_detail'),
    path('update/<int:pk>/', views.job_update, name='job_update'),
    path('cancel/<int:pk>/', views.job_cancel, name='job_cancel'),
    path('delete/<int:pk>/', views.job_delete, name='job_delete'),
    path('costing/create/<int:pk>/', views.job_costing_create, name='job_costing_create'),
    path('costing/update/<int:pk>/', views.job_costing_update, name='job_costing_update'),
    path('costing/charge/add/<int:pk>/', views.job_additional_charge_add, name='job_additional_charge_add'),
    path('costing/charge/delete/<int:pk>/<int:charge_pk>/', views.job_additional_charge_delete, name='job_additional_charge_delete'),
]
