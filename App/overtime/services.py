from decimal import Decimal
from django.utils import timezone
from django.db.models import Sum
from activities.services import log_activity
from .models import OvertimeRequest


class OvertimeService:
    @staticmethod
    def approve_request(ot_request, user):
        """Marks an overtime request as approved, records approver and timestamp, logs activity."""
        ot_request.status = OvertimeRequest.Status.APPROVED
        ot_request.approved_by = user
        ot_request.approved_at = timezone.now()
        # Ensure hours, hourly rate, and amount are computed
        if ot_request.hours == Decimal('0.00') and ot_request.start_time and ot_request.end_time:
            ot_request.hours = ot_request.calculate_hours()
        if ot_request.hourly_rate == Decimal('0.00'):
            ot_request.hourly_rate = ot_request.calculate_hourly_rate()
        ot_request.overtime_amount = ot_request.calculate_amount()
        ot_request.save()

        log_activity(
            user=user,
            employee=ot_request.employee,
            module='OVERTIME',
            action='APPROVE',
            description=f"Approved {ot_request.hours}h OT (${ot_request.overtime_amount}) for {ot_request.date}"
        )
        return ot_request

    @staticmethod
    def reject_request(ot_request, user, reason=''):
        """Marks an overtime request as rejected with an optional reason."""
        ot_request.status = OvertimeRequest.Status.REJECTED
        ot_request.approved_by = user
        ot_request.approved_at = timezone.now()
        ot_request.rejection_reason = reason
        ot_request.save()

        log_activity(
            user=user,
            employee=ot_request.employee,
            module='OVERTIME',
            action='REJECT',
            description=f"Rejected OT for {ot_request.date}. Reason: {reason or 'N/A'}"
        )
        return ot_request

    @staticmethod
    def get_monthly_overtime_total(employee, period_start, period_end):
        """Returns total approved overtime compensation for an employee in a given date range."""
        result = OvertimeRequest.objects.filter(
            employee=employee,
            status=OvertimeRequest.Status.APPROVED,
            date__gte=period_start,
            date__lte=period_end
        ).aggregate(total=Sum('overtime_amount'))
        return result['total'] or Decimal('0.00')

    @staticmethod
    def get_monthly_overtime_hours(employee, period_start, period_end):
        """Returns total approved overtime hours for an employee in a given date range."""
        result = OvertimeRequest.objects.filter(
            employee=employee,
            status=OvertimeRequest.Status.APPROVED,
            date__gte=period_start,
            date__lte=period_end
        ).aggregate(total=Sum('hours'))
        return result['total'] or Decimal('0.00')
