import re
import datetime
from decimal import Decimal
from django.utils import timezone
from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages
from django.urls import reverse, reverse_lazy
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
from django.db.models import Count, Q
from .services import (
    LeaveService,
    check_periods_overlap,
    parse_and_validate_leave_periods,
    _create_leave_periods,
)



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
        if self.request.method == 'POST':
            periods_list = []
            period_indices = {match.group(1) for key in self.request.POST.keys() if (match := re.match(r'^periods-(\d+)-start_date$', key))}
            for idx in sorted(period_indices, key=int):
                periods_list.append({
                    'start_date': self.request.POST.get(f'periods-{idx}-start_date', ''),
                    'end_date': self.request.POST.get(f'periods-{idx}-end_date', ''),
                    'days': self.request.POST.get(f'periods-{idx}-days', '1.0'),
                    'start_time': self.request.POST.get(f'periods-{idx}-start_time', ''),
                    'end_time': self.request.POST.get(f'periods-{idx}-end_time', ''),
                })
            if periods_list:
                ctx['posted_periods'] = periods_list
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

        cleaned_periods, err = parse_and_validate_leave_periods(self.request.POST, employee=employee)
        if err:
            messages.error(self.request, err)
            return self.form_invalid(form)

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
        _create_leave_periods(leave, cleaned_periods)

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


class LeaveRequestListView(LoginRequiredMixin, ListView):
    template_name = 'leave/my_leaves.html'
    context_object_name = 'leaves'
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        user = request.user
        is_admin_or_mgr = (
            user.role in ['super_admin', 'hr_admin', 'manager']
            or user.is_superuser
            or (hasattr(user, 'role_obj') and user.role_obj and not user.role_obj.is_system and user.has_permission('leave.view'))
        )
        if not is_admin_or_mgr:
            return redirect('leave:my_leaves')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        qs = LeaveRequest.objects.select_related(
            'employee', 'employee__department', 'employee__position',
            'leave_type', 'approved_by'
        ).prefetch_related('periods').order_by('-created_at')

        status_filter = self.request.GET.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        employee_filter = self.request.GET.get('employee')
        if employee_filter:
            qs = qs.filter(employee_id=employee_filter)

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['is_admin_or_mgr'] = True

        base_qs = LeaveRequest.objects.all()
        counts = base_qs.aggregate(
            total=Count('id'),
            pending=Count('id', filter=Q(status=LeaveRequest.Status.PENDING)),
            approved=Count('id', filter=Q(status=LeaveRequest.Status.APPROVED)),
            rejected=Count('id', filter=Q(status=LeaveRequest.Status.REJECTED)),
        )
        ctx['total_count'] = counts['total'] or 0
        ctx['pending_count'] = counts['pending'] or 0
        ctx['approved_count'] = counts['approved'] or 0
        ctx['rejected_count'] = counts['rejected'] or 0

        ctx['employees'] = Employee.objects.filter(status='active').order_by('first_name', 'last_name')
        ctx['current_status'] = self.request.GET.get('status', '')
        ctx['current_employee'] = self.request.GET.get('employee', '')
        ctx['reset_url'] = reverse('leave:list')
        return ctx


class MyLeaveListView(LoginRequiredMixin, ListView):
    template_name = 'leave/my_leaves.html'
    context_object_name = 'leaves'
    paginate_by = 20

    def get_queryset(self):
        user = self.request.user
        employee = getattr(user, 'employee_profile', None)
        if not employee:
            return LeaveRequest.objects.none()

        qs = LeaveRequest.objects.filter(
            employee=employee
        ).select_related(
            'employee', 'employee__department', 'employee__position',
            'leave_type', 'approved_by'
        ).prefetch_related('periods').order_by('-created_at')

        status_filter = self.request.GET.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        employee = getattr(user, 'employee_profile', None)
        ctx['is_admin_or_mgr'] = False

        if employee:
            base_qs = LeaveRequest.objects.filter(employee=employee)
            counts = base_qs.aggregate(
                total=Count('id'),
                pending=Count('id', filter=Q(status=LeaveRequest.Status.PENDING)),
                approved=Count('id', filter=Q(status=LeaveRequest.Status.APPROVED)),
                rejected=Count('id', filter=Q(status=LeaveRequest.Status.REJECTED)),
            )
            ctx['total_count'] = counts['total'] or 0
            ctx['pending_count'] = counts['pending'] or 0
            ctx['approved_count'] = counts['approved'] or 0
            ctx['rejected_count'] = counts['rejected'] or 0
            ctx['balances'] = LeaveBalance.objects.filter(
                employee=employee,
                year=timezone.now().year
            ).select_related('leave_type')
        else:
            ctx['total_count'] = 0
            ctx['pending_count'] = 0
            ctx['approved_count'] = 0
            ctx['rejected_count'] = 0
            ctx['balances'] = []

        ctx['current_status'] = self.request.GET.get('status', '')
        ctx['reset_url'] = reverse('leave:my_leaves')
        return ctx


class LeaveApproveView(RoleRequiredMixin, View):
    required_roles = ['super_admin', 'hr_admin', 'manager']

    def post(self, request, pk, *args, **kwargs):
        leave = get_object_or_404(LeaveRequest, pk=pk)
        LeaveService.approve_request(leave, request.user)
        messages.success(request, f"Leave request #{leave.pk} for {leave.employee} has been approved.")
        return redirect(request.META.get('HTTP_REFERER') or 'leave:list')


class LeaveRejectView(RoleRequiredMixin, View):
    required_roles = ['super_admin', 'hr_admin', 'manager']

    def post(self, request, pk, *args, **kwargs):
        leave = get_object_or_404(LeaveRequest, pk=pk)
        LeaveService.reject_request(leave, request.user)
        messages.info(request, f"Leave request #{leave.pk} for {leave.employee} has been rejected.")
        return redirect(request.META.get('HTTP_REFERER') or 'leave:list')


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
        return redirect(request.META.get('HTTP_REFERER') or 'leave:my_leaves')


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
        if self.request.method == 'POST':
            periods_list = []
            period_indices = {match.group(1) for key in self.request.POST.keys() if (match := re.match(r'^periods-(\d+)-start_date$', key))}
            for idx in sorted(period_indices, key=int):
                periods_list.append({
                    'start_date': self.request.POST.get(f'periods-{idx}-start_date', ''),
                    'end_date': self.request.POST.get(f'periods-{idx}-end_date', ''),
                    'days': self.request.POST.get(f'periods-{idx}-days', '1.0'),
                    'start_time': self.request.POST.get(f'periods-{idx}-start_time', ''),
                    'end_time': self.request.POST.get(f'periods-{idx}-end_time', ''),
                })
            if periods_list:
                ctx['posted_periods'] = periods_list
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

        target_employee = leave.employee
        if is_admin_or_mgr:
            new_employee = form.cleaned_data.get('employee')
            if new_employee:
                target_employee = new_employee

        post_data = self.request.POST
        has_period_keys = any(re.match(r'^periods-\d+-start_date$', k) for k in post_data.keys())
        cleaned_periods = None
        if has_period_keys:
            cleaned_periods, err = parse_and_validate_leave_periods(
                post_data, employee=target_employee, exclude_leave_id=leave.id
            )
            if err:
                messages.error(self.request, err)
                return self.form_invalid(form)

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
        if cleaned_periods is not None:
            updated_leave.periods.all().delete()
            _create_leave_periods(updated_leave, cleaned_periods)
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
