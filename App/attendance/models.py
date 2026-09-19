from django.db import models
from employees.models import Employee

class WorkSchedule(models.Model):
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    start_time = models.TimeField()
    end_time = models.TimeField()
    late_after = models.TimeField()
    early_leave_before = models.TimeField()
    status = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} ({self.start_time}-{self.end_time})"

class Attendance(models.Model):
    class Status(models.TextChoices):
        PRESENT = 'present', 'Present'
        LATE = 'late', 'Late'
        ABSENT = 'absent', 'Absent'
        EARLY_LEAVE = 'early_leave', 'Early Leave'
        OVERTIME = 'overtime', 'Overtime'

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='attendances')
    date = models.DateField()
    check_in = models.DateTimeField(null=True, blank=True)
    check_out = models.DateTimeField(null=True, blank=True)
    working_hours = models.DurationField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PRESENT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('employee', 'date')
        indexes = [models.Index(fields=['date', 'status'])]

    def calculate_working_hours(self):
        if self.check_in and self.check_out:
            self.working_hours = self.check_out - self.check_in
            if self.pk:
                self.save(update_fields=['working_hours'])


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

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='employee_schedules')
    schedule_type = models.CharField(max_length=20, choices=ScheduleType.choices, default=ScheduleType.FLEXIBLE)
    day_of_week = models.IntegerField(choices=DAY_CHOICES)
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    start_time2 = models.TimeField(null=True, blank=True)
    end_time2 = models.TimeField(null=True, blank=True)
    is_half_day = models.BooleanField(default=False)
    is_work_day = models.BooleanField(default=True)
    shift_label = models.CharField(max_length=100, default='Full Day')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

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


