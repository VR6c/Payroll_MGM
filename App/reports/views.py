import datetime
from django.views.generic import TemplateView, View
from django.http import HttpResponse
from django.db.models import Sum, Count, Q, Avg
from django.utils import timezone
from accounts.mixins import RoleRequiredMixin
from companies.models import Company, Department, Branch
from employees.models import Employee
from attendance.models import Attendance, EmployeeSchedule
from leave.models import LeaveRequest, LeavePeriod
from payroll.models import Payroll
from .exporters import (
    generate_daily_attendance_excel,
    generate_daily_attendance_pdf,
    generate_summary_report_excel,
    generate_summary_report_pdf,
    generate_detail_report_excel,
    generate_detail_report_pdf,
)


def _get_company_name():
    c = Company.objects.first()
    return c.name if c else "Payroll MGM Inc"


def _parse_report_date(date_str, default=None):
    if date_str:
        for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d", "%m/%d/%Y"):
            try:
                return datetime.datetime.strptime(date_str.strip(), fmt).date()
            except ValueError:
                continue
    return default if default is not None else timezone.now().date()


def _fmt_days(val):
    if val is None:
        return 0
    vf = float(val)
    if vf == 0:
        return 0
    if vf.is_integer():
        return int(vf)
    # Strip unnecessary zeros e.g. 0.50 -> 0.5, 0.25 -> 0.25, 0.75 -> 0.75
    return float(f"{vf:.2f}".rstrip('0').rstrip('.'))


# ==============================================================================
# DAILY REPORT VIEWS
# ==============================================================================

class DailyReportView(RoleRequiredMixin, TemplateView):
    template_name = 'reports/daily.html'
    required_roles = ['super_admin', 'hr_admin', 'manager']

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        req = self.request

        # Date parsing
        date_str = req.GET.get('date', '').strip()
        report_date = _parse_report_date(date_str, timezone.now().date())
        report_date_str = report_date.strftime("%Y-%m-%d")

        branch_id = req.GET.get('branch', '').strip()
        dept_id = req.GET.get('department', '').strip()
        emp_id = req.GET.get('employee', '').strip()
        show_resign = req.GET.get('show_resign') in ('on', 'true', '1')

        emp_qs = Employee.objects.select_related('company', 'branch', 'department', 'position').all()
        if not show_resign:
            emp_qs = emp_qs.filter(status='active')
        if branch_id:
            emp_qs = emp_qs.filter(branch_id=branch_id)
        if dept_id:
            emp_qs = emp_qs.filter(department_id=dept_id)
        if emp_id:
            emp_qs = emp_qs.filter(id=emp_id)

        employees = list(emp_qs.order_by('first_name', 'last_name'))
        emp_ids = [e.id for e in employees]

        # Attendance query
        att_qs = Attendance.objects.filter(date=report_date, employee_id__in=emp_ids).select_related(
            'employee', 'employee__department', 'employee__position', 'employee__branch'
        )
        att_map = {a.employee_id: a for a in att_qs}

        # Leave query for report_date
        leave_periods = LeavePeriod.objects.filter(
            leave_request__employee_id__in=emp_ids,
            leave_request__status='approved',
            start_date__lte=report_date,
            end_date__gte=report_date
        ).select_related(
            'leave_request', 'leave_request__employee', 'leave_request__employee__department',
            'leave_request__employee__position', 'leave_request__employee__branch',
            'leave_request__leave_type'
        )
        leave_map = {lp.leave_request.employee_id: lp for lp in leave_periods}

        # Schedules
        d_idx = report_date.weekday()
        sched_qs = EmployeeSchedule.objects.filter(day_of_week=d_idx, employee_id__in=emp_ids)
        sched_map = {s.employee_id: s for s in sched_qs}

        daily_records = []
        late_records = []
        early_records = []
        leave_records = []
        absent_records = []
        holiday_records = []

        for idx, emp in enumerate(employees, start=1):
            att = att_map.get(emp.id)
            sched = sched_map.get(emp.id)
            lp = leave_map.get(emp.id)

            emp_name = f"{emp.first_name} {emp.last_name}".strip()
            role_name = emp.position.name if emp.position else "Staff"
            dept_name = emp.department.name if emp.department else "---"
            branch_code = emp.branch.code or emp.branch.name if emp.branch else "F2"

            is_off = (sched and not sched.is_work_day) or (d_idx in (5, 6) and not (sched and sched.is_work_day))
            is_half = bool(sched.is_half_day) if sched else False

            if is_off:
                scheduled_day = 0.0
                holiday_val = 1.0
            elif is_half:
                scheduled_day = 0.5
                holiday_val = 0.5
            else:
                scheduled_day = 1.0
                holiday_val = 0.0

            # 1. Leave value
            leave_val = float(lp.days or 0) if lp else 0.0

            # 2. Attendance value
            attend_val = 0.0
            if att and att.status != 'absent':
                if att.working_hours:
                    hrs = att.working_hours.total_seconds() / 3600.0
                    if hrs >= 7.0:
                        attend_val = 1.0
                    elif hrs >= 5.0:
                        attend_val = 0.75
                    elif hrs >= 3.0:
                        attend_val = 0.5
                    elif hrs >= 1.0:
                        attend_val = 0.25
                    else:
                        attend_val = 0.25
                elif leave_val > 0:
                    base_day = scheduled_day if scheduled_day > 0 else 1.0
                    attend_val = max(0.0, base_day - leave_val)
                elif is_half:
                    attend_val = 0.5
                else:
                    attend_val = scheduled_day if scheduled_day > 0 else 1.0

            # 3. Absent value
            if scheduled_day > 0:
                absent_val = max(0.0, scheduled_day - attend_val - leave_val)
            else:
                absent_val = 0.0

            # 1. Holiday List
            if is_off and (attend_val == 0) and (leave_val == 0):
                holiday_records.append({
                    'no': len(holiday_records) + 1,
                    'name': emp_name,
                    'position': role_name,
                    'department': dept_name,
                    'branch': branch_code,
                    'duration': '1.0d',
                    'note': 'Holiday'
                })
            elif is_half:
                holiday_records.append({
                    'no': len(holiday_records) + 1,
                    'name': emp_name,
                    'position': role_name,
                    'department': dept_name,
                    'branch': branch_code,
                    'duration': '0.5d',
                    'note': 'Holiday 0.5d'
                })

            # 2. Leave List
            if leave_val > 0:
                dur_str = f"{_fmt_days(leave_val)}d"
                leave_records.append({
                    'no': len(leave_records) + 1,
                    'name': emp_name,
                    'position': role_name,
                    'department': dept_name,
                    'branch': branch_code,
                    'leave_type': lp.leave_request.leave_type.name if (lp and lp.leave_request and lp.leave_request.leave_type) else 'Leave',
                    'duration': dur_str,
                    'note': (lp.leave_request.reason if lp and lp.leave_request else '') or 'Approved Leave'
                })

            # 3. Late List
            if att and att.status == 'late':
                ci_str = timezone.localtime(att.check_in).strftime('%H:%M') if att.check_in else '---'
                late_note = 'Late Check-in'
                if att.check_in and sched and sched.start_time:
                    ci_time = timezone.localtime(att.check_in).time()
                    diff_mins = (ci_time.hour * 60 + ci_time.minute) - (sched.start_time.hour * 60 + sched.start_time.minute)
                    if diff_mins > 0:
                        late_note = f"Late by {diff_mins} mins"
                late_records.append({
                    'no': len(late_records) + 1,
                    'name': emp_name,
                    'position': role_name,
                    'department': dept_name,
                    'branch': branch_code,
                    'check_in': ci_str,
                    'note': late_note
                })

            # 4. Early Leave List
            if att and att.status == 'early_leave':
                co_str = timezone.localtime(att.check_out).strftime('%H:%M') if att.check_out else '---'
                early_note = 'Early Check-out'
                if att.check_out and sched and sched.end_time:
                    co_time = timezone.localtime(att.check_out).time()
                    diff_mins = (sched.end_time.hour * 60 + sched.end_time.minute) - (co_time.hour * 60 + co_time.minute)
                    if diff_mins > 0:
                        early_note = f"Left early by {diff_mins} mins"
                early_records.append({
                    'no': len(early_records) + 1,
                    'name': emp_name,
                    'position': role_name,
                    'department': dept_name,
                    'branch': branch_code,
                    'check_out': co_str,
                    'note': early_note
                })

            # 5. Absent List (List whenever employee has absent duration)
            if absent_val > 0:
                absent_records.append({
                    'no': len(absent_records) + 1,
                    'name': emp_name,
                    'position': role_name,
                    'department': dept_name,
                    'branch': branch_code,
                    'duration': f"{_fmt_days(absent_val)}d",
                    'note': f"Absent {_fmt_days(absent_val)}d" if absent_val < scheduled_day else 'Absent / No Check-in'
                })

            # 6. Main Attendance List (List ONLY if employee has attended days)
            if attend_val > 0:
                dur_label = f"{_fmt_days(attend_val)}d"
                is_danger = (attend_val < scheduled_day) or (att and att.status in ('late', 'early_leave'))

                daily_records.append({
                    'no': len(daily_records) + 1,
                    'employee': emp,
                    'name': emp_name,
                    'position': role_name,
                    'department': dept_name,
                    'branch': branch_code,
                    'attendance_label': dur_label,
                    'is_danger': is_danger,
                    'attendance': att,
                })

        total_active = len(employees)
        counts = att_qs.aggregate(
            present=Count('id', filter=Q(status='present')),
            late=Count('id', filter=Q(status='late')),
            absent=Count('id', filter=Q(status='absent')),
            early_leave=Count('id', filter=Q(status='early_leave')),
            overtime=Count('id', filter=Q(status='overtime')),
        )

        present_cnt = counts['present'] or 0
        late_cnt = counts['late'] or 0
        absent_cnt = counts['absent'] or 0
        early_leave_cnt = counts['early_leave'] or 0
        ot_cnt = counts['overtime'] or 0

        att_rate = ((present_cnt + late_cnt) / total_active * 100.0) if total_active > 0 else 0.0

        ctx['report_date'] = report_date
        ctx['report_date_str'] = report_date_str
        ctx['total_employees'] = total_active
        ctx['today_attendances'] = att_qs
        ctx['daily_records'] = daily_records
        ctx['late_records'] = late_records
        ctx['early_records'] = early_records
        ctx['leave_records'] = leave_records
        ctx['absent_records'] = absent_records
        ctx['holiday_records'] = holiday_records
        ctx['present_count'] = present_cnt
        ctx['late_count'] = late_cnt
        ctx['absent_count'] = absent_cnt
        ctx['early_leave_count'] = early_leave_cnt
        ctx['overtime_count'] = ot_cnt
        ctx['attendance_rate'] = att_rate

        ctx['branches'] = Branch.objects.filter(status=True)
        ctx['departments'] = Department.objects.filter(status=True)
        ctx['all_employees'] = Employee.objects.filter(status='active').order_by('first_name')
        ctx['selected_branch'] = branch_id
        ctx['selected_dept'] = dept_id
        ctx['selected_employee'] = emp_id
        ctx['show_resign'] = show_resign
        return ctx


class DailyReportExcelExportView(RoleRequiredMixin, View):
    required_roles = ['super_admin', 'hr_admin', 'manager']

    def get(self, request, *args, **kwargs):
        date_str = request.GET.get('date')
        if date_str:
            try:
                report_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                report_date = timezone.now().date()
        else:
            report_date = timezone.now().date()

        dept_id = request.GET.get('department')
        status = request.GET.get('status')

        qs = Attendance.objects.filter(date=report_date).select_related(
            'employee', 'employee__department', 'employee__position'
        ).order_by('employee__first_name')

        if dept_id:
            qs = qs.filter(employee__department_id=dept_id)
        if status:
            qs = qs.filter(status=status)

        total_active = Employee.objects.filter(status='active').count()
        counts = Attendance.objects.filter(date=report_date).aggregate(
            present=Count('id', filter=Q(status='present')),
            late=Count('id', filter=Q(status='late')),
            absent=Count('id', filter=Q(status='absent')),
            early_leave=Count('id', filter=Q(status='early_leave')),
            overtime=Count('id', filter=Q(status='overtime')),
        )

        present_cnt = counts['present'] or 0
        late_cnt = counts['late'] or 0
        stats = {
            'total_employees': total_active,
            'present_count': present_cnt,
            'late_count': late_cnt,
            'absent_count': counts['absent'] or 0,
            'early_leave_count': counts['early_leave'] or 0,
            'overtime_count': counts['overtime'] or 0,
            'attendance_rate': ((present_cnt + late_cnt) / total_active * 100.0) if total_active > 0 else 0.0,
        }

        generated_by = request.user.get_full_name() or request.user.username
        excel_bytes = generate_daily_attendance_excel(
            report_date=report_date,
            attendances=qs,
            stats=stats,
            company_name=_get_company_name(),
            generated_by=generated_by
        )

        filename = f"daily_attendance_report_{report_date.strftime('%Y%m%d')}.xlsx"
        resp = HttpResponse(
            excel_bytes,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        resp['Content-Disposition'] = f'attachment; filename="{filename}"'
        return resp


class DailyReportPdfExportView(RoleRequiredMixin, View):
    required_roles = ['super_admin', 'hr_admin', 'manager']

    def get(self, request, *args, **kwargs):
        date_str = request.GET.get('date')
        if date_str:
            try:
                report_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                report_date = timezone.now().date()
        else:
            report_date = timezone.now().date()

        dept_id = request.GET.get('department')
        status = request.GET.get('status')

        qs = Attendance.objects.filter(date=report_date).select_related(
            'employee', 'employee__department', 'employee__position'
        ).order_by('employee__first_name')

        if dept_id:
            qs = qs.filter(employee__department_id=dept_id)
        if status:
            qs = qs.filter(status=status)

        total_active = Employee.objects.filter(status='active').count()
        counts = Attendance.objects.filter(date=report_date).aggregate(
            present=Count('id', filter=Q(status='present')),
            late=Count('id', filter=Q(status='late')),
            absent=Count('id', filter=Q(status='absent')),
            early_leave=Count('id', filter=Q(status='early_leave')),
            overtime=Count('id', filter=Q(status='overtime')),
        )

        present_cnt = counts['present'] or 0
        late_cnt = counts['late'] or 0
        stats = {
            'total_employees': total_active,
            'present_count': present_cnt,
            'late_count': late_cnt,
            'absent_count': counts['absent'] or 0,
            'early_leave_count': counts['early_leave'] or 0,
            'overtime_count': counts['overtime'] or 0,
            'attendance_rate': ((present_cnt + late_cnt) / total_active * 100.0) if total_active > 0 else 0.0,
        }

        generated_by = request.user.get_full_name() or request.user.username
        pdf_bytes = generate_daily_attendance_pdf(
            report_date=report_date,
            attendances=qs,
            stats=stats,
            company_name=_get_company_name(),
            generated_by=generated_by
        )

        filename = f"daily_attendance_report_{report_date.strftime('%Y%m%d')}.pdf"
        resp = HttpResponse(pdf_bytes, content_type='application/pdf')
        resp['Content-Disposition'] = f'attachment; filename="{filename}"'
        return resp


# ==============================================================================
# SUMMARY REPORT VIEWS
# ==============================================================================

def _get_summary_data(request):
    period_str = request.GET.get('period', '').strip()
    dept_id = request.GET.get('department', '').strip()

    qs = Payroll.objects.select_related('employee', 'employee__department').all().order_by('-payroll_period', 'employee__first_name')

    if period_str:
        # e.g. YYYY-MM
        try:
            parts = period_str.split('-')
            year = int(parts[0])
            month = int(parts[1])
            qs = qs.filter(payroll_period__year=year, payroll_period__month=month)
        except (ValueError, IndexError):
            pass

    if dept_id:
        qs = qs.filter(employee__department_id=dept_id)

    total_employees = Employee.objects.count()
    active_employees = Employee.objects.filter(status='active').count()

    sums = qs.aggregate(
        gross=Sum('gross_salary'),
        deductions=Sum('total_deduction'),
        net=Sum('net_salary'),
        tax=Sum('tax'),
        nssf=Sum('nssf')
    )

    total_gross = sums['gross'] or 0
    total_deductions = sums['deductions'] or 0
    total_net = sums['net'] or 0
    p_count = qs.count()
    avg_salary = (total_net / p_count) if p_count > 0 else 0

    # Department statistics
    dept_stats = []
    departments = Department.objects.filter(status=True)
    for d in departments:
        d_qs = qs.filter(employee__department=d)
        d_sums = d_qs.aggregate(
            gross=Sum('gross_salary'),
            deductions=Sum('total_deduction'),
            net=Sum('net_salary'),
            count=Count('id')
        )
        if d_sums['count'] > 0:
            dept_stats.append({
                'name': d.name,
                'count': d_sums['count'],
                'total_gross': d_sums['gross'] or 0,
                'total_deductions': d_sums['deductions'] or 0,
                'total_net': d_sums['net'] or 0,
            })

    # Catch unassigned
    unassigned_qs = qs.filter(employee__department__isnull=True)
    unassigned_count = unassigned_qs.count()
    if unassigned_count > 0:
        u_sums = unassigned_qs.aggregate(
            gross=Sum('gross_salary'),
            deductions=Sum('total_deduction'),
            net=Sum('net_salary')
        )
        dept_stats.append({
            'name': 'Unassigned',
            'count': unassigned_count,
            'total_gross': u_sums['gross'] or 0,
            'total_deductions': u_sums['deductions'] or 0,
            'total_net': u_sums['net'] or 0,
        })

    summary_stats = {
        'total_employees': total_employees,
        'active_employees': active_employees,
        'total_gross': total_gross,
        'total_deductions': total_deductions,
        'total_net': total_net,
        'avg_salary': avg_salary,
        'tax_sum': sums['tax'] or 0,
        'nssf_sum': sums['nssf'] or 0,
        'payroll_records_count': p_count
    }

    return {
        'payrolls': qs,
        'dept_stats': dept_stats,
        'summary_stats': summary_stats,
        'period_str': period_str,
        'dept_id': dept_id,
        'departments': departments,
    }


def _get_attendance_summary_roster(request):
    req = request
    from_date_str = req.GET.get('from_date', '').strip()
    to_date_str = req.GET.get('to_date', '').strip()

    today = timezone.now().date()
    default_from = today.replace(day=1)

    from_date = _parse_report_date(from_date_str, default_from)
    to_date = _parse_report_date(to_date_str, today)
    if from_date > to_date:
        from_date, to_date = to_date, from_date

    date_range_display = f"{from_date.strftime('%d-%m-%Y')} to {to_date.strftime('%d-%m-%Y')}"

    branch_id = req.GET.get('branch', '').strip()
    dept_id = req.GET.get('department', '').strip()
    emp_id = req.GET.get('employee', '').strip()
    show_resign = req.GET.get('show_resign') in ('on', 'true', '1')

    emp_qs = Employee.objects.select_related('company', 'branch', 'department', 'position').all()
    if not show_resign:
        emp_qs = emp_qs.filter(status='active')
    if branch_id:
        emp_qs = emp_qs.filter(branch_id=branch_id)
    if dept_id:
        emp_qs = emp_qs.filter(department_id=dept_id)
    if emp_id:
        emp_qs = emp_qs.filter(id=emp_id)

    employees = list(emp_qs.order_by('first_name', 'last_name'))
    emp_ids = [e.id for e in employees]

    total_period_days = (to_date - from_date).days + 1

    att_qs = Attendance.objects.filter(employee_id__in=emp_ids, date__gte=from_date, date__lte=to_date)
    att_by_emp = {}
    for a in att_qs:
        att_by_emp.setdefault(a.employee_id, []).append(a)

    leave_qs = LeaveRequest.objects.filter(
        employee_id__in=emp_ids,
        status='approved',
        periods__start_date__lte=to_date,
        periods__end_date__gte=from_date
    ).distinct()
    leave_by_emp = {}
    for l in leave_qs:
        leave_by_emp[l.employee_id] = float(l.total_days or 0)

    # Query schedules from DB to determine exact work vs non-work (holiday) days
    sched_qs = EmployeeSchedule.objects.filter(employee_id__in=emp_ids)
    sched_by_emp = {}
    for s in sched_qs:
        sched_by_emp.setdefault(s.employee_id, {})[s.day_of_week] = {
            'is_work_day': s.is_work_day,
            'is_half_day': s.is_half_day,
        }

    # Query approved overtime requests in period
    try:
        from overtime.models import OvertimeRequest
        ot_qs = OvertimeRequest.objects.filter(
            employee_id__in=emp_ids,
            status='approved',
            date__gte=from_date,
            date__lte=to_date
        ).values('employee_id').annotate(
            total_hrs=Sum('hours'),
            total_amt=Sum('overtime_amount')
        )
        ot_by_emp = {item['employee_id']: (float(item['total_hrs'] or 0), float(item['total_amt'] or 0)) for item in ot_qs}
    except Exception:
        ot_by_emp = {}

    rows = []
    for idx, emp in enumerate(employees, start=1):
        emp_atts = att_by_emp.get(emp.id, [])
        emp_name = f"{emp.first_name} {emp.last_name}".strip()
        role_name = emp.position.name if emp.position else "Staff"
        dept_name = emp.department.name if emp.department else "---"
        branch_code = emp.branch.code or emp.branch.name if emp.branch else "F2"

        # Calculate exact holidays and scheduled work days:
        # half day count 0.5d, full day count 1d
        emp_sched = sched_by_emp.get(emp.id, {})
        holiday_days = 0.0
        scheduled_work_days = 0.0
        for d in range(total_period_days):
            cur_date = from_date + datetime.timedelta(days=d)
            dow = cur_date.weekday()
            day_cfg = emp_sched.get(dow)
            if day_cfg:
                is_work = day_cfg['is_work_day']
                is_half = day_cfg['is_half_day']
            else:
                is_work = (dow < 5)
                is_half = False

            if is_work:
                if is_half:
                    # half day count 0.5d
                    scheduled_work_days += 0.5
                    holiday_days += 0.5
                else:
                    # full day count 1d
                    scheduled_work_days += 1.0
            else:
                holiday_days += 1.0

        # Query attendance directly from DB records:
        # half day count 0.5d, full day count 1d (or working hours: 2h=0.25d, 4h=0.5d, 6h=0.75d, 8h=1d)
        attend_count = 0.0
        late_count = 0
        early_count = 0
        ot_count = 0
        for a in emp_atts:
            if a.status in ('present', 'late', 'early_leave', 'overtime'):
                a_dow = a.date.weekday()
                day_cfg = emp_sched.get(a_dow)
                is_half = day_cfg['is_half_day'] if day_cfg else False
                if a.working_hours:
                    hrs = a.working_hours.total_seconds() / 3600.0
                    if hrs >= 7.0:
                        day_val = 1.0
                    elif hrs >= 5.0:
                        day_val = 0.75
                    elif hrs >= 3.0:
                        day_val = 0.5
                    elif hrs >= 1.0:
                        day_val = 0.25
                    else:
                        day_val = 0.25
                elif is_half:
                    day_val = 0.5
                else:
                    day_val = 1.0

                attend_count += day_val

            if a.status == 'late':
                late_count += 1
            elif a.status == 'early_leave':
                early_count += 1
            elif a.status == 'overtime':
                ot_count += 1

        # Leave: leave 2h count 0.25d, 4h count 0.5d, 6h count 0.75d, 8h count 1d
        leave_days = leave_by_emp.get(emp.id, 0.0)

        # Absent = scheduled work days minus days attended minus approved leave
        absent_count = max(0.0, scheduled_work_days - attend_count - leave_days)

        rows.append({
            'no': idx,
            'employee': emp,
            'name': emp_name,
            'position': role_name,
            'department': dept_name,
            'branch': branch_code,
            'attend': _fmt_days(attend_count),
            'absent': _fmt_days(absent_count),
            'leave': _fmt_days(leave_days),
            'holiday': _fmt_days(holiday_days),
            'late': late_count,
            'early': early_count,
            'ot': ot_count,
            'overtime_request': f"{ot_by_emp[emp.id][0]:.1f}h" if emp.id in ot_by_emp and ot_by_emp[emp.id][0] > 0 else '',
            'ot_hours': ot_by_emp[emp.id][0] if emp.id in ot_by_emp else 0.0,
            'ot_amount': ot_by_emp[emp.id][1] if emp.id in ot_by_emp else 0.0,
        })

    return {
        'roster_rows': rows,
        'from_date': from_date,
        'to_date': to_date,
        'from_date_str': from_date.strftime("%Y-%m-%d"),
        'to_date_str': to_date.strftime("%Y-%m-%d"),
        'date_range_display': date_range_display,
        'branches': Branch.objects.filter(status=True),
        'departments': Department.objects.filter(status=True),
        'all_employees': Employee.objects.filter(status='active').order_by('first_name'),
        'selected_branch': branch_id,
        'selected_dept': dept_id,
        'selected_employee': emp_id,
        'show_resign': show_resign,
    }


class SummaryReportView(RoleRequiredMixin, TemplateView):
    template_name = 'reports/summary.html'
    required_roles = ['super_admin', 'hr_admin', 'manager']

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        data = _get_summary_data(self.request)
        ctx.update(data)
        roster_data = _get_attendance_summary_roster(self.request)
        ctx.update(roster_data)
        ctx['summary_rows'] = roster_data['roster_rows']
        ctx['leave_requests_count'] = LeaveRequest.objects.count()
        return ctx


class SummaryReportExcelExportView(RoleRequiredMixin, View):
    required_roles = ['super_admin', 'hr_admin', 'manager']

    def get(self, request, *args, **kwargs):
        data = _get_summary_data(request)
        generated_by = request.user.get_full_name() or request.user.username
        excel_bytes = generate_summary_report_excel(
            period_str=data['period_str'],
            payrolls=data['payrolls'],
            dept_stats=data['dept_stats'],
            summary_stats=data['summary_stats'],
            company_name=_get_company_name(),
            generated_by=generated_by
        )
        p_tag = data['period_str'].replace('-', '') if data['period_str'] else 'all'
        filename = f"executive_summary_report_{p_tag}.xlsx"
        resp = HttpResponse(
            excel_bytes,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        resp['Content-Disposition'] = f'attachment; filename="{filename}"'
        return resp


class SummaryReportPdfExportView(RoleRequiredMixin, View):
    required_roles = ['super_admin', 'hr_admin', 'manager']

    def get(self, request, *args, **kwargs):
        data = _get_summary_data(request)
        generated_by = request.user.get_full_name() or request.user.username
        pdf_bytes = generate_summary_report_pdf(
            period_str=data['period_str'],
            payrolls=data['payrolls'],
            dept_stats=data['dept_stats'],
            summary_stats=data['summary_stats'],
            company_name=_get_company_name(),
            generated_by=generated_by
        )
        p_tag = data['period_str'].replace('-', '') if data['period_str'] else 'all'
        filename = f"executive_summary_report_{p_tag}.pdf"
        resp = HttpResponse(pdf_bytes, content_type='application/pdf')
        resp['Content-Disposition'] = f'attachment; filename="{filename}"'
        return resp


# ==============================================================================
# DETAIL REPORT VIEWS
# ==============================================================================

def _get_detail_data(request):
    tab = request.GET.get('tab', 'employees')
    dept_id = request.GET.get('department')
    status = request.GET.get('status')
    q = request.GET.get('q', '').strip()

    emp_qs = Employee.objects.select_related('department', 'position').all().order_by('first_name')
    if dept_id:
        emp_qs = emp_qs.filter(department_id=dept_id)
    if status:
        emp_qs = emp_qs.filter(status=status)
    if q:
        emp_qs = emp_qs.filter(
            Q(first_name__icontains=q) |
            Q(last_name__icontains=q) |
            Q(employee_code__icontains=q) |
            Q(email__icontains=q)
        )

    pay_qs = Payroll.objects.select_related('employee', 'employee__department').all().order_by('-payroll_period')
    if dept_id:
        pay_qs = pay_qs.filter(employee__department_id=dept_id)
    if status:
        pay_qs = pay_qs.filter(status=status)
    if q:
        pay_qs = pay_qs.filter(
            Q(employee__first_name__icontains=q) |
            Q(employee__last_name__icontains=q) |
            Q(employee__employee_code__icontains=q)
        )

    att_qs = Attendance.objects.select_related('employee', 'employee__department').all().order_by('-date')
    if dept_id:
        att_qs = att_qs.filter(employee__department_id=dept_id)
    if status:
        att_qs = att_qs.filter(status=status)
    if q:
        att_qs = att_qs.filter(
            Q(employee__first_name__icontains=q) |
            Q(employee__last_name__icontains=q) |
            Q(employee__employee_code__icontains=q)
        )

    departments = Department.objects.filter(status=True)

    return {
        'tab': tab,
        'employees': emp_qs,
        'payrolls': pay_qs,
        'attendances': att_qs,
        'departments': departments,
        'selected_dept': dept_id or '',
        'selected_status': status or '',
        'search_query': q,
    }


class DetailReportView(RoleRequiredMixin, TemplateView):
    template_name = 'reports/detail.html'
    required_roles = ['super_admin', 'hr_admin', 'manager']

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(_get_detail_data(self.request))
        roster_data = _get_attendance_summary_roster(self.request)
        ctx.update(roster_data)
        ctx['detail_rows'] = roster_data['roster_rows']
        return ctx


class DetailReportExcelExportView(RoleRequiredMixin, View):
    required_roles = ['super_admin', 'hr_admin', 'manager']

    def get(self, request, *args, **kwargs):
        data = _get_detail_data(request)
        generated_by = request.user.get_full_name() or request.user.username
        excel_bytes = generate_detail_report_excel(
            employees=data['employees'],
            payrolls=data['payrolls'],
            attendances=data['attendances'],
            company_name=_get_company_name(),
            generated_by=generated_by
        )
        now_tag = timezone.now().strftime("%Y%m%d")
        filename = f"detail_master_ledger_{now_tag}.xlsx"
        resp = HttpResponse(
            excel_bytes,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        resp['Content-Disposition'] = f'attachment; filename="{filename}"'
        return resp


class DetailReportPdfExportView(RoleRequiredMixin, View):
    required_roles = ['super_admin', 'hr_admin', 'manager']

    def get(self, request, *args, **kwargs):
        data = _get_detail_data(request)
        tab = data['tab']
        if tab == 'payroll':
            items = data['payrolls']
        elif tab == 'attendance':
            items = data['attendances']
        else:
            tab = 'employees'
            items = data['employees']

        generated_by = request.user.get_full_name() or request.user.username
        pdf_bytes = generate_detail_report_pdf(
            category=tab,
            data_list=items,
            company_name=_get_company_name(),
            generated_by=generated_by
        )
        now_tag = timezone.now().strftime("%Y%m%d")
        filename = f"detail_{tab}_ledger_{now_tag}.pdf"
        resp = HttpResponse(pdf_bytes, content_type='application/pdf')
        resp['Content-Disposition'] = f'attachment; filename="{filename}"'
        return resp
