from decimal import Decimal
from django.utils import timezone
from activities.services import log_activity
from .models import LeaveRequest, LeaveBalance


class LeaveService:
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
