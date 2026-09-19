import datetime
import logging
from django.utils import timezone
from .models import Attendance, WorkSchedule, EmployeeSchedule
from activities.services import log_activity

logger = logging.getLogger('attendance')

class AttendanceService:
    @staticmethod
    def get_scheduled_hours(employee, date):
        """
        Return (expected_start, expected_end) for an employee on a given date.
        Uses EmployeeSchedule first, falls back to WorkSchedule, then standard (08:00, 17:00).
        """
        dow = date.weekday()
        sched = EmployeeSchedule.objects.filter(employee=employee, day_of_week=dow).first()
        if sched and sched.is_work_day:
            start_t = sched.start_time or datetime.time(8, 0)
            if sched.is_half_day:
                end_t = sched.end_time or datetime.time(12, 0)
            elif sched.end_time2:
                end_t = sched.end_time2
            elif sched.end_time:
                end_t = sched.end_time
            else:
                end_t = datetime.time(17, 0)
            return start_t, end_t

        # Fallback to WorkSchedule
        ws = WorkSchedule.objects.filter(company=employee.company, status=True).first()
        if ws:
            return ws.start_time, ws.end_time

        # Default company hours (8:00 AM - 5:00 PM)
        return datetime.time(8, 0), datetime.time(17, 0)

    @classmethod
    def determine_status(cls, employee, date, check_in_dt, check_out_dt, user_status=None):
        """
        Determine appropriate attendance status based on check-in and check-out times.
        Auto-evaluates early checkout against scheduled shift end.
        """
        if user_status == 'absent' or (not check_in_dt and not check_out_dt):
            return Attendance.Status.ABSENT

        if user_status == 'checkout_early' or user_status == 'early_leave':
            return Attendance.Status.CHECKOUT_EARLY

        expected_start, expected_end = cls.get_scheduled_hours(employee, date)

        ci_time = check_in_dt.time() if check_in_dt else None
        co_time = check_out_dt.time() if check_out_dt else None

        # Early departure check (e.g., leaving at 16:24 when shift ends at 17:00)
        if co_time and co_time < expected_end:
            return Attendance.Status.CHECKOUT_EARLY

        # If user explicitly requested a status (like 'present', 'overtime', 'late'), respect it
        if user_status and user_status not in ('', None):
            return user_status

        # If no user status provided, auto-evaluate
        if ci_time and ci_time > expected_start:
            return Attendance.Status.LATE

        if co_time and co_time > expected_end:
            return Attendance.Status.OVERTIME

        return Attendance.Status.PRESENT

    @classmethod
    def check_in(cls, employee, user):
        today = timezone.localdate()
        if Attendance.objects.filter(employee=employee, date=today).exists():
            raise ValueError("Already checked in today")
        now = timezone.now()
        expected_start, expected_end = cls.get_scheduled_hours(employee, today)
        status = Attendance.Status.PRESENT
        if now.time() > expected_start:
            status = Attendance.Status.LATE
        att = Attendance.objects.create(employee=employee, date=today, check_in=now, status=status)
        log_activity(user, employee, 'ATTENDANCE', 'CHECK_IN', f'Checked in at {now.strftime("%H:%M")}')
        logger.info(f"Check-in: {employee.employee_code} at {now}")
        return att

    @classmethod
    def check_out(cls, employee, user):
        today = timezone.localdate()
        att = Attendance.objects.filter(employee=employee, date=today).first()
        if not att or not att.check_in:
            raise ValueError("Must check in before checking out")
        if att.check_out:
            raise ValueError("Already checked out today")
        now = timezone.now()
        att.check_out = now
        expected_start, expected_end = cls.get_scheduled_hours(employee, today)
        if now.time() < expected_end:
            att.status = Attendance.Status.CHECKOUT_EARLY
        elif now.time() > expected_end:
            att.status = Attendance.Status.OVERTIME
        att.calculate_working_hours()
        att.save()
        log_activity(user, employee, 'ATTENDANCE', 'CHECK_OUT', f'Checked out at {now.strftime("%H:%M")}')
        logger.info(f"Check-out: {employee.employee_code} at {now}")
        return att


import datetime
from employees.models import Employee
from .models import EmployeeSchedule

class ScheduleService:
    """Service handling employee workday and shift schedule management."""

    DAYS_KEYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']

    @staticmethod
    def _parse_time(time_str, default_time):
        if not time_str:
            return default_time
        try:
            return datetime.datetime.strptime(time_str, '%H:%M').time()
        except (ValueError, TypeError):
            return default_time

    @classmethod
    def save_employee_schedule(cls, data):
        employee_ids = data.get('employee_ids', [])
        if isinstance(employee_ids, str):
            if employee_ids == 'all':
                employee_ids = list(Employee.objects.filter(status='active').values_list('id', flat=True))
            else:
                employee_ids = [int(x) for x in employee_ids.split(',') if x and x.isdigit()]
        elif isinstance(employee_ids, int):
            employee_ids = [employee_ids]

        if not employee_ids:
            raise ValueError("No employee selected.")

        schedule_type = data.get('schedule_type', 'flexible')
        employees = Employee.objects.filter(id__in=employee_ids)

        for emp in employees:
            if schedule_type == 'flexible':
                for d_idx, d_name in enumerate(cls.DAYS_KEYS):
                    d_data = data.get('days', {}).get(d_name, {})
                    is_work = bool(d_data.get('is_work', False))
                    is_half = bool(d_data.get('is_half', False))
                    start_str = d_data.get('start_time', '08:00')
                    end_str = d_data.get('end_time', '12:00')
                    start2_str = d_data.get('start_time2', '13:00')
                    end2_str = d_data.get('end_time2', '17:00')

                    st_val, et_val, st2_val, et2_val = None, None, None, None
                    if is_work:
                        st_val = cls._parse_time(start_str, datetime.time(8, 0))
                        et_val = cls._parse_time(end_str, datetime.time(12, 0))
                        if not is_half:
                            st2_val = cls._parse_time(start2_str, datetime.time(13, 0))
                            et2_val = cls._parse_time(end2_str, datetime.time(17, 0))

                    shift_label = 'Half Day' if is_half else ('Full Day' if is_work else 'Holiday')

                    EmployeeSchedule.objects.update_or_create(
                        employee=emp,
                        day_of_week=d_idx,
                        defaults={
                            'schedule_type': EmployeeSchedule.ScheduleType.FLEXIBLE,
                            'is_work_day': is_work,
                            'is_half_day': is_half,
                            'start_time': st_val,
                            'end_time': et_val,
                            'start_time2': st2_val,
                            'end_time2': et2_val,
                            'shift_label': shift_label,
                        }
                    )
            else:
                start_str = data.get('start_time', '08:00')
                end_str = data.get('end_time', '12:00')
                start2_str = data.get('start_time2', '13:00')
                end2_str = data.get('end_time2', '17:00')
                is_half = bool(data.get('is_half', False))
                active_days = data.get('active_days', [])

                st_val = cls._parse_time(start_str, datetime.time(8, 0))
                et_val = cls._parse_time(end_str, datetime.time(12, 0))
                st2_val = cls._parse_time(start2_str, datetime.time(13, 0)) if not is_half else None
                et2_val = cls._parse_time(end2_str, datetime.time(17, 0)) if not is_half else None

                for d_idx, d_name in enumerate(cls.DAYS_KEYS):
                    is_work = (d_name in active_days or d_idx in active_days or str(d_idx) in active_days)
                    shift_label = 'Half Day' if (is_work and is_half) else ('Full Day' if is_work else 'Holiday')

                    EmployeeSchedule.objects.update_or_create(
                        employee=emp,
                        day_of_week=d_idx,
                        defaults={
                            'schedule_type': EmployeeSchedule.ScheduleType.STANDARD,
                            'is_work_day': is_work,
                            'is_half_day': is_half if is_work else False,
                            'start_time': st_val if is_work else None,
                            'end_time': et_val if is_work else None,
                            'start_time2': st2_val if (is_work and not is_half) else None,
                            'end_time2': et2_val if (is_work and not is_half) else None,
                            'shift_label': shift_label,
                        }
                    )
        return len(employees)

    @classmethod
    def get_employee_schedule_data(cls, employee):
        scheds = EmployeeSchedule.objects.filter(employee=employee)
        s_map = {s.day_of_week: s for s in scheds}
        days_data = {}
        schedule_type = 'flexible'

        for d_idx, d_name in enumerate(cls.DAYS_KEYS):
            s_obj = s_map.get(d_idx)
            if s_obj:
                schedule_type = s_obj.schedule_type
                days_data[d_name] = {
                    'is_work': s_obj.is_work_day,
                    'is_half': s_obj.is_half_day,
                    'start_time': s_obj.start_time.strftime('%H:%M') if s_obj.start_time else '08:00',
                    'end_time': s_obj.end_time.strftime('%H:%M') if s_obj.end_time else '12:00',
                    'start_time2': s_obj.start_time2.strftime('%H:%M') if s_obj.start_time2 else '13:00',
                    'end_time2': s_obj.end_time2.strftime('%H:%M') if s_obj.end_time2 else '17:00',
                }
            else:
                days_data[d_name] = {
                    'is_work': (d_idx < 5),
                    'is_half': False,
                    'start_time': '08:00',
                    'end_time': '12:00',
                    'start_time2': '13:00',
                    'end_time2': '17:00',
                }

        return {
            'employee': {
                'id': employee.pk,
                'name': f"{employee.first_name} {employee.last_name}".strip(),
                'position': employee.position.name if employee.position else '',
                'avatar': employee.photo.url if employee.photo else '',
            },
            'schedule_type': schedule_type,
            'days': days_data,
        }

