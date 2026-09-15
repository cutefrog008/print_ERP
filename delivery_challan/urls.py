from django.urls import path
from . import views

app_name = 'delivery_challan'

urlpatterns = [
    path('', views.challan_list, name='challan_list'),
    path('create/', views.challan_create_step1, name='challan_create'),
    path('create/step2/<int:client_id>/', views.challan_create_step2, name='challan_create_step2'),
    path('detail/<int:pk>/', views.challan_detail, name='challan_detail'),
    path('edit/<int:pk>/', views.challan_edit, name='challan_edit'),
    path('edit/<int:pk>/add-jobs/', views.challan_add_jobs, name='challan_add_jobs'),
    path('edit/<int:pk>/remove-job/<int:item_pk>/', views.challan_remove_job, name='challan_remove_job'),
    path('print/<int:pk>/', views.challan_print, name='challan_print'),
    path('status/<int:pk>/', views.challan_status_update, name='challan_status'),
    path('cancel/<int:pk>/', views.challan_cancel, name='challan_cancel'),
    path('delete/<int:pk>/', views.challan_delete, name='challan_delete'),
    path('bulk-cleanup/', views.bulk_monthly_cleanup, name='bulk_monthly_cleanup'),
]
