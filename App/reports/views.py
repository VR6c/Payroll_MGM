from django.views.generic import TemplateView
from accounts.mixins import RoleRequiredMixin
from employees.models import Employee
from attendance.models import Attendance
from leave.models import LeaveRequest
from payroll.models import Payroll
from django.db.models import Sum, Count, Q
from django.utils import timezone

class DailyReportView(RoleRequiredMixin, TemplateView):
    template_name = 'reports/daily.html'
    required_roles = ['super_admin', 'hr_admin', 'manager']

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = timezone.now().date()
        ctx['today'] = today
        ctx['total_employees'] = Employee.objects.filter(status='active').count()
        ctx['today_attendances'] = Attendance.objects.filter(date=today).select_related('employee', 'employee__department', 'employee__position')
        
        counts = Attendance.objects.filter(date=today).aggregate(
            present=Count('id', filter=Q(status='present')),
            late=Count('id', filter=Q(status='late')),
            absent=Count('id', filter=Q(status='absent'))
        )
        ctx['present_count'] = counts['present'] or 0
        ctx['late_count'] = counts['late'] or 0
        ctx['absent_count'] = counts['absent'] or 0
        return ctx

class SummaryReportView(RoleRequiredMixin, TemplateView):
    template_name = 'reports/summary.html'
    required_roles = ['super_admin', 'hr_admin', 'manager']

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['total_employees'] = Employee.objects.count()
        ctx['active_employees'] = Employee.objects.filter(status='active').count()
        ctx['total_payroll_sum'] = Payroll.objects.aggregate(total=Sum('net_salary'))['total'] or 0
        ctx['leave_requests_count'] = LeaveRequest.objects.count()
        ctx['payrolls'] = Payroll.objects.select_related('employee', 'employee__department').order_by('-payroll_period')[:20]
        return ctx

class DetailReportView(RoleRequiredMixin, TemplateView):
    template_name = 'reports/detail.html'
    required_roles = ['super_admin', 'hr_admin', 'manager']

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['employees'] = Employee.objects.select_related('department', 'position').all()
        ctx['attendances'] = Attendance.objects.select_related('employee').order_by('-date')[:30]
        ctx['payrolls'] = Payroll.objects.select_related('employee').order_by('-payroll_period')[:30]
        return ctx
