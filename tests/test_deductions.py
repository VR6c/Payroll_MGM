from decimal import Decimal
from datetime import date, time, datetime
from django.utils import timezone
from django.test import TestCase, Client
from django.urls import reverse
from tests.factories import EmployeeFactory, SalaryStructureFactory, CompanyFactory, UserFactory
from payroll.models import Payroll, DeductionRule, PayrollDeductionItem
from payroll.services import PayrollCalculator, DeductionEngine
from attendance.models import Attendance, EmployeeSchedule
from leave.models import LeaveType, LeaveRequest, LeavePeriod
from reports.exporters import generate_payslip_pdf


class DeductionEngineUnitTest(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.employee = EmployeeFactory(company=self.company)
        # Daily salary: $1000 / 24 = $41.67, Hourly salary: $41.67 / 8 = $5.21
        self.daily_salary = Decimal('41.67')
        self.monthly_salary = Decimal('1000.00')

    def test_absent_percentage_100_and_200(self):
        # 100% daily salary rule
        r100 = DeductionRule.objects.create(
            company=self.company,
            name="Absent 100%",
            category=DeductionRule.Category.ABSENT,
            condition_unit=DeductionRule.ConditionUnit.DAYS,
            operator=DeductionRule.Operator.ALWAYS,
            calc_type=DeductionRule.CalcType.PERCENT_DAILY,
            rate_or_amount=Decimal('100.00'),
            is_active=True
        )

        metrics = {'absent_days': Decimal('1.0')}
        res = DeductionEngine.calculate_deductions(self.employee, self.daily_salary, self.monthly_salary, metrics)
        self.assertEqual(res['total_deductions'], Decimal('41.67'))
        self.assertEqual(len(res['items']), 1)
        self.assertEqual(res['items'][0]['calculated_amount'], Decimal('41.67'))

        # 200% daily salary penalty rule
        r100.delete()
        DeductionRule.objects.create(
            company=self.company,
            name="Absent 200% Penalty",
            category=DeductionRule.Category.ABSENT,
            condition_unit=DeductionRule.ConditionUnit.DAYS,
            operator=DeductionRule.Operator.ALWAYS,
            calc_type=DeductionRule.CalcType.PERCENT_DAILY,
            rate_or_amount=Decimal('200.00'),
            is_active=True
        )
        res200 = DeductionEngine.calculate_deductions(self.employee, self.daily_salary, self.monthly_salary, metrics)
        # 1.0 * 41.67 * 200% = 83.34
        self.assertEqual(res200['total_deductions'], Decimal('83.34'))

    def test_absent_fixed_5_and_10(self):
        rule5 = DeductionRule.objects.create(
            company=self.company,
            name="Absent $5 Fixed",
            category=DeductionRule.Category.ABSENT,
            condition_unit=DeductionRule.ConditionUnit.DAYS,
            operator=DeductionRule.Operator.ALWAYS,
            calc_type=DeductionRule.CalcType.FIXED_PER_UNIT,
            rate_or_amount=Decimal('5.00'),
            is_active=True
        )

        metrics = {'absent_days': Decimal('2.0')}
        res = DeductionEngine.calculate_deductions(self.employee, self.daily_salary, self.monthly_salary, metrics)
        # 2 days * $5 = $10.00
        self.assertEqual(res['total_deductions'], Decimal('10.00'))

        rule5.delete()
        DeductionRule.objects.create(
            company=self.company,
            name="Absent $10 Fixed",
            category=DeductionRule.Category.ABSENT,
            condition_unit=DeductionRule.ConditionUnit.DAYS,
            operator=DeductionRule.Operator.ALWAYS,
            calc_type=DeductionRule.CalcType.FIXED_PER_UNIT,
            rate_or_amount=Decimal('10.00'),
            is_active=True
        )
        res10 = DeductionEngine.calculate_deductions(self.employee, self.daily_salary, self.monthly_salary, metrics)
        # 2 days * $10 = $20.00
        self.assertEqual(res10['total_deductions'], Decimal('20.00'))

    def test_unpaid_leave_percentage_and_fixed(self):
        DeductionRule.objects.create(
            company=self.company,
            name="Unpaid Leave 100%",
            category=DeductionRule.Category.UNPAID_LEAVE,
            condition_unit=DeductionRule.ConditionUnit.DAYS,
            operator=DeductionRule.Operator.ALWAYS,
            calc_type=DeductionRule.CalcType.PERCENT_DAILY,
            rate_or_amount=Decimal('100.00'),
            is_active=True
        )

        metrics = {'unpaid_leave_days': Decimal('1.0'), 'unpaid_leave_count': Decimal('1.0')}
        res = DeductionEngine.calculate_deductions(self.employee, self.daily_salary, self.monthly_salary, metrics)
        self.assertEqual(res['total_deductions'], Decimal('41.67'))

    def test_late_tiering_percentage(self):
        # Tier 1: <= 1.0 hour -> 50% of hourly rate ($5.21 * 50% = $2.605 -> $2.61/hr)
        DeductionRule.objects.create(
            company=self.company,
            name="Late ≤ 1 hour (50%)",
            category=DeductionRule.Category.LATE,
            condition_unit=DeductionRule.ConditionUnit.HOURS,
            operator=DeductionRule.Operator.LTE,
            threshold_max=Decimal('1.00'),
            calc_type=DeductionRule.CalcType.PERCENT_HOURLY,
            rate_or_amount=Decimal('50.00'),
            priority=1,
            is_active=True
        )
        # Tier 2: > 1.0 hour -> 70% of hourly rate ($5.21 * 70% = $3.647 -> $3.65/hr)
        DeductionRule.objects.create(
            company=self.company,
            name="Late > 1 hour (70%)",
            category=DeductionRule.Category.LATE,
            condition_unit=DeductionRule.ConditionUnit.HOURS,
            operator=DeductionRule.Operator.GT,
            threshold_min=Decimal('1.00'),
            calc_type=DeductionRule.CalcType.PERCENT_HOURLY,
            rate_or_amount=Decimal('70.00'),
            priority=2,
            is_active=True
        )

        # 2 late incidents: 0.5 hr and 1.5 hrs
        metrics = {
            'late_hours': Decimal('2.00'),
            'late_count': Decimal('2.0'),
            'late_incidents': [Decimal('0.50'), Decimal('1.50')]
        }
        res = DeductionEngine.calculate_deductions(self.employee, self.daily_salary, self.monthly_salary, metrics)
        self.assertEqual(len(res['items']), 2)
        # Incident 1 (0.5h): 0.5 * 5.21 * 0.50 = 1.30
        self.assertEqual(res['items'][0]['calculated_amount'], Decimal('1.30'))
        # Incident 2 (1.5h): 1.5 * 5.21 * 0.70 = 5.47
        self.assertEqual(res['items'][1]['calculated_amount'], Decimal('5.47'))
        # Total = 1.30 + 5.47 = 6.77
        self.assertEqual(res['total_deductions'], Decimal('6.77'))

    def test_late_tiering_fixed(self):
        # Tier 1: <= 1.0 hour -> Fixed $3
        DeductionRule.objects.create(
            company=self.company,
            name="Late ≤ 1 hour ($3)",
            category=DeductionRule.Category.LATE,
            condition_unit=DeductionRule.ConditionUnit.HOURS,
            operator=DeductionRule.Operator.LTE,
            threshold_max=Decimal('1.00'),
            calc_type=DeductionRule.CalcType.FIXED_PER_UNIT,
            rate_or_amount=Decimal('3.00'),
            priority=1,
            is_active=True
        )
        # Tier 2: > 1.0 hour -> Fixed $8
        DeductionRule.objects.create(
            company=self.company,
            name="Late > 1 hour ($8)",
            category=DeductionRule.Category.LATE,
            condition_unit=DeductionRule.ConditionUnit.HOURS,
            operator=DeductionRule.Operator.GT,
            threshold_min=Decimal('1.00'),
            calc_type=DeductionRule.CalcType.FIXED_PER_UNIT,
            rate_or_amount=Decimal('8.00'),
            priority=2,
            is_active=True
        )

        metrics = {
            'late_hours': Decimal('2.00'),
            'late_count': Decimal('2.0'),
            'late_incidents': [Decimal('0.50'), Decimal('1.50')]
        }
        res = DeductionEngine.calculate_deductions(self.employee, self.daily_salary, self.monthly_salary, metrics)
        self.assertEqual(len(res['items']), 2)
        self.assertEqual(res['items'][0]['calculated_amount'], Decimal('3.00'))
        self.assertEqual(res['items'][1]['calculated_amount'], Decimal('8.00'))
        self.assertEqual(res['total_deductions'], Decimal('11.00'))


class PayrollCalculatorIntegrationTest(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.employee = EmployeeFactory(company=self.company)
        SalaryStructureFactory(
            employee=self.employee,
            basic_salary=Decimal('1000.00'),
            transportation=0,
            housing=0,
            meal_allowance=0,
            other_allowance=0
        )

    def test_payroll_generation_with_absent_and_late_deductions(self):
        # Configure Absent rule (100% daily salary)
        DeductionRule.objects.create(
            company=self.company,
            name="Absent 100%",
            category=DeductionRule.Category.ABSENT,
            condition_unit=DeductionRule.ConditionUnit.DAYS,
            operator=DeductionRule.Operator.ALWAYS,
            calc_type=DeductionRule.CalcType.PERCENT_DAILY,
            rate_or_amount=Decimal('100.00'),
            is_active=True
        )
        # Configure Late rule (Fixed $3 for <= 1 hour)
        DeductionRule.objects.create(
            company=self.company,
            name="Late ≤ 1 hour ($3)",
            category=DeductionRule.Category.LATE,
            condition_unit=DeductionRule.ConditionUnit.HOURS,
            operator=DeductionRule.Operator.LTE,
            threshold_max=Decimal('1.00'),
            calc_type=DeductionRule.CalcType.FIXED_PER_UNIT,
            rate_or_amount=Decimal('3.00'),
            is_active=True
        )

        # Create 1 late attendance on 2024-06-03 (Monday)
        # Work starts at 08:00, check-in at 08:30 (0.50 hrs late)
        Attendance.objects.create(
            employee=self.employee,
            date=date(2024, 6, 3),
            check_in=timezone.make_aware(datetime(2024, 6, 3, 8, 30)),
            check_out=timezone.make_aware(datetime(2024, 6, 3, 17, 0)),
            status=Attendance.Status.LATE
        )

        # Generate payroll for June 2024 with Formula 8 (Monthly / 24 -> Daily = $41.67)
        payroll = PayrollCalculator.generate_for_employee(
            self.employee, date(2024, 6, 1), formula_code='formula_8'
        )

        self.assertEqual(payroll.daily_salary, Decimal('41.67'))
        self.assertGreater(payroll.absent_days, Decimal('0'))
        self.assertEqual(payroll.late_hours, Decimal('0.50'))

        # Check deduction items created
        items = payroll.deduction_items.all()
        self.assertGreater(items.count(), 0)

        # Other deductions must be greater than 0
        self.assertGreater(payroll.other_deduction, Decimal('0'))
        # Total deductions = tax (100) + nssf (50) + other_deduction
        expected_total = payroll.tax + payroll.nssf + payroll.other_deduction
        self.assertEqual(payroll.total_deduction, expected_total)
        self.assertEqual(payroll.net_salary, payroll.gross_salary - payroll.total_deduction)

        # Test PDF exporter renders without error with deduction items
        pdf_bytes = generate_payslip_pdf(payroll)
        self.assertIsInstance(pdf_bytes, bytes)
        self.assertGreater(len(pdf_bytes), 0)


class DeductionRuleViewTest(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.admin = UserFactory(role='hr_admin')
        self.client = Client()
        self.client.force_login(self.admin)

    def test_list_rules_view(self):
        url = reverse('payroll:deduction_rules')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Custom Deduction Rules")

    def test_create_rule_view(self):
        url = reverse('payroll:deduction_rule_create')
        data = {
            'company': self.company.id,
            'name': 'Test Absent 100%',
            'category': 'absent',
            'condition_unit': 'days',
            'operator': 'always',
            'calc_type': 'percent_daily',
            'rate_or_amount': '100.00',
            'priority': 10,
            'is_active': True,
        }
        resp = self.client.post(url, data)
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(DeductionRule.objects.filter(name='Test Absent 100%').exists())

    def test_toggle_rule_view(self):
        rule = DeductionRule.objects.create(
            company=self.company,
            name="Toggle Test",
            category=DeductionRule.Category.ABSENT,
            calc_type=DeductionRule.CalcType.PERCENT_DAILY,
            rate_or_amount=Decimal('100.00'),
            is_active=True
        )
        url = reverse('payroll:deduction_rule_toggle', kwargs={'pk': rule.id})
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 302)
        rule.refresh_from_db()
        self.assertFalse(rule.is_active)
