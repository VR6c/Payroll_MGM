from django.views.generic import TemplateView
from django.utils import timezone
from accounts.mixins import RoleRequiredMixin
from employees.models import Employee
from attendance.models import Attendance
from leave.models import LeaveRequest
from activities.models import Activity

class DashboardView(RoleRequiredMixin, TemplateView):
    template_name = 'dashboard/home.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        today = timezone.localdate()
        if user.role == 'employee':
            emp = getattr(user, 'employee_profile', None)
            if emp:
                ctx['today_attendance'] = Attendance.objects.filter(employee=emp, date=today).first()
                ctx['leave_balances'] = emp.leave_balances.select_related('leave_type').filter(year=today.year)
                ctx['recent_payslips'] = emp.payrolls.order_by('-payroll_period')[:5]
                ctx['my_recent_leaves'] = emp.leave_requests.select_related('leave_type').order_by('-created_at')[:5]
        else:
            ctx['total_employees'] = Employee.objects.filter(status='active').count()
            ctx['present_today'] = Attendance.objects.filter(date=today, status__in=['present', 'late', 'overtime', 'early_leave']).count()
            ctx['late_today'] = Attendance.objects.filter(date=today, status='late').count()
            ctx['pending_leaves'] = LeaveRequest.objects.filter(status='pending').count()
            ctx['recent_activities'] = Activity.objects.select_related('user', 'employee').order_by('-created_at')[:6]
            ctx['recent_employees'] = Employee.objects.select_related('department', 'position', 'company').order_by('-created_at')[:5]
        return ctx

