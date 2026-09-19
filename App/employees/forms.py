from django import forms
from .models import Employee

class EmployeeForm(forms.ModelForm):
    class Meta:
        model = Employee
        fields = [
            'employee_code', 'first_name', 'last_name', 'gender', 'date_of_birth',
            'phone', 'email', 'address', 'photo', 'department', 'position',
            'manager', 'join_date', 'basic_salary', 'status'
        ]
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'join_date': forms.DateInput(attrs={'type': 'date'}),
            'address': forms.Textarea(attrs={'rows': 3}),
        }

class EmployeeFilterForm(forms.Form):
    search = forms.CharField(required=False, widget=forms.TextInput(attrs={'placeholder': 'Search name or code...'}))
    department = forms.ModelChoiceField(queryset=None, required=False, empty_label="All Departments")
    status = forms.ChoiceField(choices=[('', 'All Status')] + Employee.Status.choices, required=False)

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        from companies.models import Department
        if company:
            self.fields['department'].queryset = Department.objects.filter(company=company, status=True)
        else:
            self.fields['department'].queryset = Department.objects.filter(status=True)

from companies.models import Department, Position

class DepartmentForm(forms.ModelForm):
    class Meta:
        model = Department
        fields = ['company', 'name', 'description', 'status']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 2}),
        }

class PositionForm(forms.ModelForm):
    class Meta:
        model = Position
        fields = ['company', 'department', 'name', 'description', 'status']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 2}),
        }




