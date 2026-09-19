from decimal import Decimal, ROUND_HALF_UP
import datetime
from django.db import models
from django.utils import timezone
from employees.models import Employee
from config.rules import get_rule


class OvertimeType(models.Model):
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='overtime_types')
    name = models.CharField(max_length=100)
    rate_multiplier = models.DecimalField(max_digits=4, decimal_places=2, default=Decimal('1.50'))
    description = models.TextField(blank=True)
    status = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.rate_multiplier}x)"


class OvertimeRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'
        CANCELLED = 'cancelled', 'Cancelled'

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='overtime_requests')
    overtime_type = models.ForeignKey(OvertimeType, on_delete=models.SET_NULL, null=True, blank=True, related_name='requests')
    date = models.DateField()
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    hours = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('0.00'))
    rate_multiplier = models.DecimalField(max_digits=4, decimal_places=2, default=Decimal('1.50'))
    hourly_rate = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    overtime_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    reason = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    approved_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_overtimes')
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-created_at']
        indexes = [
            models.Index(fields=['date', 'status']),
            models.Index(fields=['employee', 'date']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"{self.employee} - {self.date} ({self.hours} hrs) [{self.get_status_display()}]"

    def calculate_hours(self):
        """Calculates decimal hours from start_time and end_time."""
        if not self.start_time or not self.end_time:
            return self.hours or Decimal('0.00')

        t1 = datetime.datetime.combine(datetime.date.today(), self.start_time)
        t2 = datetime.datetime.combine(datetime.date.today(), self.end_time)

        if t2 < t1:
            # Shift spans midnight
            t2 += datetime.timedelta(days=1)

        diff_seconds = (t2 - t1).total_seconds()
        computed_hours = Decimal(str(diff_seconds / 3600.0)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        return computed_hours

    def calculate_hourly_rate(self):
        """Determines hourly wage from employee salary structure or basic salary."""
        basic_sal = Decimal('0.00')
        if hasattr(self.employee, 'salary_structures'):
            struct = self.employee.salary_structures.filter(status=True).order_by('-effective_date').first()
            if struct:
                basic_sal = struct.basic_salary
        if basic_sal == Decimal('0.00') and self.employee.basic_salary:
            basic_sal = self.employee.basic_salary

        # Default standard monthly work hours: 22 workdays * 8 hours = 176 hours
        std_daily_hours = get_rule('attendance', 'standard_work_hours_per_day', Decimal('8.0'))
        std_monthly_hours = Decimal('22.0') * std_daily_hours
        if std_monthly_hours > 0:
            rate = (basic_sal / std_monthly_hours).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            return rate
        return Decimal('0.00')

    def calculate_amount(self):
        """Calculates total overtime compensation: hours * hourly_rate * rate_multiplier."""
        h = self.hours or Decimal('0.00')
        hr = self.hourly_rate or Decimal('0.00')
        rm = self.rate_multiplier or Decimal('1.50')
        return (h * hr * rm).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    def save(self, *args, **kwargs):
        # Synchronize multiplier from overtime type if set and default multiplier is used
        if self.overtime_type and self.rate_multiplier == Decimal('1.50'):
            self.rate_multiplier = self.overtime_type.rate_multiplier

        # Auto-compute hours if 0 and start/end times exist
        if (self.hours is None or self.hours == Decimal('0.00')) and self.start_time and self.end_time:
            self.hours = self.calculate_hours()

        # Auto-compute hourly rate if not provided or zero
        if self.hourly_rate is None or self.hourly_rate == Decimal('0.00'):
            self.hourly_rate = self.calculate_hourly_rate()

        # Compute total overtime amount
        if self.overtime_amount is None or self.overtime_amount == Decimal('0.00') or kwargs.get('force_recalc', False):
            self.overtime_amount = self.calculate_amount()

        if 'force_recalc' in kwargs:
            kwargs.pop('force_recalc')

        super().save(*args, **kwargs)
