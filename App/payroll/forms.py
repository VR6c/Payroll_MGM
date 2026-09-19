from django import forms
from .models import SalaryStructure, Payroll
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
