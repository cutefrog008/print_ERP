from django.urls import path
from . import views
from .backup_status import backup_status_view

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('backup-status/', backup_status_view, name='backup_status'),
]
