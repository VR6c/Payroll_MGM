import re
import datetime
import logging
from decimal import Decimal
from django.utils import timezone
from activities.services import log_activity
from .models import LeaveRequest, LeaveBalance, LeavePeriod

logger = logging.getLogger('leave')


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

    # 1. Intra-request overlap check
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

    # 2. Database collision check
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


def create_leave_periods(leave_request, periods_input):
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
            except Exception as e:
                logger.debug(f"Failed to create leave period for idx {idx}: {e}")
                continue


_create_leave_periods = create_leave_periods


class LeaveService:
    check_periods_overlap = staticmethod(check_periods_overlap)
    parse_and_validate_leave_periods = staticmethod(parse_and_validate_leave_periods)
    create_leave_periods = staticmethod(create_leave_periods)

    @staticmethod
    def approve_request(leave_request, user):
        """Marks a leave request as approved, records approver and timestamp, updates balance, and logs activity."""
        leave_request.status = LeaveRequest.Status.APPROVED
        leave_request.approved_by = user
        leave_request.approved_at = timezone.now()
        leave_request.save(update_fields=['status', 'approved_by', 'approved_at'])

        # Update leave balance if tracked
        current_year = leave_request.created_at.year if leave_request.created_at else timezone.now().year
        balance = LeaveBalance.objects.filter(
            employee=leave_request.employee,
            leave_type=leave_request.leave_type,
            year=current_year
        ).first()
        if balance:
            used = Decimal(str(balance.used_days or 0)) + Decimal(str(leave_request.total_days or 0))
            allocated = Decimal(str(balance.allocated_days or 0))
            balance.used_days = used
            balance.remaining_days = max(Decimal('0'), allocated - used)
            balance.save(update_fields=['used_days', 'remaining_days'])
        elif leave_request.leave_type and leave_request.leave_type.default_days:
            allocated = Decimal(str(leave_request.leave_type.default_days))
            used = Decimal(str(leave_request.total_days or 0))
            LeaveBalance.objects.create(
                employee=leave_request.employee,
                leave_type=leave_request.leave_type,
                year=current_year,
                allocated_days=allocated,
                used_days=used,
                remaining_days=max(Decimal('0'), allocated - used)
            )

        log_activity(
            user=user,
            employee=leave_request.employee,
            module='LEAVE',
            action='APPROVE',
            description=f"Approved leave request #{leave_request.pk} ({leave_request.total_days} days {leave_request.leave_type.name}) for {leave_request.employee}"
        )
        return leave_request

    @staticmethod
    def reject_request(leave_request, user):
        """Marks a leave request as rejected, records approver and timestamp, and logs activity."""
        leave_request.status = LeaveRequest.Status.REJECTED
        leave_request.approved_by = user
        leave_request.approved_at = timezone.now()
        leave_request.save(update_fields=['status', 'approved_by', 'approved_at'])

        log_activity(
            user=user,
            employee=leave_request.employee,
            module='LEAVE',
            action='REJECT',
            description=f"Rejected leave request #{leave_request.pk} for {leave_request.employee}"
        )
        return leave_request

    @staticmethod
    def cancel_request(leave_request, user):
        """Marks a pending leave request as cancelled by the requester, and logs activity."""
        if leave_request.status != LeaveRequest.Status.PENDING:
            return leave_request

        leave_request.status = LeaveRequest.Status.CANCELLED
        leave_request.save(update_fields=['status'])

        log_activity(
            user=user,
            employee=leave_request.employee,
            module='LEAVE',
            action='CANCEL',
            description=f"Cancelled leave request #{leave_request.pk} for {leave_request.employee}"
        )
        return leave_request

    @staticmethod
    def delete_request(leave_request, user):
        """Deletes a leave request, restores leave balance if it was approved, and logs activity."""
        emp = leave_request.employee
        total_days = Decimal(str(leave_request.total_days or 0))
        status = leave_request.status
        leave_type = leave_request.leave_type

        # Revert leave balance if was approved
        if status == LeaveRequest.Status.APPROVED and leave_type:
            current_year = leave_request.created_at.year if leave_request.created_at else timezone.now().year
            balance = LeaveBalance.objects.filter(
                employee=emp,
                leave_type=leave_type,
                year=current_year
            ).first()
            if balance:
                used = max(Decimal('0'), Decimal(str(balance.used_days or 0)) - total_days)
                allocated = Decimal(str(balance.allocated_days or 0))
                balance.used_days = used
                balance.remaining_days = max(Decimal('0'), allocated - used)
                balance.save(update_fields=['used_days', 'remaining_days'])

        log_activity(
            user=user,
            employee=emp,
            module='LEAVE',
            action='DELETE',
            description=f"Deleted leave request #{leave_request.pk} ({total_days} days {leave_type.name if leave_type else ''}) for {emp}"
        )
        leave_request.delete()

    @staticmethod
    def adjust_balance_on_update(old_snapshot, updated_leave):
        """Synchronizes leave balance when an existing request is updated."""
        current_year = timezone.now().year

        # Revert old balance if old status was approved
        if old_snapshot.get('status') == LeaveRequest.Status.APPROVED and old_snapshot.get('leave_type_id'):
            old_balance = LeaveBalance.objects.filter(
                employee_id=old_snapshot.get('employee_id'),
                leave_type_id=old_snapshot.get('leave_type_id'),
                year=current_year
            ).first()
            if old_balance:
                used = max(Decimal('0'), Decimal(str(old_balance.used_days or 0)) - Decimal(str(old_snapshot.get('total_days') or 0)))
                old_balance.used_days = used
                old_balance.remaining_days = max(Decimal('0'), Decimal(str(old_balance.allocated_days or 0)) - used)
                old_balance.save(update_fields=['used_days', 'remaining_days'])

        # Apply new balance if new status is approved
        if updated_leave.status == LeaveRequest.Status.APPROVED and updated_leave.leave_type:
            new_balance = LeaveBalance.objects.filter(
                employee=updated_leave.employee,
                leave_type=updated_leave.leave_type,
                year=current_year
            ).first()
            if new_balance:
                used = Decimal(str(new_balance.used_days or 0)) + Decimal(str(updated_leave.total_days or 0))
                new_balance.used_days = used
                new_balance.remaining_days = max(Decimal('0'), Decimal(str(new_balance.allocated_days or 0)) - used)
                new_balance.save(update_fields=['used_days', 'remaining_days'])
            elif updated_leave.leave_type.default_days:
                allocated = Decimal(str(updated_leave.leave_type.default_days))
                used = Decimal(str(updated_leave.total_days or 0))
                LeaveBalance.objects.create(
                    employee=updated_leave.employee,
                    leave_type=updated_leave.leave_type,
                    year=current_year,
                    allocated_days=allocated,
                    used_days=used,
                    remaining_days=max(Decimal('0'), allocated - used)
                )
