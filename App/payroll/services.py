from decimal import Decimal, ROUND_HALF_UP
from calendar import monthrange
from datetime import date
from django.db import transaction
from config.rules import get_rule
from .models import Payroll, SalaryStructure
from employees.models import Employee
import logging

logger = logging.getLogger('payroll')

DAILY_SALARY_FORMULAS = {
    'formula_1': {
        'id': 'formula_1',
        'number': 1,
        'name': '1st Formula: (Monthly Salary × 12) / (52 × Workdays per Week)',
        'short_name': '(Monthly × 12) / (52 × Workdays/Week)',
        'expression': 'Daily Salary = (Monthly Salary × 12) / (52 × Workdays per Week)',
        'note': '12 = 12 months in a year, 52 = 52 weeks in a year',
        'category': 'weekly',
        'requires': ['workdays_per_week'],
        'default_params': {'workdays_per_week': '5.5'},
        'param_options': {
            'workdays_per_week': [
                {'value': '5', 'label': 'Mon to Fri (5 days)'},
                {'value': '5.5', 'label': 'Mon to Half Sat (5.5 days)'},
                {'value': '6', 'label': 'Mon to Sat (6 days)'},
            ]
        }
    },
    'formula_2': {
        'id': 'formula_2',
        'number': 2,
        'name': '2nd Formula: Monthly Salary / [30 - (Days off per week × 4)]',
        'short_name': 'Monthly / [30 - (Days Off/Week × 4)]',
        'expression': 'Daily Salary = Monthly Salary / [30 - (Days off per week × 4)]',
        'note': 'Based on 30 standard days minus days off (Days off × 4)',
        'category': 'days_off',
        'requires': ['days_off_per_week'],
        'default_params': {'days_off_per_week': '1.5'},
        'param_options': {
            'days_off_per_week': [
                {'value': '1', 'label': 'Mon to Sat (1 day off)'},
                {'value': '1.5', 'label': 'Mon to Half Sat (1.5 days off)'},
                {'value': '2', 'label': 'Mon to Fri (2 days off)'},
            ]
        }
    },
    'formula_3': {
        'id': 'formula_3',
        'number': 3,
        'name': '3rd Formula: Monthly Salary / [Days in Month - (Days off per week × 4)]',
        'short_name': 'Monthly / [Days in Month - (Days Off/Week × 4)]',
        'expression': 'Daily Salary = Monthly Salary / [Days in the month - (Days off per week × 4)]',
        'note': 'Days in the month minus days off (Days off × 4)',
        'category': 'days_off',
        'requires': ['days_off_per_week', 'days_in_month'],
        'default_params': {'days_off_per_week': '1.5', 'days_in_month': '31'},
        'param_options': {
            'days_off_per_week': [
                {'value': '1', 'label': 'Mon to Sat (1 day off)'},
                {'value': '1.5', 'label': 'Mon to Half Sat (1.5 days off)'},
                {'value': '2', 'label': 'Mon to Fri (2 days off)'},
            ]
        }
    },
    'formula_4': {
        'id': 'formula_4',
        'number': 4,
        'name': '4th Formula (No Holiday): Monthly Salary / Days in Month',
        'short_name': 'Monthly / Days in Month (No Holiday)',
        'expression': 'Daily Salary = Monthly Salary / Days in the month',
        'note': 'All days in the month, including days off are considered paid.',
        'category': 'calendar',
        'requires': ['days_in_month'],
        'default_params': {'days_in_month': '31'},
    },
    'formula_5': {
        'id': 'formula_5',
        'number': 5,
        'name': '5th Formula (No Holiday): Monthly Salary / 30',
        'short_name': 'Monthly / 30 (No Holiday)',
        'expression': 'Daily Salary = Monthly Salary / 30',
        'note': 'All days in the month, including days off are considered paid.',
        'category': 'fixed',
        'divisor': '30',
    },
    'formula_6': {
        'id': 'formula_6',
        'number': 6,
        'name': '6th Formula: Monthly Salary / 26',
        'short_name': 'Monthly / 26',
        'expression': 'Daily Salary = Monthly Salary / 26',
        'note': 'Based on standard 26 workdays',
        'category': 'fixed',
        'divisor': '26',
    },
    'formula_7': {
        'id': 'formula_7',
        'number': 7,
        'name': '7th Formula: Monthly Salary / 27',
        'short_name': 'Monthly / 27',
        'expression': 'Daily Salary = Monthly Salary / 27',
        'note': 'Based on standard 27 workdays',
        'category': 'fixed',
        'divisor': '27',
    },
    'formula_8': {
        'id': 'formula_8',
        'number': 8,
        'name': '8th Formula: Monthly Salary / 24',
        'short_name': 'Monthly / 24',
        'expression': 'Daily Salary = Monthly Salary / 24',
        'note': 'Based on standard 24 workdays',
        'category': 'fixed',
        'divisor': '24',
    },
    'formula_9': {
        'id': 'formula_9',
        'number': 9,
        'name': '9th Formula: Monthly Salary / 28',
        'short_name': 'Monthly / 28',
        'expression': 'Daily Salary = Monthly Salary / 28',
        'note': 'Based on standard 28 workdays/days',
        'category': 'fixed',
        'divisor': '28',
    },
    'formula_10': {
        'id': 'formula_10',
        'number': 10,
        'name': '10th Formula: Monthly Salary / 20',
        'short_name': 'Monthly / 20',
        'expression': 'Daily Salary = Monthly Salary / 20',
        'note': 'Based on standard 20 workdays',
        'category': 'fixed',
        'divisor': '20',
    },
    'formula_11': {
        'id': 'formula_11',
        'number': 11,
        'name': '11th Formula: Monthly Salary / 25',
        'short_name': 'Monthly / 25',
        'expression': 'Daily Salary = Monthly Salary / 25',
        'note': 'Based on standard 25 workdays',
        'category': 'fixed',
        'divisor': '25',
    },
    'formula_12': {
        'id': 'formula_12',
        'number': 12,
        'name': '12th Formula: Monthly Salary / 22',
        'short_name': 'Monthly / 22',
        'expression': 'Daily Salary = Monthly Salary / 22',
        'note': 'Based on standard 22 workdays (Mon-Fri 5 days)',
        'category': 'fixed',
        'divisor': '22',
    },
    'formula_13': {
        'id': 'formula_13',
        'number': 13,
        'name': '13th Formula: Monthly Salary / 29',
        'short_name': 'Monthly / 29',
        'expression': 'Daily Salary = Monthly Salary / 29',
        'note': 'Based on standard 29 workdays/days',
        'category': 'fixed',
        'divisor': '29',
    },
    'formula_14': {
        'id': 'formula_14',
        'number': 14,
        'name': '14th Formula: Monthly Salary / Workdays in Month',
        'short_name': 'Monthly / Workdays in Month',
        'expression': 'Daily Salary = Monthly Salary / Workdays in the month',
        'note': 'Actual workdays in the month (e.g. 21 days)',
        'category': 'calendar',
        'requires': ['workdays_in_month'],
        'default_params': {'workdays_in_month': '21'},
    },
    'formula_15': {
        'id': 'formula_15',
        'number': 15,
        'name': '15th Formula: Monthly Salary / 15',
        'short_name': 'Monthly / 15',
        'expression': 'Daily Salary = Monthly Salary / 15',
        'note': 'Based on semi-monthly 15 days',
        'category': 'fixed',
        'divisor': '15',
    },
    'formula_16': {
        'id': 'formula_16',
        'number': 16,
        'name': '16th Formula: Monthly Salary / 22.5',
        'short_name': 'Monthly / 22.5',
        'expression': 'Daily Salary = Monthly Salary / 22.5',
        'note': 'Based on standard 22.5 workdays',
        'category': 'fixed',
        'divisor': '22.5',
    },
}

def calculate_daily_salary(monthly_salary, formula_code='formula_1', params=None, period_date=None):
    """
    Calculates daily salary based on one of the 16 standard formulas.
    Returns a tuple of (daily_salary: Decimal, formula_label: str).
    """
    if not isinstance(monthly_salary, Decimal):
        monthly_salary = Decimal(str(monthly_salary))
    if monthly_salary <= Decimal('0'):
        return Decimal('0.00'), "Monthly Salary = $0"

    params = params or {}
    formula = DAILY_SALARY_FORMULAS.get(formula_code, DAILY_SALARY_FORMULAS['formula_1'])
    fid = formula['id']

    days_in_month_default = 30
    if period_date:
        _, total_days = monthrange(period_date.year, period_date.month)
        days_in_month_default = total_days

    if fid == 'formula_1':
        workdays = Decimal(str(params.get('workdays_per_week') or '5.5'))
        if workdays <= Decimal('0'):
            workdays = Decimal('5.5')
        divisor = Decimal('52') * workdays
        daily = (monthly_salary * Decimal('12')) / divisor
        label = f"1st Formula: (Monthly × 12) / (52 × {workdays})"

    elif fid == 'formula_2':
        days_off = Decimal(str(params.get('days_off_per_week') or '1.5'))
        divisor = Decimal('30') - (days_off * Decimal('4'))
        if divisor <= Decimal('0'):
            divisor = Decimal('30')
        daily = monthly_salary / divisor
        label = f"2nd Formula: Monthly / [30 - ({days_off} × 4)]"

    elif fid == 'formula_3':
        days_off = Decimal(str(params.get('days_off_per_week') or '1.5'))
        days_in_month = Decimal(str(params.get('days_in_month') or days_in_month_default))
        divisor = days_in_month - (days_off * Decimal('4'))
        if divisor <= Decimal('0'):
            divisor = days_in_month
        daily = monthly_salary / divisor
        label = f"3rd Formula: Monthly / [{int(days_in_month)} - ({days_off} × 4)]"

    elif fid == 'formula_4':
        days_in_month = Decimal(str(params.get('days_in_month') or days_in_month_default))
        if days_in_month <= Decimal('0'):
            days_in_month = Decimal('30')
        daily = monthly_salary / days_in_month
        label = f"4th Formula (No Holiday): Monthly / {int(days_in_month)} days"

    elif fid == 'formula_5':
        daily = monthly_salary / Decimal('30')
        label = "5th Formula (No Holiday): Monthly / 30"

    elif fid == 'formula_6':
        daily = monthly_salary / Decimal('26')
        label = "6th Formula: Monthly / 26"

    elif fid == 'formula_7':
        daily = monthly_salary / Decimal('27')
        label = "7th Formula: Monthly / 27"

    elif fid == 'formula_8':
        daily = monthly_salary / Decimal('24')
        label = "8th Formula: Monthly / 24"

    elif fid == 'formula_9':
        daily = monthly_salary / Decimal('28')
        label = "9th Formula: Monthly / 28"

    elif fid == 'formula_10':
        daily = monthly_salary / Decimal('20')
        label = "10th Formula: Monthly / 20"

    elif fid == 'formula_11':
        daily = monthly_salary / Decimal('25')
        label = "11th Formula: Monthly / 25"

    elif fid == 'formula_12':
        daily = monthly_salary / Decimal('22')
        label = "12th Formula: Monthly / 22"

    elif fid == 'formula_13':
        daily = monthly_salary / Decimal('29')
        label = "13th Formula: Monthly / 29"

    elif fid == 'formula_14':
        workdays = Decimal(str(params.get('workdays_in_month') or '21'))
        if workdays <= Decimal('0'):
            workdays = Decimal('21')
        daily = monthly_salary / workdays
        label = f"14th Formula: Monthly / {workdays} workdays"

    elif fid == 'formula_15':
        daily = monthly_salary / Decimal('15')
        label = "15th Formula: Monthly / 15"

    elif fid == 'formula_16':
        daily = monthly_salary / Decimal('22.5')
        label = "16th Formula: Monthly / 22.5"

    else:
        daily = monthly_salary / Decimal('30')
        label = "Default: Monthly / 30"

    return daily.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP), label


def calculate_period_attendance_metrics(employee, period_start, period_end):
    """
    Computes Attendance (days), Absent (days), Late (hours), Overtime (hours & pay), and Leave (days)
    for an employee within a given period.
    """
    import datetime
    from django.utils import timezone
    from django.db.models import Sum
    from attendance.models import Attendance, EmployeeSchedule, WorkSchedule
    from leave.models import LeaveRequest
    from overtime.services import OvertimeService

    total_period_days = (period_end - period_start).days + 1

    # Fetch employee schedule
    emp_sched = {}
    sched_qs = EmployeeSchedule.objects.filter(employee=employee)
    for s in sched_qs:
        emp_sched[s.day_of_week] = {
            'is_work_day': s.is_work_day,
            'is_half_day': s.is_half_day,
            'start_time': s.start_time,
        }

    # Fetch company work schedule as fallback
    company_sched = WorkSchedule.objects.filter(company=employee.company, status=True).first()

    # Calculate scheduled work days and holidays
    scheduled_work_days = Decimal('0.0')
    holiday_days = Decimal('0.0')
    for d in range(total_period_days):
        cur_date = period_start + datetime.timedelta(days=d)
        dow = cur_date.weekday()
        day_cfg = emp_sched.get(dow)
        if day_cfg:
            is_work = day_cfg['is_work_day']
            is_half = day_cfg['is_half_day']
        else:
            is_work = (dow < 5)  # Mon-Fri default
            is_half = False

        if is_work:
            if is_half:
                scheduled_work_days += Decimal('0.5')
                holiday_days += Decimal('0.5')
            else:
                scheduled_work_days += Decimal('1.0')
        else:
            holiday_days += Decimal('1.0')

    # Query attendance records
    att_qs = Attendance.objects.filter(employee=employee, date__gte=period_start, date__lte=period_end)
    attend_count = Decimal('0.0')
    late_hours = Decimal('0.00')

    for a in att_qs:
        if a.status in ('present', 'late', 'early_leave', 'overtime'):
            a_dow = a.date.weekday()
            day_cfg = emp_sched.get(a_dow)
            is_half = day_cfg['is_half_day'] if day_cfg else False
            if a.working_hours:
                hrs = a.working_hours.total_seconds() / 3600.0
                if hrs >= 7.0:
                    day_val = Decimal('1.0')
                elif hrs >= 5.0:
                    day_val = Decimal('0.75')
                elif hrs >= 3.0:
                    day_val = Decimal('0.5')
                elif hrs >= 1.0:
                    day_val = Decimal('0.25')
                else:
                    day_val = Decimal('0.25')
            elif is_half:
                day_val = Decimal('0.5')
            else:
                day_val = Decimal('1.0')
            attend_count += day_val

        # Late hours calculation
        if a.status == 'late':
            if a.check_in:
                a_dow = a.date.weekday()
                day_cfg = emp_sched.get(a_dow)
                expected_start = (
                    day_cfg['start_time'] if day_cfg and day_cfg.get('start_time')
                    else (company_sched.start_time if company_sched and company_sched.start_time else datetime.time(8, 0))
                )
                exp_dt = datetime.datetime.combine(a.date, expected_start)
                if timezone.is_aware(a.check_in):
                    exp_dt = timezone.make_aware(exp_dt, timezone.get_current_timezone())
                diff_sec = (a.check_in - exp_dt).total_seconds()
                if diff_sec > 0:
                    late_hours += Decimal(str(round(diff_sec / 3600.0, 2)))
                else:
                    late_hours += Decimal('0.50')
            else:
                late_hours += Decimal('1.00')

    # Leave days
    leave_qs = LeaveRequest.objects.filter(
        employee=employee,
        status='approved',
        periods__start_date__lte=period_end,
        periods__end_date__gte=period_start
    ).distinct()
    leave_days = sum((Decimal(str(l.total_days or 0)) for l in leave_qs), Decimal('0.0'))

    # Absent days
    absent_count = max(Decimal('0.0'), scheduled_work_days - attend_count - leave_days)

    # Overtime hours & pay
    try:
        overtime_hours = OvertimeService.get_monthly_overtime_hours(employee, period_start, period_end)
        overtime_pay = OvertimeService.get_monthly_overtime_total(employee, period_start, period_end)
    except Exception:
        overtime_hours = Decimal('0.00')
        overtime_pay = Decimal('0.00')

    return {
        'attendance_days': attend_count.quantize(Decimal('0.1'), rounding=ROUND_HALF_UP),
        'absent_days': absent_count.quantize(Decimal('0.1'), rounding=ROUND_HALF_UP),
        'late_hours': late_hours.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
        'overtime_hours': Decimal(str(overtime_hours)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
        'overtime_pay': Decimal(str(overtime_pay)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
        'leave_days': leave_days.quantize(Decimal('0.1'), rounding=ROUND_HALF_UP),
        'holiday_days': holiday_days.quantize(Decimal('0.1'), rounding=ROUND_HALF_UP),
    }


class PayrollCalculator:
    @staticmethod
    def _prorate_amount(amount, join_date, period_start, period_end, daily_rate=None):
        if join_date <= period_start:
            return amount
        _, total_days = monthrange(period_start.year, period_start.month)
        employed_days = (period_end - max(join_date, period_start)).days + 1
        if employed_days <= 0:
            return Decimal('0')
        if daily_rate is None:
            daily_rate = amount / Decimal(total_days)
        prorated = (daily_rate * Decimal(employed_days)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        return min(amount, prorated)

    @staticmethod
    def generate_for_employee(employee, period_start, formula_code='formula_1', formula_params=None):
        period_end = date(period_start.year, period_start.month, monthrange(period_start.year, period_start.month)[1])
        structure = SalaryStructure.objects.filter(
            employee=employee, effective_date__lte=period_end, status=True
        ).order_by('-effective_date').first()
        if not structure:
            if employee.basic_salary and employee.basic_salary > 0:
                structure = SalaryStructure.objects.create(
                    employee=employee,
                    basic_salary=employee.basic_salary,
                    effective_date=employee.join_date or period_start,
                    status=True
                )
            else:
                raise ValueError(f"No active salary structure for {employee}")

        daily_salary, formula_label = calculate_daily_salary(
            structure.basic_salary, formula_code=formula_code, params=formula_params, period_date=period_start
        )

        prorated_basic = PayrollCalculator._prorate_amount(
            structure.basic_salary, employee.join_date, period_start, period_end, daily_rate=daily_salary
        )
        allowances = [structure.transportation, structure.housing, structure.meal_allowance, structure.other_allowance]
        total_allowance = sum(PayrollCalculator._prorate_amount(a, employee.join_date, period_start, period_end) for a in allowances)

        # Calculate attendance, absent, late (hours), overtime (hours & pay), and leave
        att_metrics = calculate_period_attendance_metrics(employee, period_start, period_end)
        overtime_pay = att_metrics['overtime_pay']

        gross = prorated_basic + total_allowance + overtime_pay
        tax_rate = get_rule('payroll', 'tax_rate', Decimal('0.10'))
        nssf_rate = get_rule('payroll', 'nssf_rate', Decimal('0.05'))
        tax = (gross * tax_rate).quantize(Decimal('0.01'))
        nssf = (gross * nssf_rate).quantize(Decimal('0.01'))
        net = gross - tax - nssf

        payroll, _ = Payroll.objects.update_or_create(
            employee=employee, payroll_period=period_start,
            defaults={
                'basic_salary': prorated_basic,
                'daily_salary': daily_salary,
                'daily_salary_formula': formula_label,
                'attendance_days': att_metrics['attendance_days'],
                'absent_days': att_metrics['absent_days'],
                'late_hours': att_metrics['late_hours'],
                'overtime_hours': att_metrics['overtime_hours'],
                'leave_days': att_metrics['leave_days'],
                'holiday_days': att_metrics['holiday_days'],
                'allowance': total_allowance,
                'overtime': overtime_pay,
                'gross_salary': gross,
                'tax': tax,
                'nssf': nssf,
                'total_deduction': tax + nssf,
                'net_salary': net,
                'status': Payroll.Status.DRAFT
            }
        )
        logger.info(f"Payroll generated: {employee.employee_code} | {period_start} | Daily: {daily_salary} ({formula_label}) | Net: {net}")
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
    def generate_monthly(company_id, period_start, dry_run=False, formula_code='formula_1', formula_params=None):
        employees = Employee.objects.filter(company_id=company_id, status='active')
        results = {'success': [], 'failed': [], 'dry_run': dry_run}
        for emp in employees:
            sid = transaction.savepoint()
            try:
                payroll = PayrollCalculator.generate_for_employee(
                    emp, period_start, formula_code=formula_code, formula_params=formula_params
                )
                results['success'].append({
                    'employee_code': emp.employee_code,
                    'net_salary': str(payroll.net_salary),
                    'daily_salary': str(payroll.daily_salary),
                    'formula': payroll.daily_salary_formula
                })
                transaction.savepoint_commit(sid)
            except Exception as e:
                transaction.savepoint_rollback(sid)
                results['failed'].append({'employee_code': emp.employee_code, 'error': str(e)})
                logger.error(f"Payroll FAILED: {emp.employee_code} | {e}", exc_info=True)
        if dry_run:
            transaction.set_rollback(True)
        return results
