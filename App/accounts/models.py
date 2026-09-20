from django.contrib.auth.models import AbstractUser
from django.db import models

PERMISSION_CATALOG = {
    'attendance': {
        'name': 'Attendance & Working Hours',
        'short_name': 'Attendance',
        'icon': 'mdi-clock-check-outline',
        'permissions': [
            ('attendance.view', 'View Attendance Logs', 'View daily attendance records, punch times, and late/early logs'),
            ('attendance.record', 'Check-in / Check-out', 'Perform daily attendance clock-in and clock-out'),
            ('attendance.bulk', 'Bulk Record Attendance', 'Create and import attendance records in bulk'),
            ('attendance.schedules', 'Manage Work Schedules', 'Configure work shifts, times, and weekly employee schedules'),
            ('attendance.breaks', 'Manage Lunch Breaks', 'Configure lunch break windows and auto-deduction settings'),
            ('attendance.export', 'Export Attendance', 'Download attendance reports in Excel and PDF formats'),
        ]
    },
    'employees': {
        'name': 'Employees & Organization',
        'short_name': 'Employees',
        'icon': 'mdi-account-multiple-outline',
        'permissions': [
            ('employees.view', 'View Employees', 'Browse staff directory, view personal profiles and job details'),
            ('employees.create', 'Add Employee', 'Register new employee profiles and employment terms'),
            ('employees.edit', 'Edit Employee', 'Modify employee information, salary, photo, and job role'),
            ('employees.delete', 'Delete / Terminate Employee', 'Mark employee as inactive, resigned, or terminated'),
            ('employees.positions', 'Manage Positions', 'Create, update, and manage job titles and designations'),
            ('employees.departments', 'Manage Departments', 'Create and maintain corporate departments'),
            ('employees.branches', 'Manage Branches', 'Configure physical branches and office locations'),
            ('employees.export', 'Export Directory', 'Export employee lists and rosters to Excel and PDF'),
        ]
    },
    'leave': {
        'name': 'Leave Management',
        'short_name': 'Leave',
        'icon': 'mdi-calendar-check-outline',
        'permissions': [
            ('leave.view', 'View Leave Requests', 'See personal and departmental leave requests and balances'),
            ('leave.apply', 'Apply / Request Leave', 'Submit new leave applications'),
            ('leave.approve', 'Approve / Reject Leave', 'Authorize or deny pending leave applications'),
            ('leave.types', 'Manage Leave Types', 'Configure annual leave types, paid rules, and default quotas'),
            ('leave.balances', 'Manage Balances', 'Adjust employee annual leave quotas and balance allowances'),
        ]
    },
    'overtime': {
        'name': 'Overtime & Rates',
        'short_name': 'Overtime',
        'icon': 'mdi-clock-fast',
        'permissions': [
            ('overtime.view', 'View Overtime Records', 'Browse overtime logs and approval statuses'),
            ('overtime.create', 'Submit / Log Overtime', 'Record employee overtime hours'),
            ('overtime.approve', 'Approve / Reject Overtime', 'Review and approve overtime requests'),
            ('overtime.edit', 'Edit Overtime', 'Modify logged hours, dates, and overtime types'),
            ('overtime.delete', 'Delete Overtime', 'Remove overtime records from the system'),
            ('overtime.types', 'Manage Overtime Types', 'Define overtime multipliers (1.5x Normal, 2.0x Weekend, 3.0x Holiday)'),
            ('overtime.export', 'Export Overtime', 'Export overtime calculation summaries to Excel and PDF'),
        ]
    },
    'payroll': {
        'name': 'Salary & Payroll Processing',
        'short_name': 'Payroll',
        'icon': 'mdi-cash-multiple',
        'permissions': [
            ('payroll.view', 'View Payroll & Payslips', 'Inspect payroll batches, summary figures, and payslips'),
            ('payroll.setup', 'Salary Structure Setup', 'Configure basic salaries, daily/hourly rates per employee'),
            ('payroll.allowances', 'Manage Allowances', 'Set up recurring travel, food, and accommodation allowances'),
            ('payroll.bonuses', 'Manage Bonuses & Incentives', 'Assign performance and one-time bonuses'),
            ('payroll.deductions', 'Manage Deduction Rules', 'Configure tax, NSSF, and late penalty deduction formulas'),
            ('payroll.run', 'Generate & Run Payroll', 'Calculate monthly gross, deductions, and finalize net pay'),
            ('payroll.export', 'Export Payroll Reports', 'Export payroll summaries and payslips to Excel and PDF'),
        ]
    },
    'reports': {
        'name': 'Reports & Analytics',
        'short_name': 'Reports',
        'icon': 'mdi-chart-box-outline',
        'permissions': [
            ('reports.daily', 'Daily Attendance Report', 'View and export daily department attendance reports'),
            ('reports.summary', 'Monthly Summary Report', 'View and export monthly aggregated payroll/attendance summaries'),
            ('reports.detail', 'Employee Detail Report', 'View and export individual employee full timecard reports'),
        ]
    },
    'dashboard': {
        'name': 'Dashboard & Overview',
        'short_name': 'Dashboard',
        'icon': 'mdi-grid-large',
        'permissions': [
            ('dashboard.view', 'Access Executive Dashboard', 'View organization KPI cards, present/late metrics, and quick operations'),
        ]
    },
    'activities': {
        'name': 'System Audit Trail',
        'short_name': 'Audit Logs',
        'icon': 'mdi-history',
        'permissions': [
            ('activities.view', 'View Activity Stream', 'Browse and filter system activity and audit logs'),
        ]
    },
    'users': {
        'name': 'Users & Access Roles (RBAC)',
        'short_name': 'Users & RBAC',
        'icon': 'mdi-shield-account-outline',
        'permissions': [
            ('users.manage', 'Manage Users & Roles', 'Create logins, reset passwords, and manage RBAC access roles'),
        ]
    }
}


class Role(models.Model):
    SYSTEM_ROLES = ['super_admin', 'hr_admin', 'manager', 'employee']

    MODULE_CHOICES = [
        ('dashboard', 'Dashboard & Analytics'),
        ('employees', 'Employees & Organization Setup'),
        ('attendance', 'Attendance Records, Schedules & Lunch Breaks'),
        ('leave', 'Leave Requests & Policies'),
        ('overtime', 'Overtime Records & Rates'),
        ('payroll', 'Salary Setup & Payroll Processing'),
        ('reports', 'Reports & PDF/Excel Exports'),
        ('activities', 'System Activity Logs'),
        ('users', 'User & Access Role (RBAC) Management'),
    ]

    name = models.CharField(max_length=60, unique=True)
    code = models.SlugField(max_length=50, unique=True, help_text="Unique role code (e.g. hr_specialist)")
    description = models.TextField(blank=True)
    is_system = models.BooleanField(default=False, help_text="System roles cannot be deleted or have their code altered.")
    permissions = models.JSONField(default=list, blank=True, help_text="List of permitted module keys and granular permission codes")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_system', 'name']

    def __str__(self):
        return f"{self.name} ({self.code})"

    def has_permission(self, perm_key):
        if self.code == 'super_admin':
            return True
        perms = self.permissions or []
        if perm_key in perms:
            return True
        module_key = perm_key.split('.')[0]
        if module_key in perms:
            return True
        if '.' not in perm_key:
            return any(p.startswith(f"{perm_key}.") for p in perms)
        return False

    @property
    def user_count(self):
        from django.contrib.auth import get_user_model
        return get_user_model().objects.filter(role=self.code).count()

    def get_module_permission_summary(self):
        """Returns list of tuples (module_key, module_name, icon, granted_count, total_count)"""
        summary = []
        perms = set(self.permissions or [])
        for mod_key, mod_info in PERMISSION_CATALOG.items():
            total = len(mod_info['permissions'])
            if self.code == 'super_admin' or mod_key in perms:
                granted = total
            else:
                granted = sum(1 for p_key, _, _ in mod_info['permissions'] if p_key in perms)
            if granted > 0:
                summary.append({
                    'key': mod_key,
                    'name': mod_info['name'],
                    'short_name': mod_info.get('short_name', mod_info['name']),
                    'icon': mod_info['icon'],
                    'granted': granted,
                    'total': total,
                    'is_full': granted == total
                })
        return summary


class User(AbstractUser):
    class Role(models.TextChoices):
        SUPER_ADMIN = 'super_admin', 'Super Admin'
        HR_ADMIN = 'hr_admin', 'HR Admin'
        MANAGER = 'manager', 'Manager'
        EMPLOYEE = 'employee', 'Employee'

    role = models.CharField(max_length=50, default=Role.EMPLOYEE)
    phone = models.CharField(max_length=20, blank=True)

    @property
    def role_obj(self):
        return Role.objects.filter(code=self.role).first()

    def get_role_display(self):
        obj = self.role_obj
        if obj:
            return obj.name
        for val, label in self.Role.choices:
            if val == self.role:
                return label
        return self.role.replace('_', ' ').title()

    def has_permission(self, perm_key):
        if self.is_superuser or self.role == self.Role.SUPER_ADMIN:
            return True
        r = self.role_obj
        if r:
            return r.has_permission(perm_key)
        module_key = perm_key.split('.')[0]
        return self.has_module_access(module_key)

    def has_module_access(self, module_key):
        if self.is_superuser or self.role == self.Role.SUPER_ADMIN:
            return True
        r = self.role_obj
        if r:
            return r.has_permission(module_key)
        if self.role == self.Role.HR_ADMIN:
            return module_key in ['dashboard', 'employees', 'attendance', 'leave', 'overtime', 'payroll', 'reports', 'activities']
        if self.role == self.Role.MANAGER:
            return module_key in ['dashboard', 'attendance', 'leave', 'employees']
        if self.role == self.Role.EMPLOYEE:
            return module_key in ['dashboard', 'attendance', 'leave', 'overtime', 'payroll']
        return False

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"
