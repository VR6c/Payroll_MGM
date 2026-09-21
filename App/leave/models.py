from decimal import Decimal
from typing import Any
from django.db import models
from employees.models import Employee

class LeaveType(models.Model):
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    default_days = models.IntegerField(default=0)
    paid = models.BooleanField(default=True)
    status = models.BooleanField(default=True)

    objects = models.Manager()

    def __str__(self):
        return self.name

class LeaveRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'
        CANCELLED = 'cancelled', 'Cancelled'

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='leave_requests')
    leave_type = models.ForeignKey(LeaveType, on_delete=models.CASCADE)
    reason = models.TextField()
    total_days: Any = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    approved_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = models.Manager()

    def save(self, *args: Any, **kwargs: Any) -> None:
        if self.pk and hasattr(self, 'periods') and self.periods.exists():
            self.total_days = sum((p.days for p in self.periods.all()), Decimal('0'))
        super().save(*args, **kwargs)

class LeavePeriod(models.Model):
    leave_request = models.ForeignKey(LeaveRequest, on_delete=models.CASCADE, related_name='periods')
    start_date = models.DateField()
    end_date = models.DateField()
    days = models.DecimalField(max_digits=6, decimal_places=2)

    objects = models.Manager()

class LeaveBalance(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='leave_balances')
    leave_type = models.ForeignKey(LeaveType, on_delete=models.CASCADE)
    year = models.IntegerField()
    allocated_days = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    used_days = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    remaining_days = models.DecimalField(max_digits=6, decimal_places=2, default=0)

    objects = models.Manager()

    class Meta:
        unique_together = ('employee', 'leave_type', 'year')

