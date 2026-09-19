from django.core.management.base import BaseCommand
from django.utils import timezone
from leave.models import LeaveBalance, LeaveType
from employees.models import Employee
from decimal import Decimal

class Command(BaseCommand):
    help = 'Accrue monthly leave balances for all active employees'

    def handle(self, *args, **options):
        today = timezone.localdate()
        year = today.year
        leave_types = LeaveType.objects.filter(status=True, default_days__gt=0)
        accrued_count = 0
        for lt in leave_types:
            monthly_accrual = Decimal(lt.default_days) / Decimal(12)
            balances = LeaveBalance.objects.filter(
                leave_type=lt, year=year, employee__status='active'
            ).select_related('employee')
            for balance in balances:
                if balance.employee.join_date <= today.replace(day=1):
                    balance.allocated_days += monthly_accrual
                    balance.remaining_days = balance.allocated_days - balance.used_days
                    balance.save(update_fields=['allocated_days', 'remaining_days'])
                    accrued_count += 1
        self.stdout.write(self.style.SUCCESS(f'Accrued leave for {accrued_count} records'))
