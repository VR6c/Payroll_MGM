import logging
from datetime import datetime
from django.db import transaction
from django.shortcuts import redirect, get_object_or_404
from django.http import HttpResponse, Http404
from django.contrib import messages
from django.urls import reverse_lazy
from django.views.generic import View, ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from accounts.mixins import RoleRequiredMixin
from employees.models import Employee
from .models import Payroll, SalaryStructure
from .forms import SalaryStructureForm, PayrollForm
from .services import PayrollCalculator
from reports.exporters import generate_payslip_pdf, generate_payroll_list_excel, generate_detail_report_pdf

logger = logging.getLogger('payroll')


class MyPayslipListView(LoginRequiredMixin, ListView):
    template_name = 'payroll/my_payslips.html'
    context_object_name = 'payrolls'
    paginate_by = 12

    def get_queryset(self):
        employee = getattr(self.request.user, 'employee_profile', None)
        if not employee:
            return Payroll.objects.none()
        return Payroll.objects.filter(
            employee=employee
        ).select_related('employee', 'employee__department', 'employee__position').order_by('-payroll_period')


class PayslipDetailView(LoginRequiredMixin, DetailView):
    model = Payroll
    template_name = 'payroll/payslip.html'

    def get_queryset(self):
        qs = Payroll.objects.select_related('employee', 'employee__department', 'employee__position', 'employee__company')
        if self.request.user.role in ['super_admin', 'hr_admin']:
            return qs.all()
        employee = getattr(self.request.user, 'employee_profile', None)
        if not employee:
            return qs.none()
        return qs.filter(employee=employee)


class PayslipPdfExportView(LoginRequiredMixin, View):
    def get(self, request, pk, *args, **kwargs):
        qs = Payroll.objects.select_related('employee', 'employee__department', 'employee__position', 'employee__company')
        if request.user.role not in ['super_admin', 'hr_admin']:
            employee = getattr(request.user, 'employee_profile', None)
            if not employee:
                raise Http404("Employee profile not found.")
            qs = qs.filter(employee=employee)

        payroll = get_object_or_404(qs, pk=pk)
        pdf_bytes = generate_payslip_pdf(payroll)
        filename = f"payslip_{payroll.employee.employee_code}_{payroll.payroll_period.strftime('%Y%m')}.pdf"
        resp = HttpResponse(pdf_bytes, content_type='application/pdf')
        resp['Content-Disposition'] = f'attachment; filename="{filename}"'
        return resp


class PayrollListExcelExportView(RoleRequiredMixin, View):
    required_roles = ['super_admin', 'hr_admin']

    def get(self, request, *args, **kwargs):
        qs = Payroll.objects.select_related('employee', 'employee__department', 'employee__position').all().order_by('-payroll_period')
        status = request.GET.get('status')
        period = request.GET.get('period')
        if status:
            qs = qs.filter(status=status)
        if period:
            qs = qs.filter(payroll_period=period)

        generated_by = request.user.get_full_name() or request.user.username
        excel_bytes = generate_payroll_list_excel(qs, generated_by=generated_by)
        filename = f"payroll_records_{datetime.now().strftime('%Y%m%d')}.xlsx"
        resp = HttpResponse(
            excel_bytes,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        resp['Content-Disposition'] = f'attachment; filename="{filename}"'
        return resp


class PayrollListPdfExportView(RoleRequiredMixin, View):
    required_roles = ['super_admin', 'hr_admin']

    def get(self, request, *args, **kwargs):
        qs = Payroll.objects.select_related('employee', 'employee__department', 'employee__position').all().order_by('-payroll_period')
        status = request.GET.get('status')
        period = request.GET.get('period')
        if status:
            qs = qs.filter(status=status)
        if period:
            qs = qs.filter(payroll_period=period)

        generated_by = request.user.get_full_name() or request.user.username
        pdf_bytes = generate_detail_report_pdf('payroll', qs, generated_by=generated_by)
        filename = f"payroll_records_{datetime.now().strftime('%Y%m%d')}.pdf"
        resp = HttpResponse(pdf_bytes, content_type='application/pdf')
        resp['Content-Disposition'] = f'attachment; filename="{filename}"'
        return resp


class PayrollListView(RoleRequiredMixin, ListView):
    model = Payroll
    template_name = 'payroll/list.html'
    context_object_name = 'payrolls'
    paginate_by = 50
    required_roles = ['super_admin', 'hr_admin']

    def get_queryset(self):
        qs = Payroll.objects.select_related('employee', 'employee__department', 'employee__position').all().order_by('-payroll_period')
        status = self.request.GET.get('status')
        period = self.request.GET.get('period')
        if status:
            qs = qs.filter(status=status)
        if period:
            qs = qs.filter(payroll_period=period)
        return qs


class SalarySetupView(RoleRequiredMixin, ListView):
    model = SalaryStructure
    template_name = 'payroll/salary_setup.html'
    context_object_name = 'structures'
    paginate_by = 20
    required_roles = ['super_admin', 'hr_admin']

    def get_queryset(self):
        return SalaryStructure.objects.select_related('employee', 'employee__department', 'employee__position').all()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['employees'] = Employee.objects.filter(status='active').select_related('department', 'position')
        ctx['form'] = SalaryStructureForm()
        return ctx


class SalaryStructureCreateView(RoleRequiredMixin, CreateView):
    model = SalaryStructure
    form_class = SalaryStructureForm
    success_url = reverse_lazy('payroll:salary_setup')
    required_roles = ['super_admin', 'hr_admin']

    def form_valid(self, form):
        messages.success(self.request, "Salary structure created successfully!")
        return super().form_valid(form)


class SalaryStructureUpdateView(RoleRequiredMixin, UpdateView):
    model = SalaryStructure
    form_class = SalaryStructureForm
    success_url = reverse_lazy('payroll:salary_setup')
    required_roles = ['super_admin', 'hr_admin']

    def form_valid(self, form):
        messages.success(self.request, "Salary structure updated successfully!")
        return super().form_valid(form)


class SalaryStructureDeleteView(RoleRequiredMixin, DeleteView):
    model = SalaryStructure
    success_url = reverse_lazy('payroll:salary_setup')
    required_roles = ['super_admin', 'hr_admin']

    def post(self, request, *args, **kwargs):
        messages.success(self.request, "Salary structure deleted successfully!")
        return super().post(request, *args, **kwargs)


class BonusIncentiveView(RoleRequiredMixin, ListView):
    model = Payroll
    template_name = 'payroll/bonuses.html'
    context_object_name = 'payrolls'
    paginate_by = 20
    required_roles = ['super_admin', 'hr_admin']

    def get_queryset(self):
        return Payroll.objects.select_related('employee', 'employee__department', 'employee__position').filter(bonus__gt=0).order_by('-payroll_period')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['employees'] = Employee.objects.filter(status='active').select_related('department', 'position')
        ctx['all_payrolls'] = Payroll.objects.select_related('employee', 'employee__department', 'employee__position').order_by('-payroll_period')
        return ctx


class BonusAddView(RoleRequiredMixin, UpdateView):
    model = Payroll
    fields = ['bonus']
    success_url = reverse_lazy('payroll:bonuses')
    required_roles = ['super_admin', 'hr_admin']

    def form_valid(self, form):
        payroll = form.save(commit=False)
        PayrollCalculator.recalculate_payroll_totals(payroll)
        messages.success(self.request, "Bonus / Incentive added successfully!")
        return redirect('payroll:bonuses')


class AllowanceView(RoleRequiredMixin, ListView):
    model = SalaryStructure
    template_name = 'payroll/allowances.html'
    context_object_name = 'structures'
    paginate_by = 20
    required_roles = ['super_admin', 'hr_admin']

    def get_queryset(self):
        return SalaryStructure.objects.select_related('employee', 'employee__department', 'employee__position').all()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['employees'] = Employee.objects.filter(status='active').select_related('department', 'position')
        return ctx


class NewPayrollView(RoleRequiredMixin, ListView):
    model = Payroll
    template_name = 'payroll/new_payroll.html'
    context_object_name = 'payrolls'
    required_roles = ['super_admin', 'hr_admin']

    def post(self, request, *args, **kwargs):
        period_str = request.POST.get('payroll_period')
        if period_str:
            try:
                period_date = datetime.strptime(period_str + '-01', '%Y-%m-%d').date()
                employees = Employee.objects.filter(status='active')
                created_count = 0
                failed_count = 0

                for emp in employees:
                    try:
                        with transaction.atomic():
                            PayrollCalculator.generate_for_employee(emp, period_date)
                            created_count += 1
                    except Exception as err:
                        failed_count += 1
                        logger.warning(f"Payroll generation skipped for {emp}: {err}")

                if created_count > 0:
                    messages.success(request, f"Payroll successfully generated for {created_count} employee(s) for period {period_str}.")
                if failed_count > 0:
                    messages.warning(request, f"Skipped {failed_count} employee(s) without an active salary structure or valid inputs.")
            except Exception as e:
                messages.error(request, f"Error processing payroll: {e}")
        return redirect('payroll:new_payroll')


class PayrollDeleteView(RoleRequiredMixin, DeleteView):
    model = Payroll
    success_url = reverse_lazy('payroll:list')
    required_roles = ['super_admin', 'hr_admin']

    def post(self, request, *args, **kwargs):
        messages.success(self.request, "Payroll record deleted successfully!")
        return super().post(request, *args, **kwargs)




