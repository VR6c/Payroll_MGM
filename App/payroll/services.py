from decimal import Decimal, ROUND_HALF_UP
from calendar import monthrange
from datetime import date
from django.db import transaction
from config.rules import get_rule
from .models import Payroll, SalaryStructure, DeductionRule, PayrollDeductionItem
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
    late_count = 0
    late_incidents = []

    for a in att_qs:
        if a.status in ('present', 'late', 'early_leave', 'checkout_early', 'overtime'):
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
            late_count += 1
            cur_late_hrs = Decimal('0.50')
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
                    cur_late_hrs = Decimal(str(round(diff_sec / 3600.0, 2)))
                else:
                    cur_late_hrs = Decimal('0.50')
            else:
                cur_late_hrs = Decimal('1.00')
            late_hours += cur_late_hrs
            late_incidents.append(cur_late_hrs)

    # Leave days (distinguish between paid and unpaid leaves)
    leave_qs = LeaveRequest.objects.filter(
        employee=employee,
        status='approved',
        periods__start_date__lte=period_end,
        periods__end_date__gte=period_start
    ).select_related('leave_type').distinct()

    paid_leave_days = Decimal('0.0')
    unpaid_leave_days = Decimal('0.0')
    unpaid_leave_count = 0

    for l in leave_qs:
        ldays = Decimal(str(l.total_days or 0))
        if l.leave_type and not l.leave_type.paid:
            unpaid_leave_days += ldays
            unpaid_leave_count += 1
        else:
            paid_leave_days += ldays

    leave_days = paid_leave_days + unpaid_leave_days

    # Absent days: missed workdays that are NOT covered by attendance or leave
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
        'absent_count': absent_count.quantize(Decimal('0.1'), rounding=ROUND_HALF_UP),
        'late_hours': late_hours.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
        'late_count': Decimal(str(late_count)),
        'late_incidents': late_incidents,
        'overtime_hours': Decimal(str(overtime_hours)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
        'overtime_pay': Decimal(str(overtime_pay)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
        'leave_days': leave_days.quantize(Decimal('0.1'), rounding=ROUND_HALF_UP),
        'paid_leave_days': paid_leave_days.quantize(Decimal('0.1'), rounding=ROUND_HALF_UP),
        'unpaid_leave_days': unpaid_leave_days.quantize(Decimal('0.1'), rounding=ROUND_HALF_UP),
        'unpaid_leave_count': Decimal(str(unpaid_leave_count)),
        'holiday_days': holiday_days.quantize(Decimal('0.1'), rounding=ROUND_HALF_UP),
    }


class DeductionEngine:
    @staticmethod
    def evaluate_condition(operator, value, threshold_min=None, threshold_max=None):
        if operator == DeductionRule.Operator.ALWAYS:
            return True
        val = Decimal(str(value))
        if operator == DeductionRule.Operator.LTE:
            return threshold_max is not None and val <= threshold_max
        elif operator == DeductionRule.Operator.LT:
            return threshold_max is not None and val < threshold_max
        elif operator == DeductionRule.Operator.GTE:
            return threshold_min is not None and val >= threshold_min
        elif operator == DeductionRule.Operator.GT:
            return threshold_min is not None and val > threshold_min
        elif operator == DeductionRule.Operator.BETWEEN:
            if threshold_min is not None and threshold_max is not None:
                return threshold_min <= val <= threshold_max
            elif threshold_min is not None:
                return val >= threshold_min
            elif threshold_max is not None:
                return val <= threshold_max
            return True
        elif operator == DeductionRule.Operator.EQ:
            target = threshold_min if threshold_min is not None else threshold_max
            return target is not None and val == target
        return True

    @staticmethod
    def calculate_deductions(employee, daily_salary, monthly_salary, att_metrics, period_start=None, period_end=None):
        """
        Evaluates active DeductionRules for the employee's company against period attendance metrics.
        Returns:
          - 'items': list of dicts representing calculated line items
          - 'total_deductions': Decimal total of all calculated items
        """
        rules = DeductionRule.objects.filter(
            company=employee.company, is_active=True
        ).order_by('category', 'priority', 'id')

        standard_work_hours = get_rule('attendance', 'standard_work_hours_per_day', Decimal('8.0'))
        if not isinstance(standard_work_hours, Decimal):
            standard_work_hours = Decimal(str(standard_work_hours))
        if standard_work_hours <= Decimal('0'):
            standard_work_hours = Decimal('8.0')

        hourly_salary = (daily_salary / standard_work_hours).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        items = []

        absent_days = att_metrics.get('absent_days', Decimal('0.0'))
        absent_count = att_metrics.get('absent_count', absent_days)
        unpaid_leave_days = att_metrics.get('unpaid_leave_days', Decimal('0.0'))
        unpaid_leave_count = att_metrics.get('unpaid_leave_count', Decimal('0.0'))
        late_hours = att_metrics.get('late_hours', Decimal('0.00'))
        late_count = att_metrics.get('late_count', Decimal('0.0'))
        late_incidents = att_metrics.get('late_incidents', [])

        rules_by_cat = {}
        for r in rules:
            rules_by_cat.setdefault(r.category, []).append(r)

        # 1. Evaluate Absent rules
        for r in rules_by_cat.get(DeductionRule.Category.ABSENT, []):
            qty = absent_days if r.condition_unit == DeductionRule.ConditionUnit.DAYS else absent_count
            if qty <= Decimal('0'):
                continue
            if DeductionEngine.evaluate_condition(r.operator, qty, r.threshold_min, r.threshold_max):
                amt, unit_rate, label = DeductionEngine._compute_item_amount(
                    r, qty, daily_salary, hourly_salary, monthly_salary, standard_work_hours
                )
                if amt > Decimal('0'):
                    items.append({
                        'rule': r,
                        'category': r.category,
                        'name': f"{r.name} ({qty} {r.get_condition_unit_display()} - {label})",
                        'condition_unit': r.condition_unit,
                        'quantity': qty,
                        'unit_rate': unit_rate,
                        'rate_or_amount': r.rate_or_amount,
                        'calculated_amount': amt,
                    })

        # 2. Evaluate Unpaid Leave rules
        for r in rules_by_cat.get(DeductionRule.Category.UNPAID_LEAVE, []):
            qty = unpaid_leave_days if r.condition_unit == DeductionRule.ConditionUnit.DAYS else unpaid_leave_count
            if qty <= Decimal('0'):
                continue
            if DeductionEngine.evaluate_condition(r.operator, qty, r.threshold_min, r.threshold_max):
                amt, unit_rate, label = DeductionEngine._compute_item_amount(
                    r, qty, daily_salary, hourly_salary, monthly_salary, standard_work_hours
                )
                if amt > Decimal('0'):
                    items.append({
                        'rule': r,
                        'category': r.category,
                        'name': f"{r.name} ({qty} {r.get_condition_unit_display()} - {label})",
                        'condition_unit': r.condition_unit,
                        'quantity': qty,
                        'unit_rate': unit_rate,
                        'rate_or_amount': r.rate_or_amount,
                        'calculated_amount': amt,
                    })

        # 3. Evaluate Late rules (supports per-incident tiering or aggregate hours)
        late_rules = rules_by_cat.get(DeductionRule.Category.LATE, [])
        has_incident_tiered_rules = any(
            r.condition_unit == DeductionRule.ConditionUnit.HOURS and r.operator != DeductionRule.Operator.ALWAYS
            for r in late_rules
        )

        if has_incident_tiered_rules and late_incidents:
            for inc_idx, inc_hrs in enumerate(late_incidents, 1):
                matched_rule = None
                for r in late_rules:
                    if r.condition_unit == DeductionRule.ConditionUnit.HOURS:
                        if DeductionEngine.evaluate_condition(r.operator, inc_hrs, r.threshold_min, r.threshold_max):
                            matched_rule = r
                            break
                if matched_rule:
                    if matched_rule.calc_type in (DeductionRule.CalcType.FIXED_PER_UNIT, DeductionRule.CalcType.FIXED_FLAT):
                        amt = matched_rule.rate_or_amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                        unit_rate = matched_rule.rate_or_amount
                        label = f"${matched_rule.rate_or_amount} fixed"
                        item_qty = Decimal('1.0')
                    else:
                        amt, unit_rate, label = DeductionEngine._compute_item_amount(
                            matched_rule, inc_hrs, daily_salary, hourly_salary, monthly_salary, standard_work_hours
                        )
                        item_qty = inc_hrs

                    if amt > Decimal('0'):
                        items.append({
                            'rule': matched_rule,
                            'category': matched_rule.category,
                            'name': f"{matched_rule.name} (Late #{inc_idx}: {inc_hrs}h - {label})",
                            'condition_unit': matched_rule.condition_unit,
                            'quantity': item_qty,
                            'unit_rate': unit_rate,
                            'rate_or_amount': matched_rule.rate_or_amount,
                            'calculated_amount': amt,
                        })
        else:
            for r in late_rules:
                qty = late_hours if r.condition_unit == DeductionRule.ConditionUnit.HOURS else late_count
                if qty <= Decimal('0'):
                    continue
                if DeductionEngine.evaluate_condition(r.operator, qty, r.threshold_min, r.threshold_max):
                    amt, unit_rate, label = DeductionEngine._compute_item_amount(
                        r, qty, daily_salary, hourly_salary, monthly_salary, standard_work_hours
                    )
                    if amt > Decimal('0'):
                        items.append({
                            'rule': r,
                            'category': r.category,
                            'name': f"{r.name} ({qty} {r.get_condition_unit_display()} - {label})",
                            'condition_unit': r.condition_unit,
                            'quantity': qty,
                            'unit_rate': unit_rate,
                            'rate_or_amount': r.rate_or_amount,
                            'calculated_amount': amt,
                        })

        total = sum((it['calculated_amount'] for it in items), Decimal('0.00')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        return {
            'items': items,
            'total_deductions': total
        }

    @staticmethod
    def _compute_item_amount(rule, quantity, daily_salary, hourly_salary, monthly_salary, standard_work_hours):
        rate = rule.rate_or_amount
        calc = rule.calc_type

        if calc == DeductionRule.CalcType.PERCENT_DAILY:
            unit_rate = daily_salary
            amt = (quantity * daily_salary * (rate / Decimal('100.0'))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            label = f"{rate}% of ${daily_salary}/day"
        elif calc == DeductionRule.CalcType.PERCENT_HOURLY:
            unit_rate = hourly_salary
            amt = (quantity * hourly_salary * (rate / Decimal('100.0'))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            label = f"{rate}% of ${hourly_salary}/hr"
        elif calc == DeductionRule.CalcType.PERCENT_MONTHLY:
            unit_rate = monthly_salary
            amt = (monthly_salary * (rate / Decimal('100.0'))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            label = f"{rate}% of Monthly Basic"
        elif calc == DeductionRule.CalcType.FIXED_PER_UNIT:
            unit_rate = rate
            amt = (quantity * rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            label = f"${rate} per {rule.condition_unit}"
        elif calc == DeductionRule.CalcType.FIXED_FLAT:
            unit_rate = rate
            amt = rate.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            label = f"${rate} flat"
        else:
            unit_rate = Decimal('0.00')
            amt = Decimal('0.00')
            label = ""

        return amt, unit_rate, label


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

        # Evaluate custom other deductions engine
        deduction_results = DeductionEngine.calculate_deductions(
            employee=employee,
            daily_salary=daily_salary,
            monthly_salary=prorated_basic,
            att_metrics=att_metrics,
            period_start=period_start,
            period_end=period_end
        )
        other_deduction = deduction_results['total_deductions']

        gross = prorated_basic + total_allowance + overtime_pay
        tax_rate = get_rule('payroll', 'tax_rate', Decimal('0.10'))
        nssf_rate = get_rule('payroll', 'nssf_rate', Decimal('0.05'))
        tax = (gross * tax_rate).quantize(Decimal('0.01'))
        nssf = (gross * nssf_rate).quantize(Decimal('0.01'))
        total_deduction = tax + nssf + other_deduction
        net = max(Decimal('0.00'), gross - total_deduction)

        payroll, _ = Payroll.objects.update_or_create(
            employee=employee, payroll_period=period_start,
            defaults={
                'basic_salary': prorated_basic,
                'daily_salary': daily_salary,
                'daily_salary_formula': formula_label,
                'attendance_days': att_metrics['attendance_days'],
                'absent_days': att_metrics['absent_days'],
                'unpaid_leave_days': att_metrics['unpaid_leave_days'],
                'late_hours': att_metrics['late_hours'],
                'overtime_hours': att_metrics['overtime_hours'],
                'leave_days': att_metrics['leave_days'],
                'holiday_days': att_metrics['holiday_days'],
                'allowance': total_allowance,
                'overtime': overtime_pay,
                'gross_salary': gross,
                'tax': tax,
                'nssf': nssf,
                'other_deduction': other_deduction,
                'total_deduction': total_deduction,
                'net_salary': net,
                'status': Payroll.Status.DRAFT
            }
        )

        # Sync itemized deduction records
        PayrollDeductionItem.objects.filter(payroll=payroll).delete()
        for it in deduction_results['items']:
            PayrollDeductionItem.objects.create(
                payroll=payroll,
                rule=it.get('rule'),
                category=it['category'],
                name=it['name'],
                condition_unit=it['condition_unit'],
                quantity=it['quantity'],
                unit_rate=it['unit_rate'],
                rate_or_amount=it['rate_or_amount'],
                calculated_amount=it['calculated_amount']
            )

        logger.info(f"Payroll generated: {employee.employee_code} | {period_start} | Daily: {daily_salary} ({formula_label}) | Other Ded: {other_deduction} | Net: {net}")
        return payroll

    @staticmethod
    def recalculate_payroll_totals(payroll):
        payroll.gross_salary = payroll.basic_salary + payroll.allowance + payroll.bonus + payroll.overtime
        tax_rate = get_rule('payroll', 'tax_rate', Decimal('0.10'))
        nssf_rate = get_rule('payroll', 'nssf_rate', Decimal('0.05'))
        payroll.tax = (payroll.gross_salary * tax_rate).quantize(Decimal('0.01'))
        payroll.nssf = (payroll.gross_salary * nssf_rate).quantize(Decimal('0.01'))
        payroll.total_deduction = payroll.tax + payroll.nssf + payroll.other_deduction
        payroll.net_salary = max(Decimal('0.00'), payroll.gross_salary - payroll.total_deduction)
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
