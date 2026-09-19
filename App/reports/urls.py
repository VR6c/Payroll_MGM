from django.urls import path
from .views import (
    DailyReportView, DailyReportExcelExportView, DailyReportPdfExportView,
    SummaryReportView, SummaryReportExcelExportView, SummaryReportPdfExportView,
    DetailReportView, DetailReportExcelExportView, DetailReportPdfExportView,
)

app_name = 'reports'

urlpatterns = [
    path('daily/', DailyReportView.as_view(), name='daily'),
    path('daily/excel/', DailyReportExcelExportView.as_view(), name='daily_excel'),
    path('daily/pdf/', DailyReportPdfExportView.as_view(), name='daily_pdf'),

    path('summary/', SummaryReportView.as_view(), name='summary'),
    path('summary/excel/', SummaryReportExcelExportView.as_view(), name='summary_excel'),
    path('summary/pdf/', SummaryReportPdfExportView.as_view(), name='summary_pdf'),

    path('detail/', DetailReportView.as_view(), name='detail'),
    path('detail/excel/', DetailReportExcelExportView.as_view(), name='detail_excel'),
    path('detail/pdf/', DetailReportPdfExportView.as_view(), name='detail_pdf'),
]
