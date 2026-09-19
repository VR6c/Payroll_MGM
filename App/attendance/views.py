import csv
import json
import datetime
from django.urls import reverse_lazy
from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.db.models import Q
from django.views.generic import View, ListView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from accounts.mixins import RoleRequiredMixin
from companies.models import Company, Department, Position
from employees.models import Employee
from activities.services import log_activity
from .models import Attendance, WorkSchedule, EmployeeSchedule, LunchBreak
from .services import AttendanceService, ScheduleService
from .forms import AttendanceForm, LunchBreakForm
from reports.exporters import generate_attendance_list_excel, generate_detail_report_pdf


class CheckInView(LoginRequiredMixin, View):
    def post(self, request):
        try:
            employee = getattr(request.user, 'employee_profile', None)
            if not employee:
                messages.error(request, "Only registered employees can check in.")
                return redirect('dashboard:home')
            AttendanceService.check_in(employee, request.user)
            messages.success(request, "Checked in successfully!")
        except ValueError as e:
            messages.error(request, str(e))
        except Exception as e:
            messages.error(request, f"An error occurred while checking in: {e}")
        return redirect('dashboard:home')


class CheckOutView(LoginRequiredMixin, View):
    def post(self, request):
        try:
            employee = getattr(request.user, 'employee_profile', None)
            if not employee:
                messages.error(request, "Only registered employees can check out.")
                return redirect('dashboard:home')
            AttendanceService.check_out(employee, request.user)
            messages.success(request, "Checked out successfully!")
        except ValueError as e:
            messages.error(request, str(e))
        except Exception as e:
            messages.error(request, f"An error occurred while checking out: {e}")
        return redirect('dashboard:home')


class MyAttendanceView(LoginRequiredMixin, ListView):
    template_name = 'attendance/my_attendance.html'
    context_object_name = 'attendances'
    paginate_by = 30

    def get_queryset(self):
        employee = getattr(self.request.user, 'employee_profile', None)
        if not employee:
            return Attendance.objects.none()
        return Attendance.objects.filter(
            employee=employee
        ).select_related('employee', 'employee__department', 'employee__position').order_by('-date')


class WorkScheduleListView(RoleRequiredMixin, ListView):
    model = Employee
    template_name = 'attendance/schedules.html'
    context_object_name = 'employees'
    required_roles = ['super_admin', 'hr_admin', 'manager']

    def get_paginate_by(self, queryset):
        limit = self.request.GET.get('limit', '10')
        if limit == 'all':
            return 10000
        try:
            return int(limit)
        except ValueError:
            return 10

    def get_queryset(self):
        qs = Employee.objects.filter(status='active').select_related('department', 'position', 'company')
        
        dept_id = self.request.GET.get('department')
        pos_id = self.request.GET.get('position')
        search_q = self.request.GET.get('search')
        group_by = self.request.GET.get('group_by')

        if dept_id:
            qs = qs.filter(department_id=dept_id)
        if pos_id:
            qs = qs.filter(position_id=pos_id)
        if search_q:
            qs = qs.filter(
                Q(first_name__icontains=search_q) |
                Q(last_name__icontains=search_q) |
                Q(employee_code__icontains=search_q) |
                Q(email__icontains=search_q)
            )

        if group_by == 'department':
            qs = qs.order_by('department__name', 'first_name', 'last_name')
        else:
            qs = qs.order_by('first_name', 'last_name')

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        page_emps = list(ctx['employees'])
        EmployeeSchedule.get_weekly_matrices_for_employees(page_emps)
        ctx['employees'] = page_emps

        group_by = self.request.GET.get('group_by', '')
        if group_by:
            groups = {}
            for emp in page_emps:
                if group_by == 'department':
                    g_key = emp.department.name if emp.department else 'No Department'
                else:
                    g_key = 'All Employees'
                if g_key not in groups:
                    groups[g_key] = []
                groups[g_key].append(emp)
            ctx['grouped_employees'] = groups

        
        ctx['departments'] = Department.objects.filter(status=True)
        ctx['positions'] = Position.objects.filter(status=True)
        dept_val = self.request.GET.get('department', '')
        pos_val = self.request.GET.get('position', '')
        ctx['active_department'] = int(dept_val) if dept_val and dept_val.isdigit() else ''
        ctx['active_position'] = int(pos_val) if pos_val and pos_val.isdigit() else ''
        ctx['active_limit'] = self.request.GET.get('limit', '10')
        ctx['active_search'] = self.request.GET.get('search', '')
        ctx['active_group_by'] = group_by
        ctx['all_employees'] = Employee.objects.filter(status='active').select_related('department', 'position')
        ctx['days_list'] = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        return ctx


class SaveEmployeeScheduleView(RoleRequiredMixin, View):
    required_roles = ['super_admin', 'hr_admin', 'manager']

    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
        except Exception:
            data = request.POST

        try:
            count = ScheduleService.save_employee_schedule(data)
            return JsonResponse({'success': True, 'message': f'Schedules updated successfully for {count} employee(s)!'})
        except ValueError as ve:
            return JsonResponse({'success': False, 'message': str(ve)}, status=400)
        except Exception as e:
            return JsonResponse({'success': False, 'message': f'Failed to update schedules: {e}'}, status=500)


class GetEmployeeScheduleView(RoleRequiredMixin, View):
    required_roles = ['super_admin', 'hr_admin', 'manager']

    def get(self, request, emp_id, *args, **kwargs):
        emp = get_object_or_404(Employee, pk=emp_id)
        data = ScheduleService.get_employee_schedule_data(emp)
        data['success'] = True
        return JsonResponse(data)


class ExportScheduleView(RoleRequiredMixin, View):
    required_roles = ['super_admin', 'hr_admin', 'manager']

    def get(self, request, *args, **kwargs):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="workday_shift_schedules.csv"'

        writer = csv.writer(response)
        writer.writerow(['#', 'Employee Code', 'Employee Name', 'Gender', 'Department', 'Position', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'])

        employees = Employee.objects.filter(status='active').select_related('department', 'position').order_by('first_name')
        emp_ids = [e.pk for e in employees]
        sched_map = {}
        for s in EmployeeSchedule.objects.filter(employee_id__in=emp_ids):
            if s.employee_id not in sched_map:
                sched_map[s.employee_id] = {}
            sched_map[s.employee_id][s.day_of_week] = s

        for idx, emp in enumerate(employees, start=1):
            row = [
                idx,
                emp.employee_code,
                f"{emp.first_name} {emp.last_name}".strip(),
                emp.get_gender_display(),
                emp.department.name if emp.department else '-',
                emp.position.name if emp.position else '-',
            ]
            e_map = sched_map.get(emp.pk, {})
            for d in range(7):
                s_obj = e_map.get(d)
                if s_obj and s_obj.is_work_day:
                    st = s_obj.start_time.strftime('%I:%M %p') if s_obj.start_time else '08:00 AM'
                    et = s_obj.end_time.strftime('%I:%M %p') if s_obj.end_time else '05:00 PM'
                    row.append(f"{st} - {et} ({s_obj.shift_label})")
                else:
                    row.append("Off")
            writer.writerow(row)

        return response


class AttendanceCreateView(RoleRequiredMixin, View):
    required_roles = ['super_admin', 'hr_admin', 'manager']

    def post(self, request, *args, **kwargs):
        # 1. Retrieve employees: can be 'employees' list or 'employee' single
        employee_ids = request.POST.getlist('employees')
        if not employee_ids:
            single_emp = request.POST.get('employee')
            if single_emp:
                employee_ids = [single_emp]
            elif request.POST.get('all_employees') == '1':
                employee_ids = list(Employee.objects.filter(status='active').values_list('id', flat=True))

        if not employee_ids:
            messages.error(request, "Please select at least one employee.")
            return redirect('attendance:report')

        # 2. Determine target dates
        date_mode = request.POST.get('date_mode', 'single')
        target_dates = []

        if date_mode == 'range':
            start_date_str = request.POST.get('start_date')
            end_date_str = request.POST.get('end_date')
            if not start_date_str or not end_date_str:
                messages.error(request, "Please specify both start date and end date.")
                return redirect('attendance:report')
            try:
                start_date = datetime.datetime.strptime(start_date_str, '%Y-%m-%d').date()
                end_date = datetime.datetime.strptime(end_date_str, '%Y-%m-%d').date()
            except ValueError:
                messages.error(request, "Invalid date format. Please use YYYY-MM-DD.")
                return redirect('attendance:report')

            if start_date > end_date:
                messages.error(request, "Start date cannot be after end date.")
                return redirect('attendance:report')

            selected_weekdays = request.POST.getlist('weekdays')
            if selected_weekdays:
                allowed_weekdays = {int(w) for w in selected_weekdays if str(w).isdigit()}
            else:
                if request.POST.get('exclude_weekends') == '1':
                    allowed_weekdays = {0, 1, 2, 3, 4}
                else:
                    allowed_weekdays = set(range(7))

            cur = start_date
            while cur <= end_date:
                if cur.weekday() in allowed_weekdays:
                    target_dates.append(cur)
                cur += datetime.timedelta(days=1)
        else:
            date_str = request.POST.get('date')
            if not date_str:
                date_str = timezone.localdate().strftime('%Y-%m-%d')
            try:
                target_dates.append(datetime.datetime.strptime(date_str, '%Y-%m-%d').date())
            except ValueError:
                messages.error(request, "Invalid date format.")
                return redirect('attendance:report')

        if not target_dates:
            messages.error(request, "No matching dates found for the specified range and weekday filter.")
            return redirect('attendance:report')

        # 3. Status and Times
        status = request.POST.get('status', 'present')
        check_in_str = request.POST.get('check_in_time') or request.POST.get('check_in')
        check_out_str = request.POST.get('check_out_time') or request.POST.get('check_out')
        overwrite = request.POST.get('overwrite', 'true').lower() in ('true', '1', 'on', 'yes')

        def parse_time_component(val_str):
            if not val_str:
                return None
            val_str = str(val_str).strip()
            if 'T' in val_str:
                val_str = val_str.split('T')[-1]
            for fmt in ('%H:%M:%S', '%H:%M'):
                try:
                    return datetime.datetime.strptime(val_str, fmt).time()
                except ValueError:
                    pass
            return None

        ci_time = parse_time_component(check_in_str)
        co_time = parse_time_component(check_out_str)

        employees = Employee.objects.filter(id__in=employee_ids)
        created_count = 0
        updated_count = 0
        skipped_count = 0

        current_tz = timezone.get_current_timezone()

        for emp in employees:
            for d in target_dates:
                ci_dt = None
                co_dt = None
                wh = None

                if status != 'absent':
                    if ci_time:
                        naive_ci = datetime.datetime.combine(d, ci_time)
                        ci_dt = timezone.make_aware(naive_ci, current_tz)
                    if co_time:
                        end_d = d + datetime.timedelta(days=1) if (ci_time and co_time < ci_time) else d
                        naive_co = datetime.datetime.combine(end_d, co_time)
                        co_dt = timezone.make_aware(naive_co, current_tz)
                    if ci_dt and co_dt:
                        wh = Attendance.calculate_net_working_hours(ci_dt, co_dt, employee=emp, date=d)

                record_status = status
                if record_status == 'early_leave':
                    record_status = Attendance.Status.CHECKOUT_EARLY
                elif record_status in ('present', '', None) and (ci_dt or co_dt):
                    record_status = AttendanceService.determine_status(emp, d, ci_dt, co_dt, user_status=status)

                existing = Attendance.objects.filter(employee=emp, date=d).first()
                if existing:
                    if overwrite:
                        existing.status = record_status
                        existing.check_in = ci_dt
                        existing.check_out = co_dt
                        existing.working_hours = wh
                        existing.save()
                        updated_count += 1
                    else:
                        skipped_count += 1
                else:
                    Attendance.objects.create(
                        employee=emp,
                        date=d,
                        status=record_status,
                        check_in=ci_dt,
                        check_out=co_dt,
                        working_hours=wh
                    )
                    created_count += 1

        total_emp = len(employees)
        total_d = len(target_dates)

        msg_parts = []
        if created_count > 0:
            msg_parts.append(f"{created_count} created")
        if updated_count > 0:
            msg_parts.append(f"{updated_count} updated")
        if skipped_count > 0:
            msg_parts.append(f"{skipped_count} skipped")

        summary_text = ", ".join(msg_parts) or "0 records processed"
        messages.success(
            request,
            f"Attendance successfully recorded: {summary_text} across {total_emp} employee{'s' if total_emp != 1 else ''} and {total_d} date{'s' if total_d != 1 else ''}."
        )

        try:
            log_activity(
                request.user,
                None,
                'ATTENDANCE',
                'CREATE_BULK',
                f"Recorded attendance: {created_count} created, {updated_count} updated across {total_emp} employees."
            )
        except Exception:
            pass

        return redirect('attendance:report')


class AttendanceUpdateView(RoleRequiredMixin, UpdateView):
    model = Attendance
    form_class = AttendanceForm
    success_url = reverse_lazy('attendance:report')
    required_roles = ['super_admin', 'hr_admin', 'manager']

    def form_valid(self, form):
        att = form.save(commit=False)
        if att.check_in and att.check_out:
            att.calculate_working_hours()
        else:
            att.working_hours = None
        if att.status == 'early_leave':
            att.status = Attendance.Status.CHECKOUT_EARLY
        elif att.status == 'present' and att.check_out:
            att.status = AttendanceService.determine_status(
                att.employee, att.date, att.check_in, att.check_out, user_status='present'
            )
        att.save()
        messages.success(self.request, "Attendance record updated successfully!")
        return redirect('attendance:report')

    def form_invalid(self, form):
        for field, errs in form.errors.items():
            for err in errs:
                messages.error(self.request, f"{field.replace('_', ' ').title()}: {err}")
        return redirect('attendance:report')


class AttendanceDeleteView(RoleRequiredMixin, DeleteView):
    model = Attendance
    success_url = reverse_lazy('attendance:report')
    required_roles = ['super_admin', 'hr_admin', 'manager']

    def post(self, request, *args, **kwargs):
        messages.success(self.request, "Attendance record deleted successfully!")
        return super().post(request, *args, **kwargs)


class LunchBreakListView(RoleRequiredMixin, ListView):
    model = LunchBreak
    template_name = 'attendance/lunch_breaks.html'
    context_object_name = 'breaks'
    paginate_by = 20
    required_roles = ['super_admin', 'hr_admin', 'manager']

    def get_queryset(self):
        qs = LunchBreak.objects.select_related('company').all()
        q = self.request.GET.get('search')
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(break_type__icontains=q))
        comp = self.request.GET.get('company')
        if comp:
            qs = qs.filter(company_id=comp)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        all_breaks = LunchBreak.objects.all()
        ctx['total_breaks'] = all_breaks.count()
        ctx['active_breaks'] = all_breaks.filter(status=True).count()
        ctx['auto_deduct_breaks'] = all_breaks.filter(status=True, auto_deduct=True).count()
        ctx['companies'] = Company.objects.filter(status=True)
        ctx['form'] = LunchBreakForm()
        ctx['active_search'] = self.request.GET.get('search', '')
        ctx['active_company'] = self.request.GET.get('company', '')
        return ctx


class LunchBreakCreateView(RoleRequiredMixin, CreateView):
    model = LunchBreak
    form_class = LunchBreakForm
    success_url = reverse_lazy('attendance:lunch_breaks')
    required_roles = ['super_admin', 'hr_admin']

    def form_valid(self, form):
        messages.success(self.request, f"Lunch break '{form.cleaned_data.get('name')}' created successfully!")
        return super().form_valid(form)

    def form_invalid(self, form):
        for field, errs in form.errors.items():
            for err in errs:
                messages.error(self.request, f"{field.replace('_', ' ').title()}: {err}")
        return redirect('attendance:lunch_breaks')


class LunchBreakUpdateView(RoleRequiredMixin, UpdateView):
    model = LunchBreak
    form_class = LunchBreakForm
    success_url = reverse_lazy('attendance:lunch_breaks')
    required_roles = ['super_admin', 'hr_admin']

    def form_valid(self, form):
        messages.success(self.request, f"Lunch break '{form.cleaned_data.get('name')}' updated successfully!")
        return super().form_valid(form)

    def form_invalid(self, form):
        for field, errs in form.errors.items():
            for err in errs:
                messages.error(self.request, f"{field.replace('_', ' ').title()}: {err}")
        return redirect('attendance:lunch_breaks')


class LunchBreakDeleteView(RoleRequiredMixin, DeleteView):
    model = LunchBreak
    success_url = reverse_lazy('attendance:lunch_breaks')
    required_roles = ['super_admin', 'hr_admin']

    def post(self, request, *args, **kwargs):
        obj = self.get_object()
        name = obj.name
        messages.success(self.request, f"Lunch break '{name}' deleted successfully!")
        return super().post(request, *args, **kwargs)


class AttendanceReportView(RoleRequiredMixin, ListView):
    model = Attendance
    template_name = 'attendance/report.html'
    context_object_name = 'attendances'
    paginate_by = 50
    required_roles = ['super_admin', 'hr_admin', 'manager']

    def get_queryset(self):
        qs = Attendance.objects.select_related('employee', 'employee__department', 'employee__position').all().order_by('-date')
        filter_type = self.request.GET.get('type')
        status = self.request.GET.get('status')
        from_date = self.request.GET.get('from_date')
        to_date = self.request.GET.get('to_date')
        date_str = self.request.GET.get('date')

        if filter_type == 'checkin_early':
            qs = qs.filter(
                Q(status='present') | Q(check_in__time__lte=datetime.time(8, 0), check_in__isnull=False)
            ).exclude(status__in=['late', 'checkout_early'])
        elif filter_type == 'checkin_late':
            qs = qs.filter(
                Q(status='late') | Q(check_in__time__gt=datetime.time(8, 0), check_in__isnull=False)
            )
        elif filter_type == 'checkout_early':
            qs = qs.filter(
                Q(status='checkout_early') |
                Q(check_out__time__lt=datetime.time(17, 0), check_out__isnull=False)
            )
        elif filter_type == 'checkout_late':
            qs = qs.filter(
                Q(status='overtime') |
                Q(check_out__time__gt=datetime.time(17, 0), check_out__isnull=False)
            )
        elif status:
            qs = qs.filter(status=status)

        if from_date:
            qs = qs.filter(date__gte=from_date)
        if to_date:
            qs = qs.filter(date__lte=to_date)
        if date_str and not from_date and not to_date:
            qs = qs.filter(date=date_str)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['active_type'] = self.request.GET.get('type', '')
        ctx['employees'] = Employee.objects.filter(status='active').select_related('department', 'position').order_by('department__name', 'first_name')
        ctx['departments'] = Department.objects.all().order_by('name')
        ctx['form'] = AttendanceForm()
        return ctx


class AttendanceReportExcelExportView(RoleRequiredMixin, View):
    required_roles = ['super_admin', 'hr_admin', 'manager']

    def get(self, request, *args, **kwargs):
        qs = Attendance.objects.select_related('employee', 'employee__department', 'employee__position').all().order_by('-date')
        filter_type = request.GET.get('type')
        status = request.GET.get('status')
        from_date = request.GET.get('from_date')
        to_date = request.GET.get('to_date')
        date_str = request.GET.get('date')

        if filter_type == 'checkin_early':
            qs = qs.filter(
                Q(status='present') | Q(check_in__time__lte=datetime.time(8, 0), check_in__isnull=False)
            ).exclude(status__in=['late', 'checkout_early'])
        elif filter_type == 'checkin_late':
            qs = qs.filter(
                Q(status='late') | Q(check_in__time__gt=datetime.time(8, 0), check_in__isnull=False)
            )
        elif filter_type == 'checkout_early':
            qs = qs.filter(
                Q(status='checkout_early') |
                Q(check_out__time__lt=datetime.time(17, 0), check_out__isnull=False)
            )
        elif filter_type == 'checkout_late':
            qs = qs.filter(
                Q(status='overtime') |
                Q(check_out__time__gt=datetime.time(17, 0), check_out__isnull=False)
            )
        elif status:
            qs = qs.filter(status=status)

        if from_date:
            qs = qs.filter(date__gte=from_date)
        if to_date:
            qs = qs.filter(date__lte=to_date)
        if date_str and not from_date and not to_date:
            qs = qs.filter(date=date_str)

        generated_by = request.user.get_full_name() or request.user.username
        excel_bytes = generate_attendance_list_excel(qs, generated_by=generated_by)
        filename = f"attendance_records_{datetime.date.today().strftime('%Y%m%d')}.xlsx"
        resp = HttpResponse(
            excel_bytes,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        resp['Content-Disposition'] = f'attachment; filename="{filename}"'
        return resp


class AttendanceReportPdfExportView(RoleRequiredMixin, View):
    required_roles = ['super_admin', 'hr_admin', 'manager']

    def get(self, request, *args, **kwargs):
        qs = Attendance.objects.select_related('employee', 'employee__department', 'employee__position').all().order_by('-date')
        filter_type = request.GET.get('type')
        status = request.GET.get('status')
        from_date = request.GET.get('from_date')
        to_date = request.GET.get('to_date')
        date_str = request.GET.get('date')

        if filter_type == 'checkin_early':
            qs = qs.filter(
                Q(status='present') | Q(check_in__time__lte=datetime.time(8, 0), check_in__isnull=False)
            ).exclude(status__in=['late', 'checkout_early'])
        elif filter_type == 'checkin_late':
            qs = qs.filter(
                Q(status='late') | Q(check_in__time__gt=datetime.time(8, 0), check_in__isnull=False)
            )
        elif filter_type == 'checkout_early':
            qs = qs.filter(
                Q(status='checkout_early') |
                Q(check_out__time__lt=datetime.time(17, 0), check_out__isnull=False)
            )
        elif filter_type == 'checkout_late':
            qs = qs.filter(
                Q(status='overtime') |
                Q(check_out__time__gt=datetime.time(17, 0), check_out__isnull=False)
            )
        elif status:
            qs = qs.filter(status=status)

        if from_date:
            qs = qs.filter(date__gte=from_date)
        if to_date:
            qs = qs.filter(date__lte=to_date)
        if date_str and not from_date and not to_date:
            qs = qs.filter(date=date_str)

        generated_by = request.user.get_full_name() or request.user.username
        pdf_bytes = generate_detail_report_pdf('attendance', qs, generated_by=generated_by)
        filename = f"attendance_records_{datetime.date.today().strftime('%Y%m%d')}.pdf"
        resp = HttpResponse(pdf_bytes, content_type='application/pdf')
        resp['Content-Disposition'] = f'attachment; filename="{filename}"'
        return resp
