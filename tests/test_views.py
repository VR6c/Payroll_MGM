from django.test import TestCase, Client
from django.urls import reverse
from django.template.context import BaseContext

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

from accounts.models import User
from companies.models import Company, Department, Position
from employees.models import Employee
from attendance.models import Attendance, WorkSchedule
from leave.models import LeaveType, LeaveRequest
from payroll.models import Payroll
from datetime import date, time

class ViewIntegrationTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Acme Corp")
        self.dept = Department.objects.create(company=self.company, name="Engineering")
        self.pos = Position.objects.create(company=self.company, name="Developer")

        self.admin_user = User.objects.create_superuser(username="admin", password="password123", role=User.Role.SUPER_ADMIN)
        self.employee_user = User.objects.create_user(username="johndoe", password="password123", role=User.Role.EMPLOYEE)

        self.employee = Employee.objects.create(
            user=self.employee_user,
            company=self.company,
            department=self.dept,
            position=self.pos,
            employee_code="EMP-001",
            first_name="John",
            last_name="Doe",
            email="john@acme.com",
            join_date=date(2023, 1, 1),
            basic_salary=5000.00
        )

        self.client = Client()

    def test_dashboard_view_admin(self):
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('dashboard:home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dashboard")

    def test_dashboard_view_employee(self):
        self.client.force_login(self.employee_user)
        response = self.client.get(reverse('dashboard:home'))
        self.assertEqual(response.status_code, 200)

    def test_employee_list_view(self):
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('employees:list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "EMP-001")

    def test_employee_detail_view(self):
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('employees:detail', kwargs={'pk': self.employee.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "John")

    def test_attendance_checkin_and_my_attendance(self):
        self.client.force_login(self.employee_user)
        checkin_resp = self.client.post(reverse('attendance:check_in'))
        self.assertEqual(checkin_resp.status_code, 302)

        attendance_resp = self.client.get(reverse('attendance:my_attendance'))
        self.assertEqual(attendance_resp.status_code, 200)
        self.assertContains(attendance_resp, "Present")

    def test_leave_request(self):
        self.client.force_login(self.employee_user)
        leave_type = LeaveType.objects.create(company=self.company, name="Annual Leave", default_days=10)
        response = self.client.get(reverse('leave:my_leaves'))
        self.assertEqual(response.status_code, 200)

    def test_payroll_views(self):
        self.client.force_login(self.admin_user)
        payroll = Payroll.objects.create(
            employee=self.employee,
            payroll_period=date(2024, 6, 1),
            basic_salary=5000.00,
            gross_salary=5000.00,
            tax=500.00,
            nssf=250.00,
            total_deduction=750.00,
            net_salary=4250.00,
            status=Payroll.Status.APPROVED
        )
        response = self.client.get(reverse('payroll:list'))
        self.assertEqual(response.status_code, 200)

        payslip_resp = self.client.get(reverse('payroll:payslip', kwargs={'pk': payroll.pk}))
        self.assertEqual(payslip_resp.status_code, 200)
        self.assertContains(payslip_resp, "4250.00")
