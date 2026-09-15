from django.urls import path
from . import views

urlpatterns = [
    path('', views.client_list, name='client_list'),
    path('create/', views.client_create, name='client_create'),
    path('update/<int:pk>/', views.client_update, name='client_update'),
    path('detail/<int:pk>/', views.client_detail, name='client_detail'),
    path('delete/<int:pk>/', views.client_delete, name='client_delete'),
    path('archive/<int:pk>/', views.client_archive, name='client_archive'),
    path('restore/<int:pk>/', views.client_restore, name='client_restore'),
    path('payment/create/<int:client_pk>/', views.client_payment_create, name='client_payment_create'),
    path('payment/update/<int:pk>/', views.client_payment_update, name='client_payment_update'),
    path('payment/delete/<int:pk>/', views.client_payment_delete, name='client_payment_delete'),
]
