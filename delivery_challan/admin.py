from django.contrib import admin
from .models import DeliveryChallan, DeliveryChallanItem, DeliveryChallanAuditLog


class DeliveryChallanItemInline(admin.TabularInline):
    model = DeliveryChallanItem
    extra = 0
    readonly_fields = (
        'job_number', 'job_name', 'job_date', 'paper_size', 'paper_gsm',
        'paper_type', 'quantity', 'printing_color', 'printing_type',
        'machine', 'operator', 'manual_cost', 'remarks'
    )

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class DeliveryChallanAuditLogInline(admin.TabularInline):
    model = DeliveryChallanAuditLog
    extra = 0
    readonly_fields = ('action', 'field_name', 'old_value', 'new_value', 'reason', 'performed_by', 'date', 'time', 'created_at')

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(DeliveryChallan)
class DeliveryChallanAdmin(admin.ModelAdmin):
    list_display = (
        'challan_number', 'challan_date', 'client', 'status',
        'number_of_jobs', 'total_quantity', 'total_cost', 'created_by'
    )
    list_filter = ('status', 'challan_date')
    search_fields = ('challan_number', 'client__name', 'client__company', 'lr_number', 'vehicle_number')
    readonly_fields = ('challan_number', 'created_by', 'created_at', 'updated_at')
    inlines = [DeliveryChallanItemInline, DeliveryChallanAuditLogInline]
    date_hierarchy = 'challan_date'


@admin.register(DeliveryChallanItem)
class DeliveryChallanItemAdmin(admin.ModelAdmin):
    list_display = (
        'challan', 'job_number', 'job_name', 'paper_size', 'paper_gsm',
        'quantity', 'manual_cost'
    )
    list_filter = ('paper_type', 'printing_type')
    search_fields = ('challan__challan_number', 'job_number', 'job_name')
    readonly_fields = (
        'challan', 'job', 'job_number', 'job_name', 'job_date', 'paper_size',
        'paper_gsm', 'paper_type', 'quantity', 'printing_color', 'printing_type',
        'machine', 'operator', 'manual_cost', 'remarks'
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(DeliveryChallanAuditLog)
class DeliveryChallanAuditLogAdmin(admin.ModelAdmin):
    list_display = ('challan', 'action', 'performed_by', 'date', 'time')
    list_filter = ('action', 'date')
    search_fields = ('challan__challan_number', 'reason', 'performed_by__username')
    readonly_fields = ('challan', 'action', 'field_name', 'old_value', 'new_value', 'reason', 'performed_by', 'date', 'time', 'created_at')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
