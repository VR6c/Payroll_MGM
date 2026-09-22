import re
import datetime
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


def check_periods_overlap(p1, p2):
    """
    Checks whether two leave periods overlap.
    p1 and p2 can be dicts or LeavePeriod model instances.
    """
    s1 = p1['start_date'] if isinstance(p1, dict) else p1.start_date
    e1 = p1['end_date'] if isinstance(p1, dict) else p1.end_date
    s2 = p2['start_date'] if isinstance(p2, dict) else p2.start_date
    e2 = p2['end_date'] if isinstance(p2, dict) else p2.end_date

    t_s1 = p1.get('start_time') if isinstance(p1, dict) else getattr(p1, 'start_time', None)
    t_e1 = p1.get('end_time') if isinstance(p1, dict) else getattr(p1, 'end_time', None)
    t_s2 = p2.get('start_time') if isinstance(p2, dict) else getattr(p2, 'start_time', None)
    t_e2 = p2.get('end_time') if isinstance(p2, dict) else getattr(p2, 'end_time', None)

    latest_start = max(s1, s2)
    earliest_end = min(e1, e2)

    # Date ranges do not intersect
    if latest_start > earliest_end:
        return False

    # Date ranges intersect: check if single-day hourly non-overlapping window
    if latest_start == earliest_end and s1 == e1 and s2 == e2 and t_s1 and t_e1 and t_s2 and t_e2:
        # Both are single-day with defined times: no overlap if one ends before or when other starts
        if t_e1 <= t_s2 or t_e2 <= t_s1:
            return False
        return True

    # Otherwise (e.g. multi-day or at least one is full day or overlapping times)
    return True


def parse_and_validate_leave_periods(post_data, employee=None, exclude_leave_id=None):
    """
    Parses and validates leave periods from POST data.
    Ensures:
    - At least one period is provided.
    - Dates are valid and start_date <= end_date.
    - Days > 0.
    - If hourly times are provided, start_time < end_time.
    - No two periods within the same submission duplicate or overlap.
    - No submitted period conflicts with existing approved or pending leaves for the employee.
    Returns (cleaned_periods_list, error_message).
    """
    period_indices = {match.group(1) for key in post_data.keys() if (match := re.match(r'^periods-(\d+)-start_date$', key))}
    if not period_indices:
        return None, "Please specify at least one leave period."

    cleaned_periods = []
    for idx in sorted(period_indices, key=int):
        s_date_str = post_data.get(f'periods-{idx}-start_date')
        e_date_str = post_data.get(f'periods-{idx}-end_date')
        days_str = post_data.get(f'periods-{idx}-days')
        s_time_str = post_data.get(f'periods-{idx}-start_time')
        e_time_str = post_data.get(f'periods-{idx}-end_time')

        if not s_date_str or not e_date_str or not days_str:
            return None, f"Period #{int(idx) + 1} has missing required date or duration fields."

        try:
            s_date = datetime.date.fromisoformat(s_date_str.strip())
            e_date = datetime.date.fromisoformat(e_date_str.strip())
        except (ValueError, TypeError):
            return None, f"Period #{int(idx) + 1} contains an invalid date format."

        if e_date < s_date:
            return None, f"Period #{int(idx) + 1} End Date ({e_date_str}) cannot be before Start Date ({s_date_str})."

        try:
            days_val = Decimal(str(days_str).strip())
            if days_val <= Decimal('0'):
                return None, f"Period #{int(idx) + 1} duration must be greater than 0."
        except Exception:
            return None, f"Period #{int(idx) + 1} duration is not a valid number."

        s_time = None
        e_time = None
        if s_time_str and s_time_str.strip() and e_time_str and e_time_str.strip():
            try:
                s_time = datetime.time.fromisoformat(s_time_str.strip())
                e_time = datetime.time.fromisoformat(e_time_str.strip())
            except (ValueError, TypeError):
                return None, f"Period #{int(idx) + 1} contains an invalid time format."

            if s_date == e_date and e_time <= s_time:
                return None, f"Period #{int(idx) + 1} End Time ({e_time_str}) must be after Start Time ({s_time_str})."

        cleaned_periods.append({
            'index': int(idx) + 1,
            'start_date': s_date,
            'end_date': e_date,
            'start_time': s_time,
            'end_time': e_time,
            'days': days_val
        })

    if not cleaned_periods:
        return None, "Please specify at least one valid leave period."

    # 1. Intra-request overlap check (between periods in the same submission)
    for i in range(len(cleaned_periods)):
        for j in range(i + 1, len(cleaned_periods)):
            p1 = cleaned_periods[i]
            p2 = cleaned_periods[j]
            if check_periods_overlap(p1, p2):
                if p1['start_date'] == p2['start_date'] and p1['end_date'] == p2['end_date']:
                    if not p1['start_time'] or not p2['start_time']:
                        return None, (
                            f"Duplicate date detected: Period #{p1['index']} and Period #{p2['index']} "
                            f"both cover {p1['start_date']}. Please remove duplicate dates or specify distinct hours."
                        )
                    else:
                        return None, (
                            f"Overlapping hours detected: Period #{p1['index']} ({p1['start_time'].strftime('%H:%M')}-{p1['end_time'].strftime('%H:%M')}) "
                            f"and Period #{p2['index']} ({p2['start_time'].strftime('%H:%M')}-{p2['end_time'].strftime('%H:%M')}) "
                            f"conflict on {p1['start_date']}."
                        )
                else:
                    return None, (
                        f"Overlapping periods detected: Period #{p1['index']} ({p1['start_date']} to {p1['end_date']}) "
                        f"and Period #{p2['index']} ({p2['start_date']} to {p2['end_date']}) overlap."
                    )

    # 2. Database collision check (against employee's active leaves)
    if employee:
        active_requests = LeaveRequest.objects.filter(
            employee=employee,
            status__in=[LeaveRequest.Status.PENDING, LeaveRequest.Status.APPROVED]
        )
        if exclude_leave_id:
            active_requests = active_requests.exclude(pk=exclude_leave_id)

        existing_periods = LeavePeriod.objects.filter(
            leave_request__in=active_requests
        ).select_related('leave_request', 'leave_request__leave_type')

        for new_p in cleaned_periods:
            for ex in existing_periods:
                if check_periods_overlap(new_p, ex):
                    t_new = f" ({new_p['start_time'].strftime('%H:%M')}-{new_p['end_time'].strftime('%H:%M')})" if new_p['start_time'] else ""
                    t_ex = f" ({ex.start_time.strftime('%H:%M')}-{ex.end_time.strftime('%H:%M')})" if ex.start_time else ""
                    return None, (
                        f"Leave conflict: Requested period {new_p['start_date']}{t_new} to {new_p['end_date']} "
                        f"conflicts with existing {ex.leave_request.get_status_display()} leave request #{ex.leave_request.id} "
                        f"({ex.start_date}{t_ex} to {ex.end_date}, {ex.leave_request.leave_type.name})."
                    )

    return cleaned_periods, None


def _create_leave_periods(leave_request, periods_input):
    """
    Creates LeavePeriod instances from either cleaned periods list or raw POST data.
    """
    if isinstance(periods_input, list):
        for p in periods_input:
            LeavePeriod.objects.create(
                leave_request=leave_request,
                start_date=p['start_date'],
                end_date=p['end_date'],
                start_time=p.get('start_time'),
                end_time=p.get('end_time'),
                days=p['days']
            )
        return

    # Fallback for raw POST dict
    period_indices = {match.group(1) for key in periods_input.keys() if (match := re.match(r'^periods-(\d+)-start_date$', key))}
    for idx in sorted(period_indices, key=int):
        start_date = periods_input.get(f'periods-{idx}-start_date')
        end_date = periods_input.get(f'periods-{idx}-end_date')
        days = periods_input.get(f'periods-{idx}-days')
        start_time_str = periods_input.get(f'periods-{idx}-start_time') or None
        end_time_str = periods_input.get(f'periods-{idx}-end_time') or None
        if start_date and end_date and days:
            try:
                days_val = Decimal(str(days))
                s_time = datetime.time.fromisoformat(start_time_str.strip()) if start_time_str else None
                e_time = datetime.time.fromisoformat(end_time_str.strip()) if end_time_str else None
                LeavePeriod.objects.create(
                    leave_request=leave_request,
                    start_date=start_date,
                    end_date=end_date,
                    start_time=s_time,
                    end_time=e_time,
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
