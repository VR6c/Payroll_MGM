import json
from datetime import timedelta
from django.views.generic import TemplateView
from django.utils import timezone
from django.db.models import Count, Q
from accounts.mixins import RoleRequiredMixin
from employees.models import Employee
from attendance.models import Attendance
from leave.models import LeaveRequest, LeaveBalance


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

                # --- Employee chart: last 30-day personal attendance ---
                thirty_days_ago = today - timedelta(days=29)
                personal_att = (
                    Attendance.objects
                    .filter(employee=emp, date__gte=thirty_days_ago, date__lte=today)
                    .values('date', 'status')
                    .order_by('date')
                )
                # Build 30-day label + status map
                att_by_date = {a['date']: a['status'] for a in personal_att}
                sparkline_labels = []
                sparkline_present = []
                sparkline_late = []
                for i in range(30):
                    d = thirty_days_ago + timedelta(days=i)
                    sparkline_labels.append(d.strftime('%d %b'))
                    status = att_by_date.get(d, None)
                    sparkline_present.append(1 if status in ('present', 'overtime', 'checkout_early') else 0)
                    sparkline_late.append(1 if status == 'late' else 0)

                ctx['sparkline_labels'] = sparkline_labels
                ctx['sparkline_present'] = sparkline_present
                ctx['sparkline_late'] = sparkline_late

                # --- Employee chart: leave balance per type ---
                leave_bal_labels = []
                leave_bal_used = []
                leave_bal_remaining = []
                for lb in ctx['leave_balances']:
                    leave_bal_labels.append(lb.leave_type.name)
                    leave_bal_used.append(float(lb.used_days))
                    leave_bal_remaining.append(float(lb.remaining_days))
                ctx['leave_bal_labels'] = leave_bal_labels
                ctx['leave_bal_used'] = leave_bal_used
                ctx['leave_bal_remaining'] = leave_bal_remaining

                # first leave balance for simple display
                first_balance = ctx['leave_balances'].first()
                ctx['leave_balance'] = first_balance

        else:
            # --- Admin KPI ---
            ctx['total_employees'] = Employee.objects.filter(status='active').count()
            ctx['present_today'] = Attendance.objects.filter(
                date=today, status__in=['present', 'late', 'overtime', 'checkout_early']
            ).count()
            ctx['late_today'] = Attendance.objects.filter(date=today, status='late').count()
            ctx['pending_leaves'] = LeaveRequest.objects.filter(status='pending').count()
            ctx['recent_employees'] = Employee.objects.select_related(
                'department', 'position', 'company'
            ).order_by('-created_at')[:5]

            # --- 30-Day & 7-Day Attendance Chart Datasets ---
            thirty_days_ago = today - timedelta(days=29)
            att_30_qs = (
                Attendance.objects
                .filter(date__gte=thirty_days_ago, date__lte=today)
                .values('date', 'status')
            )
            att_map = {}
            for rec in att_30_qs:
                d = rec['date']
                s = rec['status']
                if d not in att_map:
                    att_map[d] = {'present': 0, 'late': 0, 'absent': 0}
                if s in ('present', 'overtime', 'checkout_early'):
                    att_map[d]['present'] += 1
                elif s == 'late':
                    att_map[d]['late'] += 1
                elif s == 'absent':
                    att_map[d]['absent'] += 1

            # 30-day series
            labels_30 = []
            present_30 = []
            late_30 = []
            absent_30 = []
            for i in range(29, -1, -1):
                d = today - timedelta(days=i)
                labels_30.append(d.strftime('%d %b'))
                cnt = att_map.get(d, {'present': 0, 'late': 0, 'absent': 0})
                present_30.append(cnt['present'])
                late_30.append(cnt['late'])
                absent_30.append(cnt['absent'])

            # 7-day series
            labels_7 = []
            present_7 = []
            late_7 = []
            absent_7 = []
            for i in range(6, -1, -1):
                d = today - timedelta(days=i)
                labels_7.append(d.strftime('%a %d'))
                cnt = att_map.get(d, {'present': 0, 'late': 0, 'absent': 0})
                present_7.append(cnt['present'])
                late_7.append(cnt['late'])
                absent_7.append(cnt['absent'])

            total_active = ctx['total_employees'] or 1  # avoid division by zero
            ctx['chart_labels_7'] = labels_7
            ctx['chart_present_7'] = present_7
            ctx['chart_late_7'] = late_7
            ctx['chart_absent_7'] = absent_7

            ctx['chart_labels_30'] = labels_30
            ctx['chart_present_30'] = present_30
            ctx['chart_late_30'] = late_30
            ctx['chart_absent_30'] = absent_30

            # --- Attendance Rate gauge data (Today, Last 7 Days, Last 30 Days) ---
            att_rate_today = round((ctx['present_today'] / total_active) * 100, 1) if total_active else 0
            ctx['attendance_rate'] = att_rate_today

            # 7-day rate & totals
            sum_p7 = sum(present_7)
            sum_l7 = sum(late_7)
            logged_days_7 = sum(1 for p, l, a in zip(present_7, late_7, absent_7) if (p + l + a) > 0) or 1
            expected_7 = total_active * logged_days_7
            rate_7 = round((sum_p7 / expected_7) * 100, 1) if expected_7 else 0

            # 30-day rate & totals
            sum_p30 = sum(present_30)
            sum_l30 = sum(late_30)
            logged_days_30 = sum(1 for p, l, a in zip(present_30, late_30, absent_30) if (p + l + a) > 0) or 1
            expected_30 = total_active * logged_days_30
            rate_30 = round((sum_p30 / expected_30) * 100, 1) if expected_30 else 0

            ctx['gauge_periods'] = {
                'today': {
                    'rate': att_rate_today,
                    'present': ctx['present_today'],
                    'late': ctx['late_today'],
                    'total': total_active,
                },
                '7': {
                    'rate': rate_7,
                    'present': sum_p7,
                    'late': sum_l7,
                    'total': expected_7,
                },
                '30': {
                    'rate': rate_30,
                    'present': sum_p30,
                    'late': sum_l30,
                    'total': expected_30,
                }
            }

            # --- Leave Analysis: status breakdown (all time / this year) ---
            leave_qs = LeaveRequest.objects.filter(created_at__year=today.year)
            leave_approved = leave_qs.filter(status='approved').count()
            leave_pending = leave_qs.filter(status='pending').count()
            leave_rejected = leave_qs.filter(status='rejected').count()
            leave_cancelled = leave_qs.filter(status='cancelled').count()
            ctx['leave_approved'] = leave_approved
            ctx['leave_pending'] = leave_pending
            ctx['leave_rejected'] = leave_rejected
            ctx['leave_cancelled'] = leave_cancelled
            ctx['leave_doughnut_data'] = [leave_approved, leave_pending, leave_rejected, leave_cancelled]
            ctx['leave_doughnut_labels'] = ['Approved', 'Pending', 'Rejected', 'Cancelled']

            # --- Leave type breakdown (top 5 types by count) ---
            leave_by_type = (
                leave_qs
                .values('leave_type__name')
                .annotate(count=Count('id'))
                .order_by('-count')[:6]
            )
            ctx['leave_type_labels'] = [lt['leave_type__name'] or 'Unknown' for lt in leave_by_type]
            ctx['leave_type_data'] = [lt['count'] for lt in leave_by_type]

        return ctx
