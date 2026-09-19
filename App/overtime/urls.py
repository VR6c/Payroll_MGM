from django.urls import path
from .views import (
    OvertimeListView,
    OvertimeCreateView,
    OvertimeUpdateView,
    OvertimeDeleteView,
    OvertimeApproveView,
    OvertimeRejectView,
    OvertimeTypeListView,
    OvertimeTypeCreateView,
    OvertimeTypeUpdateView,
    OvertimeTypeDeleteView,
    MyOvertimeListView,
    MyOvertimeCreateView,
    MyOvertimeCancelView,
    OvertimeReportView,
    OvertimeReportExcelExportView,
    OvertimeReportPdfExportView,
)

app_name = 'overtime'

urlpatterns = [
    # Admin Overtime Records Full CRUD
    path('', OvertimeListView.as_view(), name='list'),
    path('create/', OvertimeCreateView.as_view(), name='create'),
    path('<int:pk>/edit/', OvertimeUpdateView.as_view(), name='edit'),
    path('<int:pk>/delete/', OvertimeDeleteView.as_view(), name='delete'),
    path('<int:pk>/approve/', OvertimeApproveView.as_view(), name='approve'),
    path('<int:pk>/reject/', OvertimeRejectView.as_view(), name='reject'),

    # Admin Overtime Types Full CRUD
    path('types/', OvertimeTypeListView.as_view(), name='types'),
    path('types/create/', OvertimeTypeCreateView.as_view(), name='type_create'),
    path('types/<int:pk>/edit/', OvertimeTypeUpdateView.as_view(), name='type_update'),
    path('types/<int:pk>/delete/', OvertimeTypeDeleteView.as_view(), name='type_delete'),

    # Employee Self-Service
    path('my/', MyOvertimeListView.as_view(), name='my_overtime'),
    path('my/create/', MyOvertimeCreateView.as_view(), name='my_create'),
    path('my/<int:pk>/cancel/', MyOvertimeCancelView.as_view(), name='my_cancel'),

    # Overtime Analytics & Reports
    path('report/', OvertimeReportView.as_view(), name='report'),
    path('report/export/excel/', OvertimeReportExcelExportView.as_view(), name='report_excel'),
    path('report/export/pdf/', OvertimeReportPdfExportView.as_view(), name='report_pdf'),
]
