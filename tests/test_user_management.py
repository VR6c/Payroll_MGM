from django.test import TestCase, Client
from django.urls import reverse
from django.template.context import BaseContext
from datetime import date

# Python 3.14 compatibility patch for Django Context copy
if not getattr(BaseContext, '_copy_patched', False):
    def _safe_context_copy(self):
        duplicate = self.__class__.__new__(self.__class__)
        duplicate.__dict__.update(self.__dict__)
        if hasattr(self, 'dicts'):
            duplicate.dicts = self.dicts[:]
        return duplicate
    BaseContext.__copy__ = _safe_context_copy
    BaseContext._copy_patched = True

from accounts.models import User, Role
from companies.models import Company, Department, Position
from employees.models import Employee


class UserManagementTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Payroll MGM Test")
        self.dept = Department.objects.create(company=self.company, name="HR Dept")
        self.pos = Position.objects.create(company=self.company, name="HR Specialist")

        self.super_admin = User.objects.create_superuser(
            username="testadmin",
            password="adminpassword123",
            email="admin@test.com",
            role='super_admin'
        )

        self.hr_user = User.objects.create_user(
            username="testhr",
            password="hrpassword123",
            email="hr@test.com",
            role='hr_admin'
        )

        self.employee_user = User.objects.create_user(
            username="testemp",
            password="emppassword123",
            email="emp@test.com",
            role='employee'
        )

        self.unlinked_employee = Employee.objects.create(
            company=self.company,
            department=self.dept,
            position=self.pos,
            employee_code="EMP-9999",
            first_name="Jane",
            last_name="Smith",
            email="jane.smith@test.com",
            join_date=date(2025, 1, 1),
            basic_salary=3000.00
        )

        self.client = Client()

    def test_super_admin_can_access_user_list(self):
        self.client.force_login(self.super_admin)
        response = self.client.get(reverse('accounts:user_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Users & RBAC Management")
        self.assertContains(response, "testadmin")
        self.assertContains(response, "testhr")
        self.assertContains(response, "testemp")

    def test_non_superadmin_forbidden_from_user_list(self):
        self.client.force_login(self.hr_user)
        response = self.client.get(reverse('accounts:user_list'))
        self.assertEqual(response.status_code, 403)

        self.client.force_login(self.employee_user)
        response = self.client.get(reverse('accounts:user_list'))
        self.assertEqual(response.status_code, 403)

    def test_create_user_with_role_and_employee_linking(self):
        self.client.force_login(self.super_admin)
        post_data = {
            'username': 'newuser',
            'first_name': 'New',
            'last_name': 'User',
            'email': 'newuser@test.com',
            'phone': '+85512345678',
            'role': 'hr_admin',
            'password': 'password123',
            'confirm_password': 'password123',
            'employee': self.unlinked_employee.pk,
            'is_active': 'on'
        }
        response = self.client.post(reverse('accounts:user_create'), data=post_data)
        self.assertEqual(response.status_code, 302)

        new_user = User.objects.get(username='newuser')
        self.assertEqual(new_user.role, 'hr_admin')
        self.assertTrue(new_user.is_staff)
        self.assertFalse(new_user.is_superuser)
        self.assertTrue(new_user.check_password('password123'))

        self.unlinked_employee.refresh_from_db()
        self.assertEqual(self.unlinked_employee.user, new_user)

    def test_update_user_details_and_role(self):
        self.client.force_login(self.super_admin)
        post_data = {
            'username': 'testemp',
            'first_name': 'UpdatedFirst',
            'last_name': 'UpdatedLast',
            'email': 'updated@test.com',
            'phone': '+85598765432',
            'role': 'manager',
            'employee': '',
            'is_active': 'on'
        }
        response = self.client.post(
            reverse('accounts:user_update', kwargs={'pk': self.employee_user.pk}),
            data=post_data
        )
        self.assertEqual(response.status_code, 302)

        self.employee_user.refresh_from_db()
        self.assertEqual(self.employee_user.role, 'manager')
        self.assertEqual(self.employee_user.first_name, 'UpdatedFirst')
        self.assertEqual(self.employee_user.last_name, 'UpdatedLast')
        self.assertEqual(self.employee_user.email, 'updated@test.com')

    def test_admin_password_reset(self):
        self.client.force_login(self.super_admin)
        post_data = {
            'new_password': 'brandnewsecretpassword',
            'confirm_password': 'brandnewsecretpassword'
        }
        response = self.client.post(
            reverse('accounts:user_password_reset', kwargs={'pk': self.employee_user.pk}),
            data=post_data
        )
        self.assertEqual(response.status_code, 302)

        self.employee_user.refresh_from_db()
        self.assertTrue(self.employee_user.check_password('brandnewsecretpassword'))

    def test_toggle_user_status(self):
        self.client.force_login(self.super_admin)

        # Deactivate
        response = self.client.post(
            reverse('accounts:user_status_toggle', kwargs={'pk': self.employee_user.pk})
        )
        self.assertEqual(response.status_code, 302)
        self.employee_user.refresh_from_db()
        self.assertFalse(self.employee_user.is_active)

        # Reactivate
        response = self.client.post(
            reverse('accounts:user_status_toggle', kwargs={'pk': self.employee_user.pk})
        )
        self.assertEqual(response.status_code, 302)
        self.employee_user.refresh_from_db()
        self.assertTrue(self.employee_user.is_active)

    def test_self_protection_prevent_self_toggle_or_delete(self):
        self.client.force_login(self.super_admin)

        # Prevent toggling own status
        self.client.post(
            reverse('accounts:user_status_toggle', kwargs={'pk': self.super_admin.pk})
        )
        self.super_admin.refresh_from_db()
        self.assertTrue(self.super_admin.is_active)

        # Prevent deleting self
        self.client.post(
            reverse('accounts:user_delete', kwargs={'pk': self.super_admin.pk})
        )
        self.assertTrue(User.objects.filter(pk=self.super_admin.pk).exists())

    def test_delete_user(self):
        self.client.force_login(self.super_admin)
        emp_pk = self.employee_user.pk
        response = self.client.post(
            reverse('accounts:user_delete', kwargs={'pk': emp_pk})
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(User.objects.filter(pk=emp_pk).exists())


class RoleManagementTests(TestCase):
    def setUp(self):
        self.super_admin = User.objects.create_superuser(
            username="testsuperadmin",
            password="adminpassword123",
            email="superadmin@test.com",
            role='super_admin'
        )

        self.hr_user = User.objects.create_user(
            username="testhruser",
            password="hrpassword123",
            email="hruser@test.com",
            role='hr_admin'
        )

        self.client = Client()

    def test_super_admin_can_access_role_list(self):
        self.client.force_login(self.super_admin)
        response = self.client.get(reverse('accounts:role_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Access Roles (RBAC) Management")
        self.assertContains(response, "Super Admin")
        self.assertContains(response, "HR Admin")

    def test_non_superadmin_forbidden_from_role_list(self):
        self.client.force_login(self.hr_user)
        response = self.client.get(reverse('accounts:role_list'))
        self.assertEqual(response.status_code, 403)

    def test_create_custom_role(self):
        self.client.force_login(self.super_admin)
        post_data = {
            'name': 'Payroll Auditor',
            'code': 'payroll_auditor',
            'description': 'Audits all payroll runs and calculations',
            'permissions': ['payroll', 'reports', 'activities']
        }
        response = self.client.post(reverse('accounts:role_create'), data=post_data)
        self.assertEqual(response.status_code, 302)

        role = Role.objects.get(code='payroll_auditor')
        self.assertEqual(role.name, 'Payroll Auditor')
        self.assertFalse(role.is_system)
        self.assertIn('payroll', role.permissions)
        self.assertIn('reports', role.permissions)

    def test_update_custom_role(self):
        self.client.force_login(self.super_admin)
        role = Role.objects.create(
            name='Test Custom Role',
            code='test_custom_role',
            description='Initial description',
            permissions=['dashboard']
        )
        post_data = {
            'name': 'Updated Custom Role',
            'code': 'test_custom_role',
            'description': 'Updated description',
            'permissions': ['dashboard', 'employees']
        }
        response = self.client.post(
            reverse('accounts:role_update', kwargs={'pk': role.pk}),
            data=post_data
        )
        self.assertEqual(response.status_code, 302)

        role.refresh_from_db()
        self.assertEqual(role.name, 'Updated Custom Role')
        self.assertEqual(role.description, 'Updated description')
        self.assertIn('employees', role.permissions)

    def test_cannot_delete_system_role(self):
        self.client.force_login(self.super_admin)
        super_admin_role = Role.objects.get(code='super_admin')
        response = self.client.post(
            reverse('accounts:role_delete', kwargs={'pk': super_admin_role.pk})
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Role.objects.filter(code='super_admin').exists())

    def test_cannot_delete_role_with_assigned_users(self):
        self.client.force_login(self.super_admin)
        custom_role = Role.objects.create(
            name='Team Lead',
            code='team_lead',
            description='Leads a team',
            permissions=['dashboard', 'attendance']
        )
        User.objects.create_user(
            username="leaduser",
            password="leadpassword123",
            role='team_lead'
        )

        response = self.client.post(
            reverse('accounts:role_delete', kwargs={'pk': custom_role.pk})
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Role.objects.filter(code='team_lead').exists())

    def test_delete_unassigned_custom_role(self):
        self.client.force_login(self.super_admin)
        unused_role = Role.objects.create(
            name='Temporary Role',
            code='temp_role',
            description='Temporary role for testing',
            permissions=[]
        )
        pk = unused_role.pk
        response = self.client.post(
            reverse('accounts:role_delete', kwargs={'pk': pk})
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Role.objects.filter(pk=pk).exists())

    def test_granular_permissions_resolution(self):
        self.client.force_login(self.super_admin)
        post_data = {
            'name': 'Shift Supervisor',
            'code': 'shift_supervisor',
            'description': 'Can view and record attendance but not manage break policy',
            'permissions': ['attendance.view', 'attendance.record', 'attendance.export']
        }
        response = self.client.post(reverse('accounts:role_create'), data=post_data)
        self.assertEqual(response.status_code, 302)

        role = Role.objects.get(code='shift_supervisor')
        self.assertTrue(role.has_permission('attendance.view'))
        self.assertTrue(role.has_permission('attendance.record'))
        self.assertTrue(role.has_permission('attendance.export'))
        self.assertFalse(role.has_permission('attendance.breaks'))
        self.assertTrue(role.has_permission('attendance'))

        test_user = User.objects.create_user(
            username='shiftuser',
            password='shiftpassword123',
            role='shift_supervisor'
        )
        self.assertTrue(test_user.has_permission('attendance.view'))
        self.assertTrue(test_user.has_permission('attendance.export'))
        self.assertFalse(test_user.has_permission('attendance.breaks'))

