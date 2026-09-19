import re
from django.shortcuts import redirect
from django.contrib import messages
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from accounts.mixins import RoleRequiredMixin
from companies.models import Company
from companies.services import get_default_company
from employees.models import Employee
from .models import LeavePeriod, LeaveRequest, LeaveType, LeaveBalance
from .forms import LeaveRequestForm, LeaveTypeForm, LeaveBalanceForm


def _create_leave_periods(leave_request, post_data):
    """Parses period fields from POST data and creates LeavePeriod instances."""
    period_indices = {match.group(1) for key in post_data.keys() if (match := re.match(r'^periods-(\d+)-start_date$', key))}
    for idx in period_indices:
        start_date = post_data.get(f'periods-{idx}-start_date')
        end_date = post_data.get(f'periods-{idx}-end_date')
        days = post_data.get(f'periods-{idx}-days')
        if start_date and end_date and days:
            LeavePeriod.objects.create(
                leave_request=leave_request,
                start_date=start_date,
                end_date=end_date,
                days=days
            )


class LeaveRequestCreateView(LoginRequiredMixin, CreateView):
    form_class = LeaveRequestForm
    template_name = 'leave/create.html'
    success_url = reverse_lazy('leave:my_leaves')

    def form_valid(self, form):
        employee = getattr(self.request.user, 'employee_profile', None)
        if not employee:
            messages.error(self.request, "Only registered employees can submit leave requests.")
            return redirect('leave:my_leaves')
        leave = form.save(commit=False)
        leave.employee = employee
        leave.save()
        _create_leave_periods(leave, self.request.POST)
        messages.success(self.request, "Leave request submitted successfully!")
        return redirect(self.success_url)


class MyLeaveListView(LoginRequiredMixin, ListView):
    template_name = 'leave/my_leaves.html'
    context_object_name = 'leaves'
    paginate_by = 20

    def get_queryset(self):
        employee = getattr(self.request.user, 'employee_profile', None)
        if not employee:
            return LeaveRequest.objects.none()
        return LeaveRequest.objects.filter(
            employee=employee
        ).select_related('leave_type', 'approved_by').prefetch_related('periods').order_by('-created_at')


class LeaveTypeListView(RoleRequiredMixin, ListView):
    model = LeaveType
    template_name = 'leave/types.html'
    context_object_name = 'leave_types'
    paginate_by = 20
    required_roles = ['super_admin', 'hr_admin', 'manager']

    def get_queryset(self):
        return LeaveType.objects.select_related('company').all()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        get_default_company()
        ctx['companies'] = Company.objects.all()
        ctx['form'] = LeaveTypeForm()
        return ctx


class LeaveTypeCreateView(RoleRequiredMixin, CreateView):
    model = LeaveType
    form_class = LeaveTypeForm
    success_url = reverse_lazy('leave:types')
    required_roles = ['super_admin', 'hr_admin']

    def form_valid(self, form):
        if not form.cleaned_data.get('company'):
            form.instance.company = get_default_company()
        messages.success(self.request, "Leave type created successfully!")
        return super().form_valid(form)


class LeaveTypeUpdateView(RoleRequiredMixin, UpdateView):
    model = LeaveType
    form_class = LeaveTypeForm
    success_url = reverse_lazy('leave:types')
    required_roles = ['super_admin', 'hr_admin']

    def form_valid(self, form):
        if not form.cleaned_data.get('company'):
            form.instance.company = get_default_company()
        messages.success(self.request, "Leave type updated successfully!")
        return super().form_valid(form)


class LeaveTypeDeleteView(RoleRequiredMixin, DeleteView):
    model = LeaveType
    success_url = reverse_lazy('leave:types')
    required_roles = ['super_admin', 'hr_admin']

    def post(self, request, *args, **kwargs):
        messages.success(self.request, "Leave type deleted successfully!")
        return super().post(request, *args, **kwargs)


class LeaveTypeGroupListView(RoleRequiredMixin, ListView):
    model = LeaveBalance
    template_name = 'leave/type_groups.html'
    context_object_name = 'balances'
    paginate_by = 20
    required_roles = ['super_admin', 'hr_admin', 'manager']

    def get_queryset(self):
        return LeaveBalance.objects.select_related('employee', 'employee__department', 'leave_type').all()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['employees'] = Employee.objects.filter(status='active').select_related('department', 'position')
        ctx['leave_types'] = LeaveType.objects.filter(status=True)
        ctx['form'] = LeaveBalanceForm()
        return ctx


class LeaveBalanceCreateView(RoleRequiredMixin, CreateView):
    model = LeaveBalance
    form_class = LeaveBalanceForm
    success_url = reverse_lazy('leave:type_groups')
    required_roles = ['super_admin', 'hr_admin']

    def form_valid(self, form):
        messages.success(self.request, "Leave balance allocated successfully!")
        return super().form_valid(form)


class LeaveBalanceUpdateView(RoleRequiredMixin, UpdateView):
    model = LeaveBalance
    form_class = LeaveBalanceForm
    success_url = reverse_lazy('leave:type_groups')
    required_roles = ['super_admin', 'hr_admin']

    def form_valid(self, form):
        messages.success(self.request, "Leave balance updated successfully!")
        return super().form_valid(form)


class LeaveBalanceDeleteView(RoleRequiredMixin, DeleteView):
    model = LeaveBalance
    success_url = reverse_lazy('leave:type_groups')
    required_roles = ['super_admin', 'hr_admin']

    def post(self, request, *args, **kwargs):
        messages.success(self.request, "Leave balance deleted successfully!")
        return super().post(request, *args, **kwargs)




