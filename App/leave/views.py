import re
from decimal import Decimal
from django.utils import timezone
from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, ListView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from accounts.mixins import RoleRequiredMixin
from activities.services import log_activity
from companies.models import Company
from companies.services import get_default_company
from employees.models import Employee
from .models import LeavePeriod, LeaveRequest, LeaveType, LeaveBalance
from .forms import LeaveRequestForm, LeaveTypeForm, LeaveBalanceForm
from .services import LeaveService


def _create_leave_periods(leave_request, post_data):
    """Parses period fields from POST data and creates LeavePeriod instances."""
    period_indices = {match.group(1) for key in post_data.keys() if (match := re.match(r'^periods-(\d+)-start_date$', key))}
    for idx in sorted(period_indices, key=int):
        start_date = post_data.get(f'periods-{idx}-start_date')
        end_date = post_data.get(f'periods-{idx}-end_date')
        days = post_data.get(f'periods-{idx}-days')
        if start_date and end_date and days:
            try:
                days_val = Decimal(str(days))
                LeavePeriod.objects.create(
                    leave_request=leave_request,
                    start_date=start_date,
                    end_date=end_date,
                    days=days_val
                )
            except Exception:
                continue


class LeaveRequestCreateView(LoginRequiredMixin, CreateView):
    form_class = LeaveRequestForm
    template_name = 'leave/create.html'
    success_url = reverse_lazy('leave:my_leaves')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        ctx['is_admin_or_mgr'] = user.role in ['super_admin', 'hr_admin', 'manager'] or user.is_superuser
        return ctx

    def form_valid(self, form):
        is_admin_or_mgr = self.request.user.role in ['super_admin', 'hr_admin', 'manager'] or self.request.user.is_superuser
        if is_admin_or_mgr:
            employee = form.cleaned_data.get('employee')
            if not employee:
                employee = getattr(self.request.user, 'employee_profile', None)
            if not employee:
                messages.error(self.request, "Please select an employee for this leave request.")
                return self.form_invalid(form)
            status = form.cleaned_data.get('status') or LeaveRequest.Status.PENDING
        else:
            employee = getattr(self.request.user, 'employee_profile', None)
            if not employee:
                messages.error(self.request, "Only registered employees can submit leave requests.")
                return redirect('leave:my_leaves')
            status = LeaveRequest.Status.PENDING

        leave = form.save(commit=False)
        leave.employee = employee
        leave.status = status
        if status in [LeaveRequest.Status.APPROVED, LeaveRequest.Status.REJECTED]:
            leave.approved_by = self.request.user
            leave.approved_at = timezone.now()
        else:
            leave.approved_by = None
            leave.approved_at = None

        leave.save()
        _create_leave_periods(leave, self.request.POST)

        # Recalculate total_days from created periods and persist
        total_days = sum((p.days for p in leave.periods.all()), Decimal('0'))
        leave.total_days = total_days
        leave.save(update_fields=['total_days'])

        if status == LeaveRequest.Status.APPROVED:
            current_year = leave.created_at.year if leave.created_at else timezone.now().year
            balance = LeaveBalance.objects.filter(
                employee=leave.employee,
                leave_type=leave.leave_type,
                year=current_year
            ).first()
            if balance:
                used = Decimal(str(balance.used_days or 0)) + Decimal(str(leave.total_days or 0))
                allocated = Decimal(str(balance.allocated_days or 0))
                balance.used_days = used
                balance.remaining_days = max(Decimal('0'), allocated - used)
                balance.save(update_fields=['used_days', 'remaining_days'])
            elif leave.leave_type and leave.leave_type.default_days:
                allocated = Decimal(str(leave.leave_type.default_days))
                used = Decimal(str(leave.total_days or 0))
                LeaveBalance.objects.create(
                    employee=leave.employee,
                    leave_type=leave.leave_type,
                    year=current_year,
                    allocated_days=allocated,
                    used_days=used,
                    remaining_days=max(Decimal('0'), allocated - used)
                )

        status_display = leave.get_status_display()
        log_activity(
            user=self.request.user,
            employee=employee,
            module='LEAVE',
            action='CREATE',
            description=f"Created leave request #{leave.pk} ({leave.leave_type.name}, {leave.total_days} days, status: {status_display}) for {employee}"
        )

        messages.success(self.request, f"Leave request for {employee} submitted successfully ({status_display})!")
        return redirect(self.success_url)


class MyLeaveListView(LoginRequiredMixin, ListView):
    template_name = 'leave/my_leaves.html'
    context_object_name = 'leaves'
    paginate_by = 20

    def get_queryset(self):
        user = self.request.user
        is_admin_or_mgr = user.role in ['super_admin', 'hr_admin', 'manager'] or user.is_superuser
        qs = LeaveRequest.objects.select_related(
            'employee', 'employee__department', 'employee__position',
            'leave_type', 'approved_by'
        ).prefetch_related('periods').order_by('-created_at')

        if not is_admin_or_mgr:
            employee = getattr(user, 'employee_profile', None)
            if not employee:
                return LeaveRequest.objects.none()
            qs = qs.filter(employee=employee)
        else:
            status_filter = self.request.GET.get('status')
            if status_filter:
                qs = qs.filter(status=status_filter)
            employee_filter = self.request.GET.get('employee')
            if employee_filter:
                qs = qs.filter(employee_id=employee_filter)

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        is_admin_or_mgr = user.role in ['super_admin', 'hr_admin', 'manager'] or user.is_superuser
        ctx['is_admin_or_mgr'] = is_admin_or_mgr

        base_qs = LeaveRequest.objects.all() if is_admin_or_mgr else LeaveRequest.objects.filter(employee=getattr(user, 'employee_profile', None))
        ctx['total_count'] = base_qs.count()
        ctx['pending_count'] = base_qs.filter(status=LeaveRequest.Status.PENDING).count()
        ctx['approved_count'] = base_qs.filter(status=LeaveRequest.Status.APPROVED).count()
        ctx['rejected_count'] = base_qs.filter(status=LeaveRequest.Status.REJECTED).count()

        if is_admin_or_mgr:
            ctx['employees'] = Employee.objects.filter(status='active').order_by('first_name', 'last_name')
            ctx['current_status'] = self.request.GET.get('status', '')
            ctx['current_employee'] = self.request.GET.get('employee', '')

        return ctx


class LeaveApproveView(RoleRequiredMixin, View):
    required_roles = ['super_admin', 'hr_admin', 'manager']

    def post(self, request, pk, *args, **kwargs):
        leave = get_object_or_404(LeaveRequest, pk=pk)
        LeaveService.approve_request(leave, request.user)
        messages.success(request, f"Leave request #{leave.pk} for {leave.employee} has been approved.")
        return redirect(request.META.get('HTTP_REFERER', 'leave:my_leaves'))


class LeaveRejectView(RoleRequiredMixin, View):
    required_roles = ['super_admin', 'hr_admin', 'manager']

    def post(self, request, pk, *args, **kwargs):
        leave = get_object_or_404(LeaveRequest, pk=pk)
        LeaveService.reject_request(leave, request.user)
        messages.info(request, f"Leave request #{leave.pk} for {leave.employee} has been rejected.")
        return redirect(request.META.get('HTTP_REFERER', 'leave:my_leaves'))


class LeaveCancelView(LoginRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        leave = get_object_or_404(LeaveRequest, pk=pk)
        is_admin_or_mgr = request.user.role in ['super_admin', 'hr_admin', 'manager'] or request.user.is_superuser
        emp = getattr(request.user, 'employee_profile', None)
        if not is_admin_or_mgr and leave.employee != emp:
            messages.error(request, "You are not authorized to cancel this leave request.")
            return redirect('leave:my_leaves')

        LeaveService.cancel_request(leave, request.user)
        messages.info(request, f"Leave request #{leave.pk} has been cancelled.")
        return redirect(request.META.get('HTTP_REFERER', 'leave:my_leaves'))


class LeaveRequestUpdateView(LoginRequiredMixin, UpdateView):
    model = LeaveRequest
    form_class = LeaveRequestForm
    template_name = 'leave/create.html'
    success_url = reverse_lazy('leave:my_leaves')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        ctx['is_admin_or_mgr'] = user.role in ['super_admin', 'hr_admin', 'manager'] or user.is_superuser
        ctx['is_edit'] = True
        ctx['leave_request'] = self.object
        ctx['existing_periods'] = self.object.periods.all().order_by('start_date')
        return ctx

    def form_valid(self, form):
        is_admin_or_mgr = self.request.user.role in ['super_admin', 'hr_admin', 'manager'] or self.request.user.is_superuser
        emp = getattr(self.request.user, 'employee_profile', None)
        leave = self.object

        if not is_admin_or_mgr and leave.employee != emp:
            messages.error(self.request, "You are not authorized to edit this leave request.")
            return redirect('leave:my_leaves')

        if not is_admin_or_mgr and leave.status != LeaveRequest.Status.PENDING:
            messages.error(self.request, "You can only edit leave requests that are pending.")
            return redirect('leave:my_leaves')

        old_snapshot = {
            'status': leave.status,
            'total_days': leave.total_days,
            'employee_id': leave.employee_id,
            'leave_type_id': leave.leave_type_id,
        }

        updated_leave = form.save(commit=False)

        if is_admin_or_mgr:
            new_employee = form.cleaned_data.get('employee')
            if new_employee:
                updated_leave.employee = new_employee
            new_status = form.cleaned_data.get('status') or leave.status
            updated_leave.status = new_status
            if new_status in [LeaveRequest.Status.APPROVED, LeaveRequest.Status.REJECTED]:
                updated_leave.approved_by = self.request.user
                updated_leave.approved_at = timezone.now()
            elif new_status == LeaveRequest.Status.PENDING:
                updated_leave.approved_by = None
                updated_leave.approved_at = None

        updated_leave.save()

        # Update periods if passed
        post_data = self.request.POST
        has_period_keys = any(re.match(r'^periods-\d+-start_date$', k) for k in post_data.keys())
        if has_period_keys:
            updated_leave.periods.all().delete()
            _create_leave_periods(updated_leave, post_data)
            total_days = sum((p.days for p in updated_leave.periods.all()), Decimal('0'))
            if total_days > 0:
                updated_leave.total_days = total_days
                updated_leave.save(update_fields=['total_days'])

        # Adjust leave balance synchronization
        LeaveService.adjust_balance_on_update(old_snapshot, updated_leave)

        status_display = updated_leave.get_status_display()
        log_activity(
            user=self.request.user,
            employee=updated_leave.employee,
            module='LEAVE',
            action='UPDATE',
            description=f"Updated leave request #{updated_leave.pk} ({updated_leave.leave_type.name}, {updated_leave.total_days} days, status: {status_display}) for {updated_leave.employee}"
        )

        messages.success(self.request, f"Leave request #{updated_leave.pk} updated successfully!")
        return redirect(self.success_url)


class LeaveRequestDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        leave = get_object_or_404(LeaveRequest, pk=pk)
        is_admin_or_mgr = request.user.role in ['super_admin', 'hr_admin', 'manager'] or request.user.is_superuser
        emp = getattr(request.user, 'employee_profile', None)

        if not is_admin_or_mgr and (leave.employee != emp or leave.status != LeaveRequest.Status.PENDING):
            messages.error(request, "You are not authorized to delete this leave request.")
            return redirect('leave:my_leaves')

        LeaveService.delete_request(leave, request.user)
        messages.success(request, f"Leave request #{pk} has been deleted successfully.")
        return redirect('leave:my_leaves')


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
