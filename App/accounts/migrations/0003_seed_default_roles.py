from django.db import migrations


def seed_default_roles(apps, schema_editor):
    Role = apps.get_model('accounts', 'Role')

    default_roles = [
        {
            'name': 'Super Admin',
            'code': 'super_admin',
            'description': 'Full and unrestricted access to all modules, system configurations, audit logs, and user access management.',
            'is_system': True,
            'permissions': [
                'dashboard', 'employees', 'attendance', 'leave',
                'overtime', 'payroll', 'reports', 'activities', 'users'
            ]
        },
        {
            'name': 'HR Admin',
            'code': 'hr_admin',
            'description': 'Access to HR operations including employee profiles, attendance tracking, leave requests, overtime, payroll processing, and reports.',
            'is_system': True,
            'permissions': [
                'dashboard', 'employees', 'attendance', 'leave',
                'overtime', 'payroll', 'reports', 'activities'
            ]
        },
        {
            'name': 'Manager',
            'code': 'manager',
            'description': 'Departmental management with permissions to view team attendance, approve leave requests, and monitor department schedules.',
            'is_system': True,
            'permissions': [
                'dashboard', 'employees', 'attendance', 'leave'
            ]
        },
        {
            'name': 'Employee',
            'code': 'employee',
            'description': 'Standard employee access restricted to self-service features (My Attendance, Leave Requests, Overtime, and Payslips).',
            'is_system': True,
            'permissions': [
                'dashboard', 'attendance', 'leave', 'overtime', 'payroll'
            ]
        }
    ]

    for role_data in default_roles:
        Role.objects.update_or_create(
            code=role_data['code'],
            defaults=role_data
        )


def remove_default_roles(apps, schema_editor):
    Role = apps.get_model('accounts', 'Role')
    Role.objects.filter(code__in=['super_admin', 'hr_admin', 'manager', 'employee']).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_role_alter_user_role'),
    ]

    operations = [
        migrations.RunPython(seed_default_roles, remove_default_roles),
    ]
