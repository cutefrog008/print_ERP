from django.urls import path
from . import views

app_name = 'pricing'

urlpatterns = [
    # Client Pricing Configuration
    path('client/<int:client_id>/', views.client_pricing_config, name='client_pricing_config'),
    
    # Paper Pricing
    path('client/<int:client_id>/paper/', views.paper_pricing_list, name='paper_pricing_list'),
    path('client/<int:client_id>/paper/create/', views.paper_pricing_create, name='paper_pricing_create'),
    path('client/<int:client_id>/paper/<int:pk>/update/', views.paper_pricing_update, name='paper_pricing_update'),
    path('client/<int:client_id>/paper/<int:pk>/delete/', views.paper_pricing_delete, name='paper_pricing_delete'),
    
    # Printing Pricing
    path('client/<int:client_id>/printing/', views.printing_pricing_list, name='printing_pricing_list'),
    path('client/<int:client_id>/printing/create/', views.printing_pricing_create, name='printing_pricing_create'),
    path('client/<int:client_id>/printing/<int:pk>/update/', views.printing_pricing_update, name='printing_pricing_update'),
    path('client/<int:client_id>/printing/<int:pk>/delete/', views.printing_pricing_delete, name='printing_pricing_delete'),
    
    # Plate Pricing
    path('client/<int:client_id>/plate/', views.plate_pricing_list, name='plate_pricing_list'),
    path('client/<int:client_id>/plate/create/', views.plate_pricing_create, name='plate_pricing_create'),
    path('client/<int:client_id>/plate/<int:pk>/update/', views.plate_pricing_update, name='plate_pricing_update'),
    path('client/<int:client_id>/plate/<int:pk>/delete/', views.plate_pricing_delete, name='plate_pricing_delete'),
    
    # Additional Charges
    path('client/<int:client_id>/charges/', views.additional_charges_list, name='additional_charges_list'),
    path('client/<int:client_id>/charges/create/', views.additional_charge_create, name='additional_charge_create'),
    path('client/<int:client_id>/charges/<int:pk>/update/', views.additional_charge_update, name='additional_charge_update'),
    path('client/<int:client_id>/charges/<int:pk>/delete/', views.additional_charge_delete, name='additional_charge_delete'),
    
    # Pricing History
    path('client/<int:client_id>/history/', views.pricing_history, name='pricing_history'),
]
