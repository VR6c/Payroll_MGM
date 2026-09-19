import datetime
from django.test import TestCase, Client
from django.urls import reverse
from django.template.context import BaseContext

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
from attendance.models import Attendance


class AttendanceBulkCreateTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Apex Tech")
        self.dept = Department.objects.create(company=self.company, name="Operations")
        self.pos = Position.objects.create(company=self.company, name="Staff")

        self.admin = User.objects.create_superuser(username="admin_bulk", password="password123", role=User.Role.SUPER_ADMIN)

        self.emp1 = Employee.objects.create(
            user=User.objects.create_user(username="emp1", password="password123", role=User.Role.EMPLOYEE),
            company=self.company,
            department=self.dept,
            position=self.pos,
            employee_code="EMP-B01",
            first_name="Alice",
            last_name="Smith",
            email="alice@apex.com",
            join_date=datetime.date(2023, 1, 1),
            basic_salary=3000.00
        )
        self.emp2 = Employee.objects.create(
            user=User.objects.create_user(username="emp2", password="password123", role=User.Role.EMPLOYEE),
            company=self.company,
            department=self.dept,
            position=self.pos,
            employee_code="EMP-B02",
            first_name="Bob",
            last_name="Jones",
            email="bob@apex.com",
            join_date=datetime.date(2023, 1, 1),
            basic_salary=3200.00
        )
        self.emp3 = Employee.objects.create(
            user=User.objects.create_user(username="emp3", password="password123", role=User.Role.EMPLOYEE),
            company=self.company,
            department=self.dept,
            position=self.pos,
            employee_code="EMP-B03",
            first_name="Charlie",
            last_name="Brown",
            email="charlie@apex.com",
            join_date=datetime.date(2023, 1, 1),
            basic_salary=3100.00
        )

        self.client = Client()
        self.client.force_login(self.admin)

    def test_multi_employee_single_date(self):
        """Test marking attendance for multiple employees on a single date."""
        target_date = "2026-09-18"
        post_data = {
            'employees': [self.emp1.id, self.emp2.id, self.emp3.id],
            'date_mode': 'single',
            'date': target_date,
            'status': 'present',
            'check_in_time': '08:30',
            'check_out_time': '17:30',
            'overwrite': 'true'
        }
        response = self.client.post(reverse('attendance:create'), post_data)
        self.assertRedirects(response, reverse('attendance:report'))

        records = Attendance.objects.filter(date=target_date)
        self.assertEqual(records.count(), 3)
        for rec in records:
            self.assertEqual(rec.status, 'present')
            self.assertIsNotNone(rec.check_in)
            self.assertIsNotNone(rec.check_out)
            self.assertEqual(rec.check_in.hour, 8)
            self.assertEqual(rec.check_in.minute, 30)
            self.assertEqual(rec.check_out.hour, 17)
            self.assertEqual(rec.check_out.minute, 30)
            self.assertEqual(rec.working_hours, datetime.timedelta(hours=9))

    def test_multi_employee_date_range_with_weekdays(self):
        """Test marking attendance for multiple employees across a date range with weekday filtering."""
        # 2026-09-14 is Monday, 2026-09-18 is Friday (5 weekdays)
        start_date = "2026-09-14"
        end_date = "2026-09-18"
        post_data = {
            'employees': [self.emp1.id, self.emp2.id],
            'date_mode': 'range',
            'start_date': start_date,
            'end_date': end_date,
            'weekdays': ['0', '1', '2', '3', '4'], # Mon-Fri
            'status': 'present',
            'check_in_time': '08:00',
            'check_out_time': '17:00',
            'overwrite': 'true'
        }
        response = self.client.post(reverse('attendance:create'), post_data)
        self.assertRedirects(response, reverse('attendance:report'))

        # 2 employees * 5 dates = 10 records
        records = Attendance.objects.filter(date__gte=start_date, date__lte=end_date)
        self.assertEqual(records.count(), 10)

    def test_weekend_exclusion(self):
        """Test that weekends are excluded when only Mon-Fri are selected."""
        # 2026-09-18 (Fri), 2026-09-19 (Sat), 2026-09-20 (Sun), 2026-09-21 (Mon)
        start_date = "2026-09-18"
        end_date = "2026-09-21"
        post_data = {
            'employees': [self.emp1.id],
            'date_mode': 'range',
            'start_date': start_date,
            'end_date': end_date,
            'weekdays': ['0', '4'], # Only Mon (0) and Fri (4)
            'status': 'present',
            'check_in_time': '08:00',
            'check_out_time': '17:00'
        }
        response = self.client.post(reverse('attendance:create'), post_data)
        self.assertRedirects(response, reverse('attendance:report'))

        dates_created = list(Attendance.objects.filter(employee=self.emp1).values_list('date', flat=True))
        self.assertEqual(len(dates_created), 2)
        self.assertIn(datetime.date(2026, 9, 18), dates_created) # Fri
        self.assertIn(datetime.date(2026, 9, 21), dates_created) # Mon
        self.assertNotIn(datetime.date(2026, 9, 19), dates_created) # Sat
        self.assertNotIn(datetime.date(2026, 9, 20), dates_created) # Sun

    def test_overwrite_existing_records(self):
        """Test that overwrite updates existing records without throwing integrity errors."""
        target_date = datetime.date(2026, 9, 10)
        # Create initial record
        Attendance.objects.create(
            employee=self.emp1,
            date=target_date,
            status='present'
        )

        post_data = {
            'employees': [self.emp1.id],
            'date_mode': 'single',
            'date': '2026-09-10',
            'status': 'late',
            'check_in_time': '09:15',
            'check_out_time': '17:00',
            'overwrite': 'true'
        }
        response = self.client.post(reverse('attendance:create'), post_data)
        self.assertRedirects(response, reverse('attendance:report'))

        rec = Attendance.objects.get(employee=self.emp1, date=target_date)
        self.assertEqual(rec.status, 'late')
        self.assertEqual(rec.check_in.hour, 9)
        self.assertEqual(rec.check_in.minute, 15)

    def test_skip_existing_when_overwrite_false(self):
        """Test that existing records are preserved when overwrite is false."""
        target_date = datetime.date(2026, 9, 10)
        Attendance.objects.create(
            employee=self.emp1,
            date=target_date,
            status='present'
        )

        post_data = {
            'employees': [self.emp1.id],
            'date_mode': 'single',
            'date': '2026-09-10',
            'status': 'late',
            'check_in_time': '09:15',
            'check_out_time': '17:00',
            'overwrite': 'false'
        }
        response = self.client.post(reverse('attendance:create'), post_data)
        self.assertRedirects(response, reverse('attendance:report'))

        rec = Attendance.objects.get(employee=self.emp1, date=target_date)
        # Should remain 'present'
        self.assertEqual(rec.status, 'present')

    def test_absent_status_no_times(self):
        """Test that absent status does not record check_in and check_out times."""
        target_date = "2026-09-12"
        post_data = {
            'employees': [self.emp1.id],
            'date_mode': 'single',
            'date': target_date,
            'status': 'absent'
        }
        response = self.client.post(reverse('attendance:create'), post_data)
        self.assertRedirects(response, reverse('attendance:report'))

        rec = Attendance.objects.get(employee=self.emp1, date=target_date)
        self.assertEqual(rec.status, 'absent')
        self.assertIsNone(rec.check_in)
        self.assertIsNone(rec.check_out)
        self.assertIsNone(rec.working_hours)

    def test_backward_compatibility_single_employee_post(self):
        """Test backwards compatibility with 'employee' field and datetime-local format."""
        post_data = {
            'employee': str(self.emp1.id),
            'date': '2026-09-15',
            'check_in': '2026-09-15T08:00',
            'check_out': '2026-09-15T17:00',
            'status': 'present'
        }
        response = self.client.post(reverse('attendance:create'), post_data)
        self.assertRedirects(response, reverse('attendance:report'))

        rec = Attendance.objects.filter(employee=self.emp1, date='2026-09-15').first()
        self.assertIsNotNone(rec)
        self.assertEqual(rec.status, 'present')
        self.assertEqual(rec.working_hours, datetime.timedelta(hours=9))

    def test_validation_missing_employee(self):
        """Test error handling when no employees are submitted."""
        post_data = {
            'date_mode': 'single',
            'date': '2026-09-15',
            'status': 'present'
        }
        response = self.client.post(reverse('attendance:create'), post_data)
        self.assertRedirects(response, reverse('attendance:report'))
        self.assertEqual(Attendance.objects.count(), 0)

    def test_validation_invalid_date_range(self):
        """Test error handling when start_date is after end_date."""
        post_data = {
            'employees': [self.emp1.id],
            'date_mode': 'range',
            'start_date': '2026-09-20',
            'end_date': '2026-09-10',
            'status': 'present'
        }
        response = self.client.post(reverse('attendance:create'), post_data)
        self.assertRedirects(response, reverse('attendance:report'))
        self.assertEqual(Attendance.objects.count(), 0)

    def test_attendance_report_date_range_filter(self):
        """Test filtering the attendance report by from_date and to_date."""
        Attendance.objects.create(employee=self.emp1, date=datetime.date(2026, 8, 1), status='present')
        Attendance.objects.create(employee=self.emp1, date=datetime.date(2026, 8, 15), status='present')
        Attendance.objects.create(employee=self.emp1, date=datetime.date(2026, 8, 30), status='present')
        Attendance.objects.create(employee=self.emp1, date=datetime.date(2026, 9, 5), status='present')

        # Filter 2026-08-10 to 2026-08-25 (should only include Aug 15)
        url = reverse('attendance:report') + '?from_date=2026-08-10&to_date=2026-08-25'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        attendances = list(response.context['attendances'])
        self.assertEqual(len(attendances), 1)
        self.assertEqual(attendances[0].date, datetime.date(2026, 8, 15))

    def test_attendance_update_with_time_inputs(self):
        """Test editing an attendance record using HH:MM time inputs."""
        att = Attendance.objects.create(
            employee=self.emp1,
            date=datetime.date(2026, 9, 19),
            status='present'
        )
        post_data = {
            'employee': self.emp1.id,
            'date': '2026-09-19',
            'check_in': '08:30',
            'check_out': '17:30',
            'status': 'present'
        }
        response = self.client.post(reverse('attendance:update', args=[att.id]), post_data)
        self.assertRedirects(response, reverse('attendance:report'))
        att.refresh_from_db()
        self.assertIsNotNone(att.check_in)
        self.assertIsNotNone(att.check_out)
        self.assertEqual(att.check_in.hour, 8)
        self.assertEqual(att.check_in.minute, 30)
        self.assertEqual(att.check_out.hour, 17)
        self.assertEqual(att.check_out.minute, 30)
        self.assertEqual(att.working_hours, datetime.timedelta(hours=9))

    def test_attendance_update_absent_clears_times(self):
        """Test editing an attendance record to absent clears check-in/out and working hours."""
        att = Attendance.objects.create(
            employee=self.emp1,
            date=datetime.date(2026, 9, 19),
            status='present'
        )
        post_data = {
            'employee': self.emp1.id,
            'date': '2026-09-19',
            'check_in': '08:00',
            'check_out': '17:00',
            'status': 'absent'
        }
        response = self.client.post(reverse('attendance:update', args=[att.id]), post_data)
        self.assertRedirects(response, reverse('attendance:report'))
        att.refresh_from_db()
        self.assertEqual(att.status, 'absent')
        self.assertIsNone(att.check_in)
        self.assertIsNone(att.check_out)
        self.assertIsNone(att.working_hours)

    def test_attendance_update_overnight_shift(self):
        """Test editing an attendance record with overnight hours."""
        att = Attendance.objects.create(
            employee=self.emp1,
            date=datetime.date(2026, 9, 19),
            status='present'
        )
        post_data = {
            'employee': self.emp1.id,
            'date': '2026-09-19',
            'check_in': '22:00',
            'check_out': '06:00',
            'status': 'present'
        }
        response = self.client.post(reverse('attendance:update', args=[att.id]), post_data)
        self.assertRedirects(response, reverse('attendance:report'))
        att.refresh_from_db()
        self.assertEqual(att.check_out.date(), datetime.date(2026, 9, 20))
        self.assertEqual(att.working_hours, datetime.timedelta(hours=8))

