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
    unpaid_leave_days = models.DecimalField(max_digits=5, decimal_places=1, default=Decimal('0.0'))
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


class DeductionRule(models.Model):
    class Category(models.TextChoices):
        ABSENT = 'absent', 'Absent'
        UNPAID_LEAVE = 'unpaid_leave', 'Leave Unpaid'
        LATE = 'late', 'Late'
        EARLY_LEAVE = 'early_leave', 'Early Leave'
        CUSTOM = 'custom', 'Custom / Other'

    class ConditionUnit(models.TextChoices):
        DAYS = 'days', 'Days'
        HOURS = 'hours', 'Hours'
        TIMES = 'times', 'Times (Occurrences)'

    class Operator(models.TextChoices):
        ALWAYS = 'always', 'Per Unit (Always Apply)'
        LTE = 'lte', '≤ Less than or equal to'
        LT = 'lt', '< Less than'
        GTE = 'gte', '≥ Greater than or equal to'
        GT = 'gt', '> Greater than'
        BETWEEN = 'between', 'Between'
        EQ = 'eq', '= Equal to'

    class CalcType(models.TextChoices):
        PERCENT_DAILY = 'percent_daily', '% of Salary / Day'
        PERCENT_HOURLY = 'percent_hourly', '% of Salary / Hour'
        PERCENT_MONTHLY = 'percent_monthly', '% of Monthly Salary'
        FIXED_PER_UNIT = 'fixed_per_unit', 'Fixed Amount per Unit ($)'
        FIXED_FLAT = 'fixed_flat', 'Fixed Flat Amount ($)'

    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='deduction_rules')
    name = models.CharField(max_length=150)
    category = models.CharField(max_length=30, choices=Category.choices)
    condition_unit = models.CharField(max_length=20, choices=ConditionUnit.choices, default=ConditionUnit.DAYS)
    operator = models.CharField(max_length=20, choices=Operator.choices, default=Operator.ALWAYS)
    threshold_min = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    threshold_max = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)

    calc_type = models.CharField(max_length=30, choices=CalcType.choices)
    rate_or_amount = models.DecimalField(max_digits=10, decimal_places=2, help_text="Percentage (e.g. 100 for 100%) or Fixed dollar amount")

    priority = models.PositiveIntegerField(default=10, help_text="Lower number = higher priority")
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['category', 'priority', 'id']

    def __str__(self):
        return f"{self.name} ({self.get_category_display()})"


class PayrollDeductionItem(models.Model):
    payroll = models.ForeignKey(Payroll, on_delete=models.CASCADE, related_name='deduction_items')
    rule = models.ForeignKey(DeductionRule, on_delete=models.SET_NULL, null=True, blank=True, related_name='applied_items')
    category = models.CharField(max_length=30)
    name = models.CharField(max_length=150)
    condition_unit = models.CharField(max_length=20, default='days')
    quantity = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'))
    unit_rate = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    rate_or_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    calculated_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f"{self.name}: -${self.calculated_amount}"

