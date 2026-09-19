from django import forms
from .models import SalaryStructure, Payroll, DeductionRule
from employees.models import Employee

class SalaryStructureForm(forms.ModelForm):
    class Meta:
        model = SalaryStructure
        fields = ['employee', 'basic_salary', 'transportation', 'housing', 'meal_allowance', 'other_allowance', 'effective_date', 'status']
        widgets = {
            'effective_date': forms.DateInput(attrs={'type': 'date'}),
        }

class PayrollForm(forms.ModelForm):
    class Meta:
        model = Payroll
        fields = [
            'employee', 'payroll_period', 'basic_salary', 'daily_salary', 'daily_salary_formula',
            'attendance_days', 'absent_days', 'late_hours', 'overtime_hours', 'leave_days', 'holiday_days',
            'overtime', 'allowance', 'bonus', 'gross_salary', 'tax', 'nssf', 'other_deduction',
            'total_deduction', 'net_salary', 'status'
        ]
        widgets = {
            'payroll_period': forms.DateInput(attrs={'type': 'date'}),
        }


class DeductionRuleForm(forms.ModelForm):
    class Meta:
        model = DeductionRule
        fields = [
            'company', 'name', 'category', 'condition_unit', 'operator',
            'threshold_min', 'threshold_max', 'calc_type', 'rate_or_amount',
            'priority', 'is_active', 'description'
        ]
        widgets = {
            'company': forms.Select(attrs={'class': 'form-select'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Absent Full Day Deduction'}),
            'category': forms.Select(attrs={'class': 'form-select', 'id': 'id_category'}),
            'condition_unit': forms.Select(attrs={'class': 'form-select', 'id': 'id_condition_unit'}),
            'operator': forms.Select(attrs={'class': 'form-select', 'id': 'id_operator'}),
            'threshold_min': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'Min (optional)'}),
            'threshold_max': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'Max (optional)'}),
            'calc_type': forms.Select(attrs={'class': 'form-select', 'id': 'id_calc_type'}),
            'rate_or_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'e.g. 100 for 100% or 5.00 for $5'}),
            'priority': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'value': '10'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Optional internal notes...'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        rate_or_amount = cleaned_data.get('rate_or_amount')
        threshold_min = cleaned_data.get('threshold_min')
        threshold_max = cleaned_data.get('threshold_max')
        operator = cleaned_data.get('operator')

        if rate_or_amount is not None and rate_or_amount < 0:
            self.add_error('rate_or_amount', "Rate or amount cannot be negative.")

        if operator == DeductionRule.Operator.BETWEEN:
            if threshold_min is not None and threshold_max is not None and threshold_min > threshold_max:
                self.add_error('threshold_min', "Minimum threshold cannot exceed maximum threshold.")

        return cleaned_data
