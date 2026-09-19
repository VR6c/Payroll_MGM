from decimal import Decimal
from django.db import models
from employees.models import Employee

class SalaryStructure(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='salary_structures')
    basic_salary = models.DecimalField(max_digits=12, decimal_places=2)
    transportation = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    housing = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    meal_allowance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    other_allowance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    effective_date = models.DateField()
    status = models.BooleanField(default=True)

    class Meta:
        ordering = ['-effective_date']
        indexes = [
            models.Index(fields=['employee', 'status']),
        ]

class Payroll(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        PROCESSING = 'processing', 'Processing'
        APPROVED = 'approved', 'Approved'
        PAID = 'paid', 'Paid'
        CANCELLED = 'cancelled', 'Cancelled'

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='payrolls')
    payroll_period = models.DateField()
    basic_salary = models.DecimalField(max_digits=12, decimal_places=2)
    overtime = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    allowance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    bonus = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    gross_salary = models.DecimalField(max_digits=12, decimal_places=2)
    tax = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    nssf = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    other_deduction = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_deduction = models.DecimalField(max_digits=12, decimal_places=2)
    net_salary = models.DecimalField(max_digits=12, decimal_places=2)
    daily_salary = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    daily_salary_formula = models.CharField(max_length=150, blank=True, default='')
    attendance_days = models.DecimalField(max_digits=5, decimal_places=1, default=Decimal('0.0'))
    absent_days = models.DecimalField(max_digits=5, decimal_places=1, default=Decimal('0.0'))
    late_hours = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('0.00'))
    overtime_hours = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('0.00'))
    leave_days = models.DecimalField(max_digits=5, decimal_places=1, default=Decimal('0.0'))
    holiday_days = models.DecimalField(max_digits=5, decimal_places=1, default=Decimal('0.0'))
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('employee', 'payroll_period')
        indexes = [
            models.Index(fields=['payroll_period']),
            models.Index(fields=['status']),
            models.Index(fields=['employee', 'payroll_period']),
        ]

