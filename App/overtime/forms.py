from django import forms
from .models import OvertimeType, OvertimeRequest
from employees.models import Employee


class OvertimeTypeForm(forms.ModelForm):
    class Meta:
        model = OvertimeType
        fields = ['company', 'name', 'rate_multiplier', 'description', 'status']
        widgets = {
            'company': forms.Select(attrs={'class': 'form-select'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Weekend Overtime (2.0x)'}),
            'rate_multiplier': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'min': '1.0'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Policy description...'}),
            'status': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class AdminOvertimeRequestForm(forms.ModelForm):
    class Meta:
        model = OvertimeRequest
        fields = [
            'employee', 'overtime_type', 'date', 'start_time', 'end_time',
            'hours', 'rate_multiplier', 'hourly_rate', 'overtime_amount',
            'reason', 'status'
        ]
        widgets = {
            'employee': forms.Select(attrs={'class': 'form-select select2'}),
            'overtime_type': forms.Select(attrs={'class': 'form-select'}),
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'start_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'hours': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.25', 'min': '0'}),
            'rate_multiplier': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'min': '1.0'}),
            'hourly_rate': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'overtime_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'reason': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Reason for overtime...'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['employee'].queryset = Employee.objects.filter(status='active').select_related('department', 'position')
        self.fields['overtime_type'].queryset = OvertimeType.objects.filter(status=True)


class EmployeeOvertimeRequestForm(forms.ModelForm):
    class Meta:
        model = OvertimeRequest
        fields = ['date', 'overtime_type', 'start_time', 'end_time', 'hours', 'reason']
        widgets = {
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'overtime_type': forms.Select(attrs={'class': 'form-select'}),
            'start_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'hours': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.25', 'min': '0.25', 'placeholder': 'Optional if start/end set'}),
            'reason': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Provide justification for this overtime request...'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['overtime_type'].queryset = OvertimeType.objects.filter(status=True)
        self.fields['hours'].required = False
