from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils.text import slugify
from employees.models import Employee
from .models import Role, PERMISSION_CATALOG

User = get_user_model()


class RoleForm(forms.ModelForm):
    class Meta:
        model = Role
        fields = ['name', 'code', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Payroll Specialist'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. payroll_specialist'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Describe duties and scope of access...'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.is_system:
            self.fields['code'].disabled = True
            self.fields['code'].help_text = "Core system role identifier cannot be modified."

    def clean_name(self):
        name = self.cleaned_data.get('name', '').strip()
        qs = Role.objects.filter(name__iexact=name)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError("A role with this name already exists.")
        return name

    def clean_code(self):
        if self.instance and self.instance.pk and self.instance.is_system:
            return self.instance.code
        code = self.cleaned_data.get('code', '').strip()
        if not code:
            name = self.cleaned_data.get('name', '')
            code = slugify(name).replace('-', '_')
        code = slugify(code).replace('-', '_')
        qs = Role.objects.filter(code__iexact=code)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError("A role with this code already exists.")
        return code

    def save(self, commit=True):
        role = super().save(commit=False)
        # Capture granular permissions from POST data
        if hasattr(self, 'data'):
            perms = self.data.getlist('permissions')
            if role.code == 'super_admin':
                all_perms = []
                for mod_info in PERMISSION_CATALOG.values():
                    all_perms.extend([p[0] for p in mod_info['permissions']])
                role.permissions = all_perms
            else:
                role.permissions = list(set(perms))
        if commit:
            role.save()
        return role


class UserCreateForm(forms.ModelForm):
    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Minimum 6 characters'}),
        min_length=6,
        help_text="At least 6 characters."
    )
    confirm_password = forms.CharField(
        label="Confirm Password",
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Re-enter password'}),
        min_length=6
    )
    employee = forms.ModelChoiceField(
        queryset=Employee.objects.none(),
        required=False,
        empty_label="-- No Linked Employee (Standalone Account) --",
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text="Optionally link this login to an employee profile."
    )

    class Meta:
        model = User
        fields = [
            'username', 'first_name', 'last_name', 'email',
            'phone', 'role', 'is_active'
        ]
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. john.doe'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First name'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last name'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'user@example.com'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+855 ...'}),
            'role': forms.Select(attrs={'class': 'form-select'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['employee'].queryset = Employee.objects.filter(user__isnull=True).order_by('first_name', 'last_name')
        self.fields['is_active'].initial = True

        # Dynamically load choices from Role table
        roles = Role.objects.all()
        if roles.exists():
            self.fields['role'].choices = [(r.code, r.name) for r in roles]

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError("A user with this username already exists.")
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email and User.objects.filter(email__iexact=email).exists():
            raise ValidationError("A user with this email address already exists.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get('password')
        p2 = cleaned_data.get('confirm_password')
        if p1 and p2 and p1 != p2:
            self.add_error('confirm_password', "Passwords do not match.")
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])
        if user.role == 'super_admin':
            user.is_staff = True
            user.is_superuser = True
        elif user.role == 'hr_admin':
            user.is_staff = True
            user.is_superuser = False
        else:
            user.is_superuser = False

        if commit:
            user.save()
            selected_employee = self.cleaned_data.get('employee')
            if selected_employee:
                selected_employee.user = user
                if not user.first_name and selected_employee.first_name:
                    user.first_name = selected_employee.first_name
                if not user.last_name and selected_employee.last_name:
                    user.last_name = selected_employee.last_name
                if not user.email and selected_employee.email:
                    user.email = selected_employee.email
                user.save()
                selected_employee.save()
        return user


class UserUpdateForm(forms.ModelForm):
    employee = forms.ModelChoiceField(
        queryset=Employee.objects.none(),
        required=False,
        empty_label="-- No Linked Employee (Standalone Account) --",
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text="Link or unlink an employee profile."
    )

    class Meta:
        model = User
        fields = [
            'username', 'first_name', 'last_name', 'email',
            'phone', 'role', 'is_active'
        ]
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'role': forms.Select(attrs={'class': 'form-select'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        current_emp = getattr(self.instance, 'employee_profile', None)
        emp_filter = Q(user__isnull=True)
        if current_emp:
            emp_filter |= Q(pk=current_emp.pk)
            self.fields['employee'].initial = current_emp

        self.fields['employee'].queryset = Employee.objects.filter(emp_filter).order_by('first_name', 'last_name')

        # Dynamically load choices from Role table
        roles = Role.objects.all()
        if roles.exists():
            self.fields['role'].choices = [(r.code, r.name) for r in roles]

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username__iexact=username).exclude(pk=self.instance.pk).exists():
            raise ValidationError("A user with this username already exists.")
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email and User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise ValidationError("A user with this email address already exists.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        new_role = cleaned_data.get('role')
        is_active = cleaned_data.get('is_active')

        if self.instance.pk:
            is_currently_super_admin = (self.instance.role == 'super_admin' or self.instance.is_superuser)
            if is_currently_super_admin:
                super_admin_count = User.objects.filter(
                    Q(role='super_admin') | Q(is_superuser=True),
                    is_active=True
                ).exclude(pk=self.instance.pk).count()

                if super_admin_count == 0:
                    if new_role != 'super_admin':
                        self.add_error('role', "Cannot change role. At least one active Super Admin must exist in the system.")
                    if not is_active:
                        self.add_error('is_active', "Cannot deactivate the only active Super Admin.")

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        if user.role == 'super_admin':
            user.is_staff = True
            user.is_superuser = True
        elif user.role == 'hr_admin':
            user.is_staff = True
            user.is_superuser = False
        else:
            user.is_superuser = False

        if commit:
            user.save()
            new_employee = self.cleaned_data.get('employee')
            current_employee = getattr(user, 'employee_profile', None)

            if current_employee and current_employee != new_employee:
                current_employee.user = None
                current_employee.save()

            if new_employee:
                new_employee.user = user
                new_employee.save()

        return user


class UserAdminPasswordResetForm(forms.Form):
    new_password = forms.CharField(
        label="New Password",
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Minimum 6 characters'}),
        min_length=6
    )
    confirm_password = forms.CharField(
        label="Confirm New Password",
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Re-enter new password'}),
        min_length=6
    )

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get('new_password')
        p2 = cleaned_data.get('confirm_password')
        if p1 and p2 and p1 != p2:
            self.add_error('confirm_password', "Passwords do not match.")
        return cleaned_data

    def save(self, user):
        user.set_password(self.cleaned_data['new_password'])
        user.save()
        return user
