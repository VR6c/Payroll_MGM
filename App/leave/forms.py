from django import forms
from employees.models import Employee
from .models import LeaveRequest, LeaveType, LeaveBalance


class LeaveRequestForm(forms.ModelForm):
    employee = forms.ModelChoiceField(
        queryset=Employee.objects.filter(status='active').select_related('department', 'position'),
        widget=forms.Select(attrs={'class': 'form-select select2', 'id': 'id_employee'}),
        required=False,
        label="Employee",
        help_text="Select employee requesting leave"
    )
    status = forms.ChoiceField(
        choices=[
            (LeaveRequest.Status.PENDING, 'Pending Review'),
            (LeaveRequest.Status.APPROVED, 'Approved (Direct Approval)'),
            (LeaveRequest.Status.REJECTED, 'Rejected'),
        ],
        required=False,
        initial=LeaveRequest.Status.PENDING,
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_status'}),
        label="Approval Status",
        help_text="Directly approve, reject, or keep as pending review"
    )

    class Meta:
        model = LeaveRequest
        fields = ['employee', 'leave_type', 'status', 'reason']
        widgets = {
            'leave_type': forms.Select(attrs={'class': 'form-select select2', 'id': 'id_leave_type'}),
            'reason': forms.Textarea(attrs={'rows': 3, 'class': 'form-control', 'id': 'id_reason', 'placeholder': 'Provide detailed reason for leave...'}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        is_admin_or_mgr = user and (user.role in ['super_admin', 'hr_admin', 'manager'] or user.is_superuser)
        if is_admin_or_mgr:
            if 'employee' in self.fields:
                self.fields['employee'].required = True
                self.fields['employee'].queryset = Employee.objects.filter(status='active').select_related('department', 'position')
                if hasattr(user, 'employee_profile') and user.employee_profile:
                    self.fields['employee'].initial = user.employee_profile
            if 'status' in self.fields:
                self.fields['status'].required = True
        else:
            if 'employee' in self.fields:
                del self.fields['employee']
            if 'status' in self.fields:
                del self.fields['status']

        if 'leave_type' in self.fields:
            self.fields['leave_type'].queryset = LeaveType.objects.filter(status=True)


class LeaveTypeForm(forms.ModelForm):
    class Meta:
        model = LeaveType
        fields = ['company', 'name', 'default_days', 'paid', 'status']


class LeaveBalanceForm(forms.ModelForm):
    class Meta:
        model = LeaveBalance
        fields = ['employee', 'leave_type', 'year', 'allocated_days', 'used_days', 'remaining_days']
