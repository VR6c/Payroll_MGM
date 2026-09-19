from django.urls import path
from .views import (
    CheckInView, CheckOutView, MyAttendanceView, AttendanceReportView,
    AttendanceReportExcelExportView, AttendanceReportPdfExportView,
    WorkScheduleListView, SaveEmployeeScheduleView, GetEmployeeScheduleView, ExportScheduleView,
    AttendanceCreateView, AttendanceUpdateView, AttendanceDeleteView,
    LunchBreakListView, LunchBreakCreateView, LunchBreakUpdateView, LunchBreakDeleteView
)

app_name = 'attendance'

urlpatterns = [
    path('check-in/', CheckInView.as_view(), name='check_in'),
    path('check-out/', CheckOutView.as_view(), name='check_out'),
    path('my/', MyAttendanceView.as_view(), name='my_attendance'),
    path('breaks/', LunchBreakListView.as_view(), name='lunch_breaks'),
    path('breaks/create/', LunchBreakCreateView.as_view(), name='lunch_break_create'),
    path('breaks/<int:pk>/edit/', LunchBreakUpdateView.as_view(), name='lunch_break_update'),
    path('breaks/<int:pk>/delete/', LunchBreakDeleteView.as_view(), name='lunch_break_delete'),
    path('schedules/', WorkScheduleListView.as_view(), name='schedules'),
    path('schedules/api/save/', SaveEmployeeScheduleView.as_view(), name='save_schedule'),
    path('schedules/api/get/<int:emp_id>/', GetEmployeeScheduleView.as_view(), name='get_schedule'),
    path('schedules/export/', ExportScheduleView.as_view(), name='export_schedules'),
    path('report/', AttendanceReportView.as_view(), name='report'),
    path('report/export/excel/', AttendanceReportExcelExportView.as_view(), name='export_excel'),
    path('report/export/pdf/', AttendanceReportPdfExportView.as_view(), name='export_pdf'),
    path('create/', AttendanceCreateView.as_view(), name='create'),
    path('<int:pk>/edit/', AttendanceUpdateView.as_view(), name='update'),
    path('<int:pk>/delete/', AttendanceDeleteView.as_view(), name='delete'),
]

