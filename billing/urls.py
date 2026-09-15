from django.urls import path
from . import views

urlpatterns = [
    path('', views.invoice_list, name='invoice_list'),
    path('create/', views.invoice_create, name='invoice_create'),
    path('update/<int:pk>/', views.invoice_update, name='invoice_update'),
    path('detail/<int:pk>/', views.invoice_detail, name='invoice_detail'),
    path('detail/<int:invoice_pk>/items/add/', views.invoice_item_add, name='invoice_item_add'),
    path('detail/<int:invoice_pk>/items/update/<int:item_pk>/', views.invoice_item_update, name='invoice_item_update'),
    path('detail/<int:invoice_pk>/items/delete/<int:item_pk>/', views.invoice_item_delete, name='invoice_item_delete'),
    path('payment/<int:invoice_pk>/', views.payment_create, name='payment_create'),
    path('job-billing/<int:job_pk>/', views.job_billing_create, name='job_billing_create'),
]
