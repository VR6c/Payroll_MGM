from decimal import Decimal
from datetime import date, time, timedelta
from django.test import TestCase, Client
from django.urls import reverse
from django.template.context import BaseContext
from django.utils import timezone

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
from payroll.models import SalaryStructure, Payroll
from payroll.services import PayrollCalculator
from overtime.models import OvertimeType, OvertimeRequest
from overtime.services import OvertimeService


class OvertimeModelAndServiceTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Acme Tech")
        self.dept = Department.objects.create(company=self.company, name="Operations")
        self.pos = Position.objects.create(company=self.company, department=self.dept, name="Analyst")

        self.admin_user = User.objects.create_superuser(username="admin", password="password123", role=User.Role.SUPER_ADMIN)
        self.emp_user = User.objects.create_user(username="sarah", password="password123", role=User.Role.EMPLOYEE)

        self.employee = Employee.objects.create(
            user=self.emp_user,
            company=self.company,
            department=self.dept,
            position=self.pos,
            employee_code="EMP-777",
            first_name="Sarah",
            last_name="Connor",
            email="sarah@acme.com",
            join_date=date(2023, 1, 1),
            basic_salary=Decimal('3520.00')  # 3520 / 176 = $20.00 / hr
        )

        SalaryStructure.objects.create(
            employee=self.employee,
            basic_salary=Decimal('3520.00'),
            effective_date=date(2023, 1, 1),
            status=True
        )

        self.ot_type = OvertimeType.objects.create(
            company=self.company,
            name="Weekend Shift (2.0x)",
            rate_multiplier=Decimal('2.00')
        )

    def test_overtime_type_str(self):
        self.assertEqual(str(self.ot_type), "Weekend Shift (2.0x) (2.00x)")

    def test_hours_calculation_same_day(self):
        req = OvertimeRequest.objects.create(
            employee=self.employee,
            overtime_type=self.ot_type,
            date=date(2024, 6, 15),
            start_time=time(17, 0),
            end_time=time(20, 30),
        )
        self.assertEqual(req.hours, Decimal('3.50'))
        self.assertEqual(req.hourly_rate, Decimal('20.00'))
        # 3.5 hrs * $20/hr * 2.0x = $140.00
        self.assertEqual(req.overtime_amount, Decimal('140.00'))

    def test_hours_calculation_spanning_midnight(self):
        req = OvertimeRequest.objects.create(
            employee=self.employee,
            overtime_type=self.ot_type,
            date=date(2024, 6, 15),
            start_time=time(22, 0),
            end_time=time(2, 0),
        )
        self.assertEqual(req.hours, Decimal('4.00'))
        # 4 hrs * $20/hr * 2.0x = $160.00
        self.assertEqual(req.overtime_amount, Decimal('160.00'))

    def test_overtime_service_approve_and_reject(self):
        req = OvertimeRequest.objects.create(
            employee=self.employee,
            overtime_type=self.ot_type,
            date=date(2024, 6, 15),
            hours=Decimal('3.00'),
            hourly_rate=Decimal('20.00'),
            rate_multiplier=Decimal('1.50'),
            status=OvertimeRequest.Status.PENDING
        )

        OvertimeService.approve_request(req, self.admin_user)
        req.refresh_from_db()
        self.assertEqual(req.status, OvertimeRequest.Status.APPROVED)
        self.assertEqual(req.approved_by, self.admin_user)
        self.assertIsNotNone(req.approved_at)
        # 3.0 hrs * $20/hr * 2.0x (from ot_type) = $120.00
        self.assertEqual(req.overtime_amount, Decimal('120.00'))

        # Test Reject
        req2 = OvertimeRequest.objects.create(
            employee=self.employee,
            date=date(2024, 6, 16),
            hours=Decimal('2.00'),
            status=OvertimeRequest.Status.PENDING
        )
        OvertimeService.reject_request(req2, self.admin_user, reason="Unauthorized overtime")
        req2.refresh_from_db()
        self.assertEqual(req2.status, OvertimeRequest.Status.REJECTED)
        self.assertEqual(req2.rejection_reason, "Unauthorized overtime")

    def test_payroll_integration_with_approved_overtime(self):
        # Create approved overtime in June 2024
        OvertimeRequest.objects.create(
            employee=self.employee,
            overtime_type=self.ot_type,
            date=date(2024, 6, 10),
            hours=Decimal('5.00'),
            hourly_rate=Decimal('20.00'),
            rate_multiplier=Decimal('2.00'),
            overtime_amount=Decimal('200.00'),
            status=OvertimeRequest.Status.APPROVED
        )

        # Create pending overtime in June 2024 (should NOT be added to payroll)
        OvertimeRequest.objects.create(
            employee=self.employee,
            overtime_type=self.ot_type,
            date=date(2024, 6, 12),
            hours=Decimal('2.00'),
            hourly_rate=Decimal('20.00'),
            rate_multiplier=Decimal('2.00'),
            overtime_amount=Decimal('80.00'),
            status=OvertimeRequest.Status.PENDING
        )

        payroll = PayrollCalculator.generate_for_employee(self.employee, date(2024, 6, 1))
        # Basic: 3520.00 + Overtime: 200.00 = Gross: 3720.00
        self.assertEqual(payroll.overtime, Decimal('200.00'))
        self.assertEqual(payroll.gross_salary, Decimal('3720.00'))


class OvertimeViewsIntegrationTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Acme Tech")
        self.dept = Department.objects.create(company=self.company, name="Operations")
        self.pos = Position.objects.create(company=self.company, department=self.dept, name="Analyst")

        self.admin_user = User.objects.create_superuser(username="superadmin", password="password123", role=User.Role.SUPER_ADMIN)
        self.emp_user = User.objects.create_user(username="john", password="password123", role=User.Role.EMPLOYEE)

        self.employee = Employee.objects.create(
            user=self.emp_user,
            company=self.company,
            department=self.dept,
            position=self.pos,
            employee_code="EMP-100",
            first_name="John",
            last_name="Doe",
            email="john.doe@acme.com",
            join_date=date(2023, 1, 1),
            basic_salary=Decimal('4000.00')
        )

        self.ot_type = OvertimeType.objects.create(
            company=self.company,
            name="Holiday Overtime (3.0x)",
            rate_multiplier=Decimal('3.00')
        )

        self.ot_record = OvertimeRequest.objects.create(
            employee=self.employee,
            overtime_type=self.ot_type,
            date=date(2024, 7, 4),
            hours=Decimal('4.00'),
            hourly_rate=Decimal('22.73'),
            rate_multiplier=Decimal('3.00'),
            overtime_amount=Decimal('272.76'),
            status=OvertimeRequest.Status.PENDING
        )

        self.client = Client()

    def test_admin_list_view(self):
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('overtime:list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Overtime Management")
        self.assertContains(response, "EMP-100")

    def test_admin_create_overtime(self):
        self.client.force_login(self.admin_user)
        post_data = {
            'employee': self.employee.id,
            'overtime_type': self.ot_type.id,
            'date': '2024-07-05',
            'start_time': '18:00',
            'end_time': '21:00',
            'hours': '3.00',
            'rate_multiplier': '3.00',
            'hourly_rate': '22.73',
            'overtime_amount': '204.57',
            'reason': 'Production incident resolution',
            'status': 'approved'
        }
        response = self.client.post(reverse('overtime:create'), data=post_data)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(OvertimeRequest.objects.filter(date='2024-07-05').exists())

    def test_admin_update_overtime(self):
        self.client.force_login(self.admin_user)
        post_data = {
            'employee': self.employee.id,
            'overtime_type': self.ot_type.id,
            'date': '2024-07-04',
            'start_time': '18:00',
            'end_time': '22:00',
            'hours': '4.00',
            'rate_multiplier': '3.00',
            'hourly_rate': '22.73',
            'overtime_amount': '272.76',
            'reason': 'Updated task reason',
            'status': 'approved'
        }
        response = self.client.post(reverse('overtime:edit', kwargs={'pk': self.ot_record.id}), data=post_data)
        self.assertEqual(response.status_code, 302)
        self.ot_record.refresh_from_db()
        self.assertEqual(self.ot_record.reason, 'Updated task reason')
        self.assertEqual(self.ot_record.status, OvertimeRequest.Status.APPROVED)

    def test_admin_delete_overtime(self):
        self.client.force_login(self.admin_user)
        response = self.client.post(reverse('overtime:delete', kwargs={'pk': self.ot_record.id}))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(OvertimeRequest.objects.filter(id=self.ot_record.id).exists())

    def test_admin_quick_approve_and_reject(self):
        self.client.force_login(self.admin_user)
        approve_resp = self.client.post(reverse('overtime:approve', kwargs={'pk': self.ot_record.id}))
        self.assertEqual(approve_resp.status_code, 302)
        self.ot_record.refresh_from_db()
        self.assertEqual(self.ot_record.status, OvertimeRequest.Status.APPROVED)

        reject_resp = self.client.post(
            reverse('overtime:reject', kwargs={'pk': self.ot_record.id}),
            data={'rejection_reason': 'Invalid timing'}
        )
        self.assertEqual(reject_resp.status_code, 302)
        self.ot_record.refresh_from_db()
        self.assertEqual(self.ot_record.status, OvertimeRequest.Status.REJECTED)

    def test_overtime_types_crud(self):
        self.client.force_login(self.admin_user)

        # List
        resp = self.client.get(reverse('overtime:types'))
        self.assertEqual(resp.status_code, 200)

        # Create
        create_resp = self.client.post(reverse('overtime:type_create'), data={
            'company': self.company.id,
            'name': 'Custom Project OT (1.8x)',
            'rate_multiplier': '1.80',
            'description': 'Custom project rate',
            'status': True,
        })
        self.assertEqual(create_resp.status_code, 302)
        created_type = OvertimeType.objects.get(name='Custom Project OT (1.8x)')
        self.assertEqual(created_type.rate_multiplier, Decimal('1.80'))

        # Update
        update_resp = self.client.post(reverse('overtime:type_update', kwargs={'pk': created_type.id}), data={
            'company': self.company.id,
            'name': 'Custom Project OT (2.2x)',
            'rate_multiplier': '2.20',
            'description': 'Updated description',
            'status': True,
        })
        self.assertEqual(update_resp.status_code, 302)
        created_type.refresh_from_db()
        self.assertEqual(created_type.rate_multiplier, Decimal('2.20'))

        # Delete
        del_resp = self.client.post(reverse('overtime:type_delete', kwargs={'pk': created_type.id}))
        self.assertEqual(del_resp.status_code, 302)
        self.assertFalse(OvertimeType.objects.filter(id=created_type.id).exists())

    def test_employee_self_service(self):
        self.client.force_login(self.emp_user)

        # View my overtime
        resp = self.client.get(reverse('overtime:my_overtime'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "My Overtime Requests")

        # Submit overtime request
        sub_resp = self.client.post(reverse('overtime:my_create'), data={
            'date': '2024-07-06',
            'start_time': '18:00',
            'end_time': '20:00',
            'hours': '2.00',
            'reason': 'Server upgrade support'
        })
        self.assertEqual(sub_resp.status_code, 302)
        new_req = OvertimeRequest.objects.get(employee=self.employee, date='2024-07-06')
        self.assertEqual(new_req.status, OvertimeRequest.Status.PENDING)
        self.assertEqual(new_req.hours, Decimal('2.00'))

        # Cancel pending request
        cancel_resp = self.client.post(reverse('overtime:my_cancel', kwargs={'pk': new_req.id}))
        self.assertEqual(cancel_resp.status_code, 302)
        new_req.refresh_from_db()
        self.assertEqual(new_req.status, OvertimeRequest.Status.CANCELLED)

    def test_employee_cannot_access_admin_overtime_crud(self):
        self.client.force_login(self.emp_user)
        # Employee should be forbidden or redirected from admin list
        resp = self.client.get(reverse('overtime:list'))
        self.assertIn(resp.status_code, [302, 403])

    def test_overtime_report_view_and_exports(self):
        self.client.force_login(self.admin_user)

        # 1. Report page view
        resp = self.client.get(reverse('overtime:report'))
        self.assertContains(resp, "Overtime Report")
        self.assertContains(resp, "Department Overtime Distribution")

        # 2. Filtered report view
        filtered_resp = self.client.get(
            reverse('overtime:report'),
            data={'from_date': '2024-06-01', 'to_date': '2024-06-30'}
        )
        self.assertEqual(filtered_resp.status_code, 200)

        # 3. Excel export
        excel_resp = self.client.get(reverse('overtime:report_excel'))
        self.assertEqual(excel_resp.status_code, 200)
        self.assertEqual(
            excel_resp['Content-Type'],
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        self.assertTrue(len(excel_resp.content) > 0)

        # 4. PDF export
        pdf_resp = self.client.get(reverse('overtime:report_pdf'))
        self.assertEqual(pdf_resp.status_code, 200)
        self.assertEqual(pdf_resp['Content-Type'], 'application/pdf')
        self.assertTrue(len(pdf_resp.content) > 0)

