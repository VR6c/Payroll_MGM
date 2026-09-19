from django.test import TestCase
from decimal import Decimal
from datetime import date
from tests.factories import EmployeeFactory, SalaryStructureFactory
from payroll.services import PayrollCalculator, PayrollGenerator
from payroll.models import Payroll

class PayrollCalculatorTest(TestCase):
    def setUp(self):
        self.emp = EmployeeFactory()
        SalaryStructureFactory(employee=self.emp)

    def test_gross_calculation(self):
        payroll = PayrollCalculator.generate_for_employee(self.emp, date(2024, 6, 1))
        self.assertEqual(payroll.gross_salary, Decimal('6500.00'))

    def test_missing_structure_raises(self):
        emp2 = EmployeeFactory()
        with self.assertRaises(ValueError):
            PayrollCalculator.generate_for_employee(emp2, date(2024, 6, 1))

class PayrollGeneratorTest(TestCase):
    def setUp(self):
        self.company = EmployeeFactory().company
        for _ in range(5):
            e = EmployeeFactory(company=self.company)
            SalaryStructureFactory(employee=e)

    def test_bulk_generation(self):
        result = PayrollGenerator.generate_monthly(self.company.id, date(2024, 6, 1))
        self.assertEqual(len(result['success']), 5)
        self.assertEqual(Payroll.objects.count(), 5)

    def test_dry_run(self):
        result = PayrollGenerator.generate_monthly(self.company.id, date(2024, 7, 1), dry_run=True)
        self.assertEqual(len(result['success']), 5)
        self.assertEqual(Payroll.objects.count(), 0)
