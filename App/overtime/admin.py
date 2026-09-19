from django.contrib import admin
from .models import OvertimeType, OvertimeRequest


@admin.register(OvertimeType)
class OvertimeTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'company', 'rate_multiplier', 'status', 'created_at')
    list_filter = ('status', 'company')
    search_fields = ('name', 'description')


@admin.register(OvertimeRequest)
class OvertimeRequestAdmin(admin.ModelAdmin):
    list_display = ('employee', 'date', 'hours', 'rate_multiplier', 'overtime_amount', 'status', 'approved_by')
    list_filter = ('status', 'date', 'overtime_type')
    search_fields = ('employee__first_name', 'employee__last_name', 'employee__employee_code', 'reason')
    date_hierarchy = 'date'
