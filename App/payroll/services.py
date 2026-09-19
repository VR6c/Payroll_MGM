from decimal import Decimal, ROUND_HALF_UP
from calendar import monthrange
from datetime import date
from django.db import transaction
from config.rules import get_rule
from .models import Payroll, SalaryStructure
from employees.models import Employee
import logging

logger = logging.getLogger('payroll')

class PayrollCalculator:
    @staticmethod
    def _prorate_amount(amount, join_date, period_start, period_end):
        if join_date <= period_start:
            return amount
        _, total_days = monthrange(period_start.year, period_start.month)
        employed_days = (period_end - max(join_date, period_start)).days + 1
        if employed_days <= 0:
            return Decimal('0')
        daily_rate = amount / Decimal(total_days)
        return (daily_rate * Decimal(employed_days)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    @staticmethod
    def generate_for_employee(employee, period_start):
        period_end = date(period_start.year, period_start.month, monthrange(period_start.year, period_start.month)[1])
        structure = SalaryStructure.objects.filter(
            employee=employee, effective_date__lte=period_end, status=True
        ).order_by('-effective_date').first()
        if not structure:
            raise ValueError(f"No active salary structure for {employee}")

        prorated_basic = PayrollCalculator._prorate_amount(structure.basic_salary, employee.join_date, period_start, period_end)
        allowances = [structure.transportation, structure.housing, structure.meal_allowance, structure.other_allowance]
        total_allowance = sum(PayrollCalculator._prorate_amount(a, employee.join_date, period_start, period_end) for a in allowances)

        gross = prorated_basic + total_allowance
        tax_rate = get_rule('payroll', 'tax_rate', Decimal('0.10'))
        nssf_rate = get_rule('payroll', 'nssf_rate', Decimal('0.05'))
        tax = (gross * tax_rate).quantize(Decimal('0.01'))
        nssf = (gross * nssf_rate).quantize(Decimal('0.01'))
        net = gross - tax - nssf

        payroll, _ = Payroll.objects.update_or_create(
            employee=employee, payroll_period=period_start,
            defaults={
                'basic_salary': prorated_basic, 'allowance': total_allowance,
                'gross_salary': gross, 'tax': tax, 'nssf': nssf,
                'total_deduction': tax + nssf, 'net_salary': net,
                'status': Payroll.Status.DRAFT
            }
        )
        logger.info(f"Payroll generated: {employee.employee_code} | {period_start} | Net: {net}")
        return payroll

    @staticmethod
    def recalculate_payroll_totals(payroll):
        payroll.gross_salary = payroll.basic_salary + payroll.allowance + payroll.bonus + payroll.overtime
        tax_rate = get_rule('payroll', 'tax_rate', Decimal('0.10'))
        nssf_rate = get_rule('payroll', 'nssf_rate', Decimal('0.05'))
        payroll.tax = (payroll.gross_salary * tax_rate).quantize(Decimal('0.01'))
        payroll.nssf = (payroll.gross_salary * nssf_rate).quantize(Decimal('0.01'))
        payroll.total_deduction = payroll.tax + payroll.nssf + payroll.other_deduction
        payroll.net_salary = payroll.gross_salary - payroll.total_deduction
        payroll.save()
        return payroll

class PayrollGenerator:
    @staticmethod
    @transaction.atomic
    def generate_monthly(company_id, period_start, dry_run=False):
        employees = Employee.objects.filter(company_id=company_id, status='active')
        results = {'success': [], 'failed': [], 'dry_run': dry_run}
        for emp in employees:
            sid = transaction.savepoint()
            try:
                payroll = PayrollCalculator.generate_for_employee(emp, period_start)
                results['success'].append({'employee_code': emp.employee_code, 'net_salary': str(payroll.net_salary)})
                transaction.savepoint_commit(sid)
            except Exception as e:
                transaction.savepoint_rollback(sid)
                results['failed'].append({'employee_code': emp.employee_code, 'error': str(e)})
                logger.error(f"Payroll FAILED: {emp.employee_code} | {e}", exc_info=True)
        if dry_run:
            transaction.set_rollback(True)
        return results
