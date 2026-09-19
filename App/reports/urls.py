from django.urls import path
from .views import DailyReportView, SummaryReportView, DetailReportView

app_name = 'reports'

urlpatterns = [
    path('daily/', DailyReportView.as_view(), name='daily'),
    path('summary/', SummaryReportView.as_view(), name='summary'),
    path('detail/', DetailReportView.as_view(), name='detail'),
]
