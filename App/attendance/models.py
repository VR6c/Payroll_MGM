import datetime
from typing import Any
from django.db import models
from django.utils import timezone
from employees.models import Employee

class LunchBreak(models.Model):
    class BreakType(models.TextChoices):
        LUNCH = 'lunch', 'Lunch Break'
        TEA = 'tea', 'Tea Break'
        CUSTOM = 'custom', 'Custom Break'

    company: Any = models.ForeignKey(
        'companies.Company',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='lunch_breaks',
        help_text="Optional company assignment. If blank, applies to all companies."
    )
    name: Any = models.CharField(max_length=100, default='Lunch Break')
    break_type: Any = models.CharField(max_length=20, choices=BreakType.choices, default=BreakType.LUNCH)
    start_time: Any = models.TimeField(default=datetime.time(12, 0), help_text="Start time of the break, e.g. 12:00")
    end_time: Any = models.TimeField(default=datetime.time(13, 0), help_text="End time of the break, e.g. 13:00")
    duration_minutes: Any = models.PositiveIntegerField(
        default=60,
        help_text="Duration in minutes (e.g. 60 for 1 hour)"
    )
    auto_deduct: Any = models.BooleanField(
        default=True,
        help_text="Automatically deduct this break from working hours if shift overlaps"
    )
    min_work_hours: Any = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=4.00,
        help_text="Minimum elapsed hours worked to qualify for break deduction"
    )
    status: Any = models.BooleanField(default=True, help_text="Active / Inactive status")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = models.Manager()

    class Meta:
        ordering = ['start_time', 'name']
        verbose_name = 'Lunch Break'
        verbose_name_plural = 'Lunch Breaks'

    def __str__(self):
        st = self.start_time.strftime('%I:%M %p') if self.start_time else ''
        et = self.end_time.strftime('%I:%M %p') if self.end_time else ''
        return f"{self.name} ({st} - {et}, {self.duration_minutes}m)"

    def get_overlap_duration(self, check_in_dt, check_out_dt, target_date=None):
        """
        Calculate the exact timedelta overlap between the work interval [check_in_dt, check_out_dt]
        and this break window on target_date.
        """
        if not self.auto_deduct or not self.status:
            return datetime.timedelta(0)
        if not check_in_dt or not check_out_dt or check_out_dt <= check_in_dt:
            return datetime.timedelta(0)

        elapsed = check_out_dt - check_in_dt
        if self.min_work_hours and (elapsed.total_seconds() / 3600.0) < float(self.min_work_hours):
            return datetime.timedelta(0)

        if not target_date:
            target_date = timezone.localdate(check_in_dt) if timezone.is_aware(check_in_dt) else check_in_dt.date()

        tz = check_in_dt.tzinfo if timezone.is_aware(check_in_dt) else None

        if self.start_time and self.end_time:
            naive_start = datetime.datetime.combine(target_date, self.start_time)
            naive_end = datetime.datetime.combine(target_date, self.end_time)

            if self.end_time < self.start_time:
                naive_end += datetime.timedelta(days=1)

            if tz:
                break_start = timezone.make_aware(naive_start, tz) if timezone.is_naive(naive_start) else naive_start
                break_end = timezone.make_aware(naive_end, tz) if timezone.is_naive(naive_end) else naive_end
            else:
                break_start = naive_start
                break_end = naive_end

            overlap_start = max(check_in_dt, break_start)
            overlap_end = min(check_out_dt, break_end)

            if overlap_end > overlap_start:
                return overlap_end - overlap_start
            return datetime.timedelta(0)
        elif self.duration_minutes:
            break_td = datetime.timedelta(minutes=self.duration_minutes)
            return min(elapsed, break_td)

        return datetime.timedelta(0)


class WorkSchedule(models.Model):
    company: Any = models.ForeignKey('companies.Company', on_delete=models.CASCADE)
    name: Any = models.CharField(max_length=100)
    start_time: Any = models.TimeField()
    end_time: Any = models.TimeField()
    late_after: Any = models.TimeField()
    early_leave_before: Any = models.TimeField()
    status: Any = models.BooleanField(default=True)

    objects = models.Manager()

    def __str__(self):
        return f"{self.name} ({self.start_time}-{self.end_time})"

class Attendance(models.Model):
    class Status(models.TextChoices):
        PRESENT = 'present', 'Present'
        LATE = 'late', 'Late'
        ABSENT = 'absent', 'Absent'
        CHECKOUT_EARLY = 'checkout_early', 'Checkout Early'
        OVERTIME = 'overtime', 'Overtime'

    employee: Any = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='attendances')
    date: Any = models.DateField()
    check_in: Any = models.DateTimeField(null=True, blank=True)
    check_out: Any = models.DateTimeField(null=True, blank=True)
    working_hours: Any = models.DurationField(null=True, blank=True)
    status: Any = models.CharField(max_length=20, choices=Status.choices, default=Status.PRESENT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = models.Manager()

    class Meta:
        unique_together = ('employee', 'date')
        indexes = [models.Index(fields=['date', 'status'])]

    @classmethod
    def calculate_net_working_hours(cls, check_in_dt, check_out_dt, employee=None, date=None):
        """
        Calculate working hours between check_in and check_out, subtracting any active
        lunch break / break time overlap (e.g. 9 hours elapsed - 1 hour lunch = 8 hours).
        """
        if not check_in_dt or not check_out_dt or check_out_dt <= check_in_dt:
            return None

        raw_duration = check_out_dt - check_in_dt
        if not date:
            date = timezone.localdate(check_in_dt) if timezone.is_aware(check_in_dt) else check_in_dt.date()

        # Query active breaks
        breaks_qs = LunchBreak.objects.filter(status=True, auto_deduct=True)
        if employee and getattr(employee, 'company_id', None):
            breaks_qs = breaks_qs.filter(
                models.Q(company_id=employee.company_id) | models.Q(company__isnull=True)
            )
        else:
            breaks_qs = breaks_qs.filter(company__isnull=True)

        breaks = list(breaks_qs)
        if not breaks:
            default_break = LunchBreak(
                name="Lunch Break",
                start_time=datetime.time(12, 0),
                end_time=datetime.time(13, 0),
                duration_minutes=60,
                auto_deduct=True,
                status=True
            )
            breaks = [default_break]

        total_deduction = datetime.timedelta(0)
        for b in breaks:
            deduct = b.get_overlap_duration(check_in_dt, check_out_dt, target_date=date)
            total_deduction += deduct

        net_duration = raw_duration - total_deduction
        return max(datetime.timedelta(0), net_duration)

    @property
    def get_working_hours(self):
        if self.check_in and self.check_out:
            return self.calculate_net_working_hours(
                self.check_in, self.check_out, employee=self.employee, date=self.date
            )
        return self.working_hours

    def calculate_working_hours(self):
        if self.check_in and self.check_out:
            self.working_hours = self.calculate_net_working_hours(
                self.check_in, self.check_out, employee=self.employee, date=self.date
            )
            if self.pk:
                super().save(update_fields=['working_hours'])

    def save(self, *args, **kwargs):
        if self.check_in and self.check_out:
            self.working_hours = self.calculate_net_working_hours(
                self.check_in, self.check_out, employee=self.employee, date=self.date
            )
        elif not self.check_in or not self.check_out:
            self.working_hours = None
        super().save(*args, **kwargs)


class EmployeeSchedule(models.Model):
    class ScheduleType(models.TextChoices):
        FLEXIBLE = 'flexible', 'Flexible'
        STANDARD = 'standard', 'Standard'

    DAY_CHOICES = [
        (0, 'Monday'),
        (1, 'Tuesday'),
        (2, 'Wednesday'),
        (3, 'Thursday'),
        (4, 'Friday'),
        (5, 'Saturday'),
        (6, 'Sunday'),
    ]

    employee: Any = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='employee_schedules')
    schedule_type: Any = models.CharField(max_length=20, choices=ScheduleType.choices, default=ScheduleType.FLEXIBLE)
    day_of_week: Any = models.IntegerField(choices=DAY_CHOICES)
    start_time: Any = models.TimeField(null=True, blank=True)
    end_time: Any = models.TimeField(null=True, blank=True)
    start_time2: Any = models.TimeField(null=True, blank=True)
    end_time2: Any = models.TimeField(null=True, blank=True)
    is_half_day: Any = models.BooleanField(default=False)
    is_work_day: Any = models.BooleanField(default=True)
    shift_label: Any = models.CharField(max_length=100, default='Full Day')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = models.Manager()

    class Meta:
        unique_together = ('employee', 'day_of_week')
        ordering = ['employee', 'day_of_week']
        indexes = [
            models.Index(fields=['employee', 'day_of_week']),
            models.Index(fields=['is_work_day']),
        ]

    def __str__(self):
        return f"{self.employee} - {self.get_day_of_week_display()} ({self.start_time}-{self.end_time})"

    @classmethod
    def get_weekly_matrices_for_employees(cls, employees):
        emp_ids = [e.pk for e in employees]
        schedules_map = {}
        if emp_ids:
            scheds = cls.objects.filter(employee_id__in=emp_ids)
            for s in scheds:
                if s.employee_id not in schedules_map:
                    schedules_map[s.employee_id] = {}
                schedules_map[s.employee_id][s.day_of_week] = s

        days_name = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        for emp in employees:
            e_map = schedules_map.get(emp.pk, {})
            weekly = []
            for d_idx in range(7):
                s_obj = e_map.get(d_idx)
                if s_obj:
                    is_work = s_obj.is_work_day
                    is_half = s_obj.is_half_day
                    st1 = s_obj.start_time.strftime('%I:%M %p') if s_obj.start_time else '08:00 AM'
                    et1 = s_obj.end_time.strftime('%I:%M %p') if s_obj.end_time else ('12:00 PM' if (is_half or s_obj.start_time2) else '05:00 PM')
                    st2 = s_obj.start_time2.strftime('%I:%M %p') if s_obj.start_time2 else '01:00 PM'
                    et2 = s_obj.end_time2.strftime('%I:%M %p') if s_obj.end_time2 else '05:00 PM'
                    has_shift2 = bool(s_obj.start_time2 and s_obj.end_time2) or (is_work and not is_half)

                    weekly.append({
                        'day_idx': d_idx,
                        'day_name': days_name[d_idx],
                        'is_work_day': is_work,
                        'is_half_day': is_half,
                        'start_time': st1,
                        'end_time': et1,
                        'start_time2': st2 if has_shift2 else '',
                        'end_time2': et2 if has_shift2 else '',
                        'raw_start': s_obj.start_time.strftime('%H:%M') if s_obj.start_time else '08:00',
                        'raw_end': s_obj.end_time.strftime('%H:%M') if s_obj.end_time else ('12:00' if is_half else '17:00'),
                        'raw_start2': s_obj.start_time2.strftime('%H:%M') if s_obj.start_time2 else '13:00',
                        'raw_end2': s_obj.end_time2.strftime('%H:%M') if s_obj.end_time2 else '17:00',
                        'shift_label': 'Half Day' if is_half else ('Full Day' if is_work else 'Holiday'),
                    })
                else:
                    is_work = (d_idx < 5)
                    weekly.append({
                        'day_idx': d_idx,
                        'day_name': days_name[d_idx],
                        'is_work_day': is_work,
                        'is_half_day': False,
                        'start_time': '08:00 AM' if is_work else '',
                        'end_time': '12:00 PM' if is_work else '',
                        'start_time2': '01:00 PM' if is_work else '',
                        'end_time2': '05:00 PM' if is_work else '',
                        'raw_start': '08:00',
                        'raw_end': '12:00',
                        'raw_start2': '13:00',
                        'raw_end2': '17:00',
                        'shift_label': 'Full Day' if is_work else 'Holiday',
                    })
            emp.weekly_matrix = weekly
        return employees


