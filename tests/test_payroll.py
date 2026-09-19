from django.test import TestCase
from decimal import Decimal
from datetime import date
from tests.factories import EmployeeFactory, SalaryStructureFactory, CompanyFactory
from payroll.services import PayrollCalculator, PayrollGenerator, calculate_daily_salary, DAILY_SALARY_FORMULAS
from payroll.models import Payroll

class DailySalaryFormulaTest(TestCase):
    def test_all_16_formulas(self):
        salary = Decimal('1000.00')

        # 1st: (1000 * 12) / (52 * 5.5) = 12000 / 286 = 41.96
        d1, l1 = calculate_daily_salary(salary, 'formula_1', {'workdays_per_week': '5.5'})
        self.assertEqual(d1, Decimal('41.96'))
        self.assertIn('5.5', l1)

        # 2nd: 1000 / [30 - (1.5 * 4)] = 1000 / 24 = 41.67
        d2, l2 = calculate_daily_salary(salary, 'formula_2', {'days_off_per_week': '1.5'})
        self.assertEqual(d2, Decimal('41.67'))

        # 3rd: 1000 / [31 - (1.5 * 4)] = 1000 / 25 = 40.00
        d3, l3 = calculate_daily_salary(salary, 'formula_3', {'days_off_per_week': '1.5', 'days_in_month': '31'})
        self.assertEqual(d3, Decimal('40.00'))

        # 4th: 1000 / 31 = 32.26
        d4, l4 = calculate_daily_salary(salary, 'formula_4', {'days_in_month': '31'})
        self.assertEqual(d4, Decimal('32.26'))

        # 5th: 1000 / 30 = 33.33
        d5, _ = calculate_daily_salary(salary, 'formula_5')
        self.assertEqual(d5, Decimal('33.33'))

        # 6th: 1000 / 26 = 38.46
        d6, _ = calculate_daily_salary(salary, 'formula_6')
        self.assertEqual(d6, Decimal('38.46'))

        # 7th: 1000 / 27 = 37.04
        d7, _ = calculate_daily_salary(salary, 'formula_7')
        self.assertEqual(d7, Decimal('37.04'))

        # 8th: 1000 / 24 = 41.67
        d8, _ = calculate_daily_salary(salary, 'formula_8')
        self.assertEqual(d8, Decimal('41.67'))

        # 9th: 1000 / 28 = 35.71
        d9, _ = calculate_daily_salary(salary, 'formula_9')
        self.assertEqual(d9, Decimal('35.71'))

        # 10th: 1000 / 20 = 50.00
        d10, _ = calculate_daily_salary(salary, 'formula_10')
        self.assertEqual(d10, Decimal('50.00'))

        # 11th: 1000 / 25 = 40.00
        d11, _ = calculate_daily_salary(salary, 'formula_11')
        self.assertEqual(d11, Decimal('40.00'))

        # 12th: 1000 / 22 = 45.45
        d12, _ = calculate_daily_salary(salary, 'formula_12')
        self.assertEqual(d12, Decimal('45.45'))

        # 13th: 1000 / 29 = 34.48
        d13, _ = calculate_daily_salary(salary, 'formula_13')
        self.assertEqual(d13, Decimal('34.48'))

        # 14th: 1000 / 21 = 47.62
        d14, _ = calculate_daily_salary(salary, 'formula_14', {'workdays_in_month': '21'})
        self.assertEqual(d14, Decimal('47.62'))

        # 15th: 1000 / 15 = 66.67
        d15, _ = calculate_daily_salary(salary, 'formula_15')
        self.assertEqual(d15, Decimal('66.67'))

        # 16th: 1000 / 22.5 = 44.44
        d16, _ = calculate_daily_salary(salary, 'formula_16')
        self.assertEqual(d16, Decimal('44.44'))

    def test_daily_salary_saved_on_payroll(self):
        emp = EmployeeFactory()
        SalaryStructureFactory(employee=emp, basic_salary=Decimal('1000.00'), transportation=0, housing=0, meal_allowance=0, other_allowance=0)
        payroll = PayrollCalculator.generate_for_employee(
            emp, date(2024, 6, 1), formula_code='formula_6'
        )
        self.assertEqual(payroll.daily_salary, Decimal('38.46'))
        self.assertIn('26', payroll.daily_salary_formula)

class PayrollCalculatorTest(TestCase):
    def setUp(self):
        self.emp = EmployeeFactory()
        SalaryStructureFactory(employee=self.emp)

    def test_gross_calculation(self):
        payroll = PayrollCalculator.generate_for_employee(self.emp, date(2024, 6, 1))
        self.assertEqual(payroll.gross_salary, Decimal('6500.00'))

    def test_missing_structure_raises(self):
        emp2 = EmployeeFactory(basic_salary=Decimal('0.00'))
        with self.assertRaises(ValueError):
            PayrollCalculator.generate_for_employee(emp2, date(2024, 6, 1))

    def test_holiday_calculation_and_persistence(self):
        # In June 2024 (30 days: 20 weekdays, 10 weekend days Sat/Sun)
        # Without custom schedules, default is Mon-Fri work (20 workdays) and Sat/Sun off (10 holidays)
        payroll = PayrollCalculator.generate_for_employee(self.emp, date(2024, 6, 1))
        self.assertEqual(payroll.holiday_days, Decimal('10.0'))
        self.assertGreater(payroll.holiday_days, Decimal('0.0'))

    def test_holiday_with_schedule_and_exporters(self):
        from attendance.models import EmployeeSchedule
        from reports.exporters import generate_payroll_list_excel, generate_payslip_pdf
        # Set Saturday as half day (0.5 workday, 0.5 holiday) and Sunday as off (1.0 holiday)
        # Weekdays Mon-Fri as full workdays (5 days)
        for dow in range(5):
            EmployeeSchedule.objects.create(employee=self.emp, day_of_week=dow, is_work_day=True, is_half_day=False)
        EmployeeSchedule.objects.create(employee=self.emp, day_of_week=5, is_work_day=True, is_half_day=True)
        EmployeeSchedule.objects.create(employee=self.emp, day_of_week=6, is_work_day=False, is_half_day=False)

        payroll = PayrollCalculator.generate_for_employee(self.emp, date(2024, 6, 1))
        # In June 2024: 5 Saturdays (5 * 0.5 = 2.5), 5 Sundays (5 * 1.0 = 5.0) => 7.5 holiday days
        self.assertEqual(payroll.holiday_days, Decimal('7.5'))

        # Test Excel exporter with holiday column
        excel_bytes = generate_payroll_list_excel([payroll])
        self.assertIsInstance(excel_bytes, bytes)
        self.assertGreater(len(excel_bytes), 0)

        # Test PDF exporter with holiday KPI
        pdf_bytes = generate_payslip_pdf(payroll)
        self.assertIsInstance(pdf_bytes, bytes)
        self.assertGreater(len(pdf_bytes), 0)

class PayrollGeneratorTest(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        for _ in range(5):
            e = EmployeeFactory(company=self.company)
            SalaryStructureFactory(employee=e)

    def test_bulk_generation(self):
        result = PayrollGenerator.generate_monthly(
            self.company.id, date(2024, 6, 1), formula_code='formula_1', formula_params={'workdays_per_week': '5.5'}
        )
        self.assertEqual(len(result['success']), 5)
        self.assertEqual(Payroll.objects.count(), 5)
        first_payroll = Payroll.objects.first()
        self.assertGreater(first_payroll.daily_salary, Decimal('0'))

    def test_dry_run(self):
        result = PayrollGenerator.generate_monthly(self.company.id, date(2024, 7, 1), dry_run=True)
        self.assertEqual(len(result['success']), 5)
        self.assertEqual(Payroll.objects.count(), 0)
