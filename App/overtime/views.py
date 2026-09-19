from decimal import Decimal
from django.shortcuts import redirect, get_object_or_404, render
from django.http import HttpResponse
from django.urls import reverse_lazy
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum, Count, Q
from django.views.generic import View, ListView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from accounts.mixins import RoleRequiredMixin
from companies.models import Company, Department
from companies.services import get_default_company
from employees.models import Employee
from activities.services import log_activity

from .models import OvertimeType, OvertimeRequest
from .forms import OvertimeTypeForm, AdminOvertimeRequestForm, EmployeeOvertimeRequestForm
from .services import OvertimeService
from .exporters import generate_overtime_report_excel, generate_overtime_report_pdf


# ==========================================
# Overtime Records (Admin Full CRUD)
# ==========================================

class OvertimeListView(RoleRequiredMixin, ListView):
    model = OvertimeRequest
    template_name = 'overtime/list.html'
    context_object_name = 'overtimes'
    paginate_by = 25
    required_roles = ['super_admin', 'hr_admin', 'manager']

    def get_queryset(self):
        qs = OvertimeRequest.objects.select_related(
            'employee', 'employee__department', 'employee__position', 'overtime_type', 'approved_by'
        ).all()

        search = self.request.GET.get('search')
        if search:
            qs = qs.filter(
                Q(employee__first_name__icontains=search) |
                Q(employee__last_name__icontains=search) |
                Q(employee__employee_code__icontains=search)
            )

        emp_id = self.request.GET.get('employee')
        if emp_id:
            qs = qs.filter(employee_id=emp_id)

        dept_id = self.request.GET.get('department')
        if dept_id:
            qs = qs.filter(employee__department_id=dept_id)

        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)

        type_id = self.request.GET.get('overtime_type')
        if type_id:
            qs = qs.filter(overtime_type_id=type_id)

        from_date = self.request.GET.get('from_date')
        if from_date:
            qs = qs.filter(date__gte=from_date)

        to_date = self.request.GET.get('to_date')
        if to_date:
            qs = qs.filter(date__lte=to_date)

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        filtered_qs = self.get_queryset()

        stats = filtered_qs.aggregate(
            total_hours=Sum('hours'),
            total_amount=Sum('overtime_amount'),
            pending_count=Count('id', filter=Q(status=OvertimeRequest.Status.PENDING)),
            approved_count=Count('id', filter=Q(status=OvertimeRequest.Status.APPROVED)),
        )

        ctx['total_hours'] = stats['total_hours'] or Decimal('0.00')
        ctx['total_amount'] = stats['total_amount'] or Decimal('0.00')
        ctx['pending_count'] = stats['pending_count'] or 0
        ctx['approved_count'] = stats['approved_count'] or 0

        ctx['departments'] = Department.objects.filter(status=True)
        ctx['employees'] = Employee.objects.filter(status='active').select_related('department', 'position')
        ctx['overtime_types'] = OvertimeType.objects.filter(status=True)
        ctx['form'] = AdminOvertimeRequestForm()

        # Preserve query parameters
        params = self.request.GET.copy()
        if 'page' in params:
            params.pop('page')
        ctx['query_params'] = params.urlencode()

        return ctx


class OvertimeCreateView(RoleRequiredMixin, CreateView):
    model = OvertimeRequest
    form_class = AdminOvertimeRequestForm
    success_url = reverse_lazy('overtime:list')
    required_roles = ['super_admin', 'hr_admin']

    def form_valid(self, form):
        ot = form.save(commit=False)
        if ot.status == OvertimeRequest.Status.APPROVED and not ot.approved_by:
            ot.approved_by = self.request.user
            ot.approved_at = timezone.now()

        ot.save()
        log_activity(
            user=self.request.user,
            employee=ot.employee,
            module='OVERTIME',
            action='CREATE',
            description=f"Created {ot.hours}h overtime record for {ot.employee} on {ot.date}"
        )
        messages.success(self.request, f"Overtime record for {ot.employee} created successfully!")
        return redirect(self.success_url)

    def form_invalid(self, form):
        messages.error(self.request, f"Failed to create overtime record: {form.errors}")
        return redirect('overtime:list')


class OvertimeUpdateView(RoleRequiredMixin, UpdateView):
    model = OvertimeRequest
    form_class = AdminOvertimeRequestForm
    success_url = reverse_lazy('overtime:list')
    required_roles = ['super_admin', 'hr_admin']

    def form_valid(self, form):
        ot = form.save(commit=False)
        if ot.status == OvertimeRequest.Status.APPROVED and not ot.approved_by:
            ot.approved_by = self.request.user
            ot.approved_at = timezone.now()

        ot.save()
        log_activity(
            user=self.request.user,
            employee=ot.employee,
            module='OVERTIME',
            action='UPDATE',
            description=f"Updated overtime record ID #{ot.pk} for {ot.employee}"
        )
        messages.success(self.request, f"Overtime record updated successfully!")
        return redirect(self.success_url)

    def form_invalid(self, form):
        messages.error(self.request, f"Failed to update overtime record: {form.errors}")
        return redirect('overtime:list')


class OvertimeDeleteView(RoleRequiredMixin, DeleteView):
    model = OvertimeRequest
    success_url = reverse_lazy('overtime:list')
    required_roles = ['super_admin', 'hr_admin']

    def post(self, request, *args, **kwargs):
        obj = self.get_object()
        emp = obj.employee
        pk_val = obj.pk
        obj.delete()
        log_activity(
            user=request.user,
            employee=emp,
            module='OVERTIME',
            action='DELETE',
            description=f"Deleted overtime record #{pk_val} for {emp}"
        )
        messages.success(request, "Overtime record deleted successfully!")
        return redirect(self.success_url)


class OvertimeApproveView(RoleRequiredMixin, View):
    required_roles = ['super_admin', 'hr_admin', 'manager']

    def post(self, request, pk, *args, **kwargs):
        ot = get_object_or_404(OvertimeRequest, pk=pk)
        OvertimeService.approve_request(ot, request.user)
        messages.success(request, f"Overtime request for {ot.employee} approved successfully.")
        return redirect(request.META.get('HTTP_REFERER', 'overtime:list'))


class OvertimeRejectView(RoleRequiredMixin, View):
    required_roles = ['super_admin', 'hr_admin', 'manager']

    def post(self, request, pk, *args, **kwargs):
        ot = get_object_or_404(OvertimeRequest, pk=pk)
        reason = request.POST.get('rejection_reason', '')
        OvertimeService.reject_request(ot, request.user, reason)
        messages.info(request, f"Overtime request for {ot.employee} rejected.")
        return redirect(request.META.get('HTTP_REFERER', 'overtime:list'))


# ==========================================
# Overtime Types (Admin Full CRUD)
# ==========================================

class OvertimeTypeListView(RoleRequiredMixin, ListView):
    model = OvertimeType
    template_name = 'overtime/types.html'
    context_object_name = 'overtime_types'
    paginate_by = 20
    required_roles = ['super_admin', 'hr_admin', 'manager']

    def get_queryset(self):
        return OvertimeType.objects.select_related('company').all()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        get_default_company()
        ctx['companies'] = Company.objects.all()
        ctx['form'] = OvertimeTypeForm()
        return ctx


class OvertimeTypeCreateView(RoleRequiredMixin, CreateView):
    model = OvertimeType
    form_class = OvertimeTypeForm
    success_url = reverse_lazy('overtime:types')
    required_roles = ['super_admin', 'hr_admin']

    def form_valid(self, form):
        if not form.cleaned_data.get('company'):
            form.instance.company = get_default_company()
        messages.success(self.request, "Overtime type created successfully!")
        return super().form_valid(form)


class OvertimeTypeUpdateView(RoleRequiredMixin, UpdateView):
    model = OvertimeType
    form_class = OvertimeTypeForm
    success_url = reverse_lazy('overtime:types')
    required_roles = ['super_admin', 'hr_admin']

    def form_valid(self, form):
        if not form.cleaned_data.get('company'):
            form.instance.company = get_default_company()
        messages.success(self.request, "Overtime type updated successfully!")
        return super().form_valid(form)


class OvertimeTypeDeleteView(RoleRequiredMixin, DeleteView):
    model = OvertimeType
    success_url = reverse_lazy('overtime:types')
    required_roles = ['super_admin', 'hr_admin']

    def post(self, request, *args, **kwargs):
        messages.success(self.request, "Overtime type deleted successfully!")
        return super().post(request, *args, **kwargs)


# ==========================================
# Employee Self-Service Views
# ==========================================

class MyOvertimeListView(LoginRequiredMixin, ListView):
    template_name = 'overtime/my_overtime.html'
    context_object_name = 'overtimes'
    paginate_by = 20

    def get_queryset(self):
        employee = getattr(self.request.user, 'employee_profile', None)
        if not employee:
            return OvertimeRequest.objects.none()
        return OvertimeRequest.objects.filter(
            employee=employee
        ).select_related('overtime_type', 'approved_by').order_by('-date', '-created_at')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['form'] = EmployeeOvertimeRequestForm()
        employee = getattr(self.request.user, 'employee_profile', None)
        if employee:
            totals = OvertimeRequest.objects.filter(employee=employee).aggregate(
                total_hours=Sum('hours', filter=Q(status=OvertimeRequest.Status.APPROVED)),
                total_amount=Sum('overtime_amount', filter=Q(status=OvertimeRequest.Status.APPROVED)),
                pending_count=Count('id', filter=Q(status=OvertimeRequest.Status.PENDING)),
            )
            ctx['my_total_hours'] = totals['total_hours'] or Decimal('0.00')
            ctx['my_total_amount'] = totals['total_amount'] or Decimal('0.00')
            ctx['my_pending_count'] = totals['pending_count'] or 0
        return ctx


class MyOvertimeCreateView(LoginRequiredMixin, CreateView):
    form_class = EmployeeOvertimeRequestForm
    template_name = 'overtime/my_overtime.html'
    success_url = reverse_lazy('overtime:my_overtime')

    def form_valid(self, form):
        employee = getattr(self.request.user, 'employee_profile', None)
        if not employee:
            messages.error(self.request, "Only registered employees can submit overtime requests.")
            return redirect('overtime:my_overtime')

        ot = form.save(commit=False)
        ot.employee = employee
        ot.status = OvertimeRequest.Status.PENDING
        ot.save()

        log_activity(
            user=self.request.user,
            employee=employee,
            module='OVERTIME',
            action='REQUEST',
            description=f"Submitted overtime request for {ot.date} ({ot.hours} hrs)"
        )
        messages.success(self.request, "Overtime request submitted successfully!")
        return redirect(self.success_url)


class MyOvertimeCancelView(LoginRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        employee = getattr(request.user, 'employee_profile', None)
        if not employee:
            messages.error(request, "Employee profile not found.")
            return redirect('overtime:my_overtime')

        ot = get_object_or_404(OvertimeRequest, pk=pk, employee=employee)
        if ot.status != OvertimeRequest.Status.PENDING:
            messages.error(request, "Only pending overtime requests can be cancelled.")
            return redirect('overtime:my_overtime')

        ot.status = OvertimeRequest.Status.CANCELLED
        ot.save(update_fields=['status', 'updated_at'])
        log_activity(
            user=request.user,
            employee=employee,
            module='OVERTIME',
            action='CANCEL',
            description=f"Cancelled overtime request #{ot.pk} for {ot.date}"
        )
        messages.success(request, "Overtime request cancelled.")
        return redirect('overtime:my_overtime')


# ==========================================
# Overtime Analytics & Summary Reports
# ==========================================

def _get_overtime_report_data(request):
    today = timezone.localdate() if hasattr(timezone, 'localdate') else timezone.now().date()
    first_of_month = today.replace(day=1)

    from_date_str = request.GET.get('from_date') or first_of_month.strftime('%Y-%m-%d')
    to_date_str = request.GET.get('to_date') or today.strftime('%Y-%m-%d')
    selected_dept = request.GET.get('department', '')
    selected_employee = request.GET.get('employee', '')
    selected_type = request.GET.get('overtime_type', '')
    selected_status = request.GET.get('status', '')

    qs = OvertimeRequest.objects.select_related(
        'employee', 'employee__department', 'employee__position', 'overtime_type', 'approved_by'
    ).all()

    if from_date_str:
        qs = qs.filter(date__gte=from_date_str)
    if to_date_str:
        qs = qs.filter(date__lte=to_date_str)
    if selected_dept:
        qs = qs.filter(employee__department_id=selected_dept)
    if selected_employee:
        qs = qs.filter(employee_id=selected_employee)
    if selected_type:
        qs = qs.filter(overtime_type_id=selected_type)
    if selected_status:
        qs = qs.filter(status=selected_status)

    qs = qs.order_by('-date', '-created_at')

    stats = qs.aggregate(
        total_hours=Sum('hours'),
        total_amount=Sum('overtime_amount'),
        approved_hours=Sum('hours', filter=Q(status=OvertimeRequest.Status.APPROVED)),
        approved_amount=Sum('overtime_amount', filter=Q(status=OvertimeRequest.Status.APPROVED)),
        pending_hours=Sum('hours', filter=Q(status=OvertimeRequest.Status.PENDING)),
        total_requests=Count('id'),
        approved_count=Count('id', filter=Q(status=OvertimeRequest.Status.APPROVED)),
        pending_count=Count('id', filter=Q(status=OvertimeRequest.Status.PENDING)),
        rejected_count=Count('id', filter=Q(status=OvertimeRequest.Status.REJECTED)),
    )

    total_hours = stats['total_hours'] or Decimal('0.00')
    total_amount = stats['total_amount'] or Decimal('0.00')
    approved_hours = stats['approved_hours'] or Decimal('0.00')
    approved_amount = stats['approved_amount'] or Decimal('0.00')
    total_requests = stats['total_requests'] or 0
    approved_count = stats['approved_count'] or 0
    pending_count = stats['pending_count'] or 0
    rejected_count = stats['rejected_count'] or 0
    avg_hours = (total_hours / total_requests) if total_requests > 0 else Decimal('0.00')

    dept_qs = qs.values(
        'employee__department__name'
    ).annotate(
        total_hours=Sum('hours'),
        total_amount=Sum('overtime_amount'),
        emp_count=Count('employee', distinct=True),
        session_count=Count('id')
    ).order_by('-total_amount')

    dept_breakdown = []
    for d in dept_qs:
        dept_breakdown.append({
            'dept_name': d['employee__department__name'] or 'Unassigned',
            'emp_count': d['emp_count'],
            'total_hours': d['total_hours'] or Decimal('0.00'),
            'total_amount': d['total_amount'] or Decimal('0.00'),
            'session_count': d['session_count']
        })

    emp_qs = qs.values(
        'employee__id', 'employee__employee_code', 'employee__first_name', 'employee__last_name', 'employee__department__name'
    ).annotate(
        total_hours=Sum('hours'),
        total_amount=Sum('overtime_amount'),
        session_count=Count('id'),
        approved_count=Count('id', filter=Q(status=OvertimeRequest.Status.APPROVED))
    ).order_by('-total_amount')

    employee_breakdown = []
    for e in emp_qs:
        employee_breakdown.append({
            'emp_code': e['employee__employee_code'],
            'emp_name': f"{e['employee__first_name']} {e['employee__last_name']}".strip(),
            'dept_name': e['employee__department__name'] or '-',
            'total_hours': e['total_hours'] or Decimal('0.00'),
            'total_amount': e['total_amount'] or Decimal('0.00'),
            'session_count': e['session_count'],
            'approved_count': e['approved_count']
        })

    return {
        'from_date': from_date_str,
        'to_date': to_date_str,
        'selected_dept': selected_dept,
        'selected_employee': selected_employee,
        'selected_type': selected_type,
        'selected_status': selected_status,
        'total_hours': total_hours,
        'total_amount': total_amount,
        'approved_hours': approved_hours,
        'approved_amount': approved_amount,
        'pending_hours': stats['pending_hours'] or Decimal('0.00'),
        'total_requests': total_requests,
        'approved_count': approved_count,
        'pending_count': pending_count,
        'rejected_count': rejected_count,
        'avg_hours': avg_hours,
        'dept_breakdown': dept_breakdown,
        'employee_breakdown': employee_breakdown,
        'records': qs,
    }


class OvertimeReportView(RoleRequiredMixin, View):
    required_roles = ['super_admin', 'hr_admin', 'manager']
    template_name = 'overtime/report.html'

    def get(self, request, *args, **kwargs):
        data = _get_overtime_report_data(request)
        context = {
            **data,
            'departments': Department.objects.filter(status=True),
            'employees': Employee.objects.filter(status='active').select_related('department'),
            'overtime_types': OvertimeType.objects.filter(status=True),
        }
        return render(request, self.template_name, context)


class OvertimeReportExcelExportView(RoleRequiredMixin, View):
    required_roles = ['super_admin', 'hr_admin', 'manager']

    def get(self, request, *args, **kwargs):
        data = _get_overtime_report_data(request)
        generated_by = request.user.get_full_name() or request.user.username
        excel_bytes = generate_overtime_report_excel(data, generated_by=generated_by)
        filename = f"overtime_report_{data['from_date']}_{data['to_date']}.xlsx"
        resp = HttpResponse(
            excel_bytes,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        resp['Content-Disposition'] = f'attachment; filename="{filename}"'
        return resp


class OvertimeReportPdfExportView(RoleRequiredMixin, View):
    required_roles = ['super_admin', 'hr_admin', 'manager']

    def get(self, request, *args, **kwargs):
        data = _get_overtime_report_data(request)
        generated_by = request.user.get_full_name() or request.user.username
        pdf_bytes = generate_overtime_report_pdf(data, generated_by=generated_by)
        filename = f"overtime_report_{data['from_date']}_{data['to_date']}.pdf"
        resp = HttpResponse(pdf_bytes, content_type='application/pdf')
        resp['Content-Disposition'] = f'attachment; filename="{filename}"'
        return resp
