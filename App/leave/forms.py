from django import forms
from .models import LeaveRequest, LeaveType, LeaveBalance

class LeaveRequestForm(forms.ModelForm):
    class Meta:
        model = LeaveRequest
        fields = ['leave_type', 'reason']
        widgets = {'reason': forms.Textarea(attrs={'rows': 3})}

class LeaveTypeForm(forms.ModelForm):
    class Meta:
        model = LeaveType
        fields = ['company', 'name', 'default_days', 'paid', 'status']

class LeaveBalanceForm(forms.ModelForm):
    class Meta:
        model = LeaveBalance
        fields = ['employee', 'leave_type', 'year', 'allocated_days', 'used_days', 'remaining_days']

