from django.contrib import admin
from .models import LunchBreak, Attendance, WorkSchedule, EmployeeSchedule

@admin.register(LunchBreak)
class LunchBreakAdmin(admin.ModelAdmin):
    list_display = ('name', 'break_type', 'start_time', 'end_time', 'duration_minutes', 'auto_deduct', 'company', 'status')
    list_filter = ('break_type', 'auto_deduct', 'status', 'company')
    search_fields = ('name',)

@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('employee', 'date', 'check_in', 'check_out', 'working_hours', 'status')
    list_filter = ('status', 'date')
    search_fields = ('employee__employee_code', 'employee__first_name', 'employee__last_name')

@admin.register(WorkSchedule)
class WorkScheduleAdmin(admin.ModelAdmin):
    list_display = ('name', 'company', 'start_time', 'end_time', 'status')
    list_filter = ('company', 'status')

@admin.register(EmployeeSchedule)
class EmployeeScheduleAdmin(admin.ModelAdmin):
    list_display = ('employee', 'day_of_week', 'is_work_day', 'is_half_day', 'start_time', 'end_time', 'shift_label')
    list_filter = ('day_of_week', 'is_work_day', 'is_half_day')
    search_fields = ('employee__employee_code', 'employee__first_name', 'employee__last_name')
