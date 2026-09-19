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
from accounts.mixins import RoleRequiredMixin
from companies.models import Department, Position
from employees.models import Employee
from .models import Attendance, WorkSchedule, EmployeeSchedule
from .services import AttendanceService, ScheduleService
from .forms import AttendanceForm
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


class AttendanceCreateView(RoleRequiredMixin, CreateView):
    model = Attendance
    form_class = AttendanceForm
    success_url = reverse_lazy('attendance:report')
    required_roles = ['super_admin', 'hr_admin', 'manager']

    def form_valid(self, form):
        att = form.save(commit=False)
        att.save()
        att.calculate_working_hours()
        messages.success(self.request, "Attendance record created successfully!")
        return redirect('attendance:report')


class AttendanceUpdateView(RoleRequiredMixin, UpdateView):
    model = Attendance
    form_class = AttendanceForm
    success_url = reverse_lazy('attendance:report')
    required_roles = ['super_admin', 'hr_admin', 'manager']

    def form_valid(self, form):
        att = form.save(commit=False)
        att.save()
        att.calculate_working_hours()
        messages.success(self.request, "Attendance record updated successfully!")
        return redirect('attendance:report')


class AttendanceDeleteView(RoleRequiredMixin, DeleteView):
    model = Attendance
    success_url = reverse_lazy('attendance:report')
    required_roles = ['super_admin', 'hr_admin', 'manager']

    def post(self, request, *args, **kwargs):
        messages.success(self.request, "Attendance record deleted successfully!")
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
        date_str = self.request.GET.get('date')

        if filter_type == 'checkin_early':
            qs = qs.filter(status='present')
        elif filter_type == 'checkin_late':
            qs = qs.filter(status='late')
        elif filter_type == 'checkout_early':
            qs = qs.filter(status='early_leave')
        elif filter_type == 'checkout_late':
            qs = qs.filter(status='overtime')
        elif status:
            qs = qs.filter(status=status)

        if date_str:
            qs = qs.filter(date=date_str)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['active_type'] = self.request.GET.get('type', '')
        ctx['employees'] = Employee.objects.filter(status='active').select_related('department', 'position')
        ctx['form'] = AttendanceForm()
        return ctx


class AttendanceReportExcelExportView(RoleRequiredMixin, View):
    required_roles = ['super_admin', 'hr_admin', 'manager']

    def get(self, request, *args, **kwargs):
        qs = Attendance.objects.select_related('employee', 'employee__department', 'employee__position').all().order_by('-date')
        filter_type = request.GET.get('type')
        status = request.GET.get('status')
        date_str = request.GET.get('date')

        if filter_type == 'checkin_early':
            qs = qs.filter(status='present')
        elif filter_type == 'checkin_late':
            qs = qs.filter(status='late')
        elif filter_type == 'checkout_early':
            qs = qs.filter(status='early_leave')
        elif filter_type == 'checkout_late':
            qs = qs.filter(status='overtime')
        elif status:
            qs = qs.filter(status=status)

        if date_str:
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
        date_str = request.GET.get('date')

        if filter_type == 'checkin_early':
            qs = qs.filter(status='present')
        elif filter_type == 'checkin_late':
            qs = qs.filter(status='late')
        elif filter_type == 'checkout_early':
            qs = qs.filter(status='early_leave')
        elif filter_type == 'checkout_late':
            qs = qs.filter(status='overtime')
        elif status:
            qs = qs.filter(status=status)

        if date_str:
            qs = qs.filter(date=date_str)

        generated_by = request.user.get_full_name() or request.user.username
        pdf_bytes = generate_detail_report_pdf('attendance', qs, generated_by=generated_by)
        filename = f"attendance_records_{datetime.date.today().strftime('%Y%m%d')}.pdf"
        resp = HttpResponse(pdf_bytes, content_type='application/pdf')
        resp['Content-Disposition'] = f'attachment; filename="{filename}"'
        return resp
