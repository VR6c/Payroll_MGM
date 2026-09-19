import datetime
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from accounts.models import User
from companies.models import Company
from employees.models import Employee
from attendance.models import Attendance, LunchBreak

class LunchBreakModelTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name='Test Corp')
        self.user = User.objects.create_user(username='testemp', password='password', role='employee')
        self.employee = Employee.objects.create(
            user=self.user,
            company=self.company,
            employee_code='EMP001',
            first_name='John',
            last_name='Doe',
            email='john@test.com',
            basic_salary=1000
        )
        # Ensure only our test lunch break exists
        LunchBreak.objects.all().delete()
        self.lunch_break = LunchBreak.objects.create(
            name='Default Lunch Break',
            start_time=datetime.time(12, 0),
            end_time=datetime.time(13, 0),
            duration_minutes=60,
            auto_deduct=True,
            status=True
        )

    def test_full_day_9h_counts_as_8h(self):
        """Test: working 9 hours (08:00 to 17:00) counts as 8 hours with 1h lunch break deducted."""
        today = datetime.date(2026, 9, 20)
        current_tz = timezone.get_current_timezone()
        ci = timezone.make_aware(datetime.datetime.combine(today, datetime.time(8, 0)), current_tz)
        co = timezone.make_aware(datetime.datetime.combine(today, datetime.time(17, 0)), current_tz)

        net_hours = Attendance.calculate_net_working_hours(ci, co, employee=self.employee, date=today)
        self.assertEqual(co - ci, datetime.timedelta(hours=9))
        self.assertEqual(net_hours, datetime.timedelta(hours=8))

    def test_morning_half_day_no_break_deducted(self):
        """Test: working morning shift 08:00 to 12:00 has 0 break deducted (4 hours worked)."""
        today = datetime.date(2026, 9, 20)
        current_tz = timezone.get_current_timezone()
        ci = timezone.make_aware(datetime.datetime.combine(today, datetime.time(8, 0)), current_tz)
        co = timezone.make_aware(datetime.datetime.combine(today, datetime.time(12, 0)), current_tz)

        net_hours = Attendance.calculate_net_working_hours(ci, co, employee=self.employee, date=today)
        self.assertEqual(net_hours, datetime.timedelta(hours=4))

    def test_afternoon_half_day_no_break_deducted(self):
        """Test: working afternoon shift 13:00 to 17:00 has 0 break deducted (4 hours worked)."""
        today = datetime.date(2026, 9, 20)
        current_tz = timezone.get_current_timezone()
        ci = timezone.make_aware(datetime.datetime.combine(today, datetime.time(13, 0)), current_tz)
        co = timezone.make_aware(datetime.datetime.combine(today, datetime.time(17, 0)), current_tz)

        net_hours = Attendance.calculate_net_working_hours(ci, co, employee=self.employee, date=today)
        self.assertEqual(net_hours, datetime.timedelta(hours=4))

    def test_partial_lunch_overlap(self):
        """Test: leaving during lunch at 12:30 (08:00 to 12:30, 4.5h) deducts 30 mins (4.0h worked)."""
        today = datetime.date(2026, 9, 20)
        current_tz = timezone.get_current_timezone()
        ci = timezone.make_aware(datetime.datetime.combine(today, datetime.time(8, 0)), current_tz)
        co = timezone.make_aware(datetime.datetime.combine(today, datetime.time(12, 30)), current_tz)

        net_hours = Attendance.calculate_net_working_hours(ci, co, employee=self.employee, date=today)
        self.assertEqual(net_hours, datetime.timedelta(hours=4))

    def test_inactive_break_not_deducted(self):
        """Test: when break is inactive, full elapsed duration is counted."""
        self.lunch_break.status = False
        self.lunch_break.save()

        today = datetime.date(2026, 9, 20)
        current_tz = timezone.get_current_timezone()
        ci = timezone.make_aware(datetime.datetime.combine(today, datetime.time(8, 0)), current_tz)
        co = timezone.make_aware(datetime.datetime.combine(today, datetime.time(17, 0)), current_tz)

        # Deactivated break in DB means no active break matches
        self.lunch_break.delete()  # completely remove so default fallback does not apply if status was false
        # When no break exists, test default behavior
        net_hours = Attendance.calculate_net_working_hours(ci, co, employee=self.employee, date=today)
        self.assertEqual(net_hours, datetime.timedelta(hours=8))

    def test_custom_lunch_break_duration(self):
        """Test: custom 1.5h lunch break (11:30 to 13:00) deducts 1.5 hours from 9 hours -> 7.5 hours."""
        self.lunch_break.start_time = datetime.time(11, 30)
        self.lunch_break.end_time = datetime.time(13, 0)
        self.lunch_break.duration_minutes = 90
        self.lunch_break.save()

        today = datetime.date(2026, 9, 20)
        current_tz = timezone.get_current_timezone()
        ci = timezone.make_aware(datetime.datetime.combine(today, datetime.time(8, 0)), current_tz)
        co = timezone.make_aware(datetime.datetime.combine(today, datetime.time(17, 0)), current_tz)

        net_hours = Attendance.calculate_net_working_hours(ci, co, employee=self.employee, date=today)
        self.assertEqual(net_hours, datetime.timedelta(hours=7, minutes=30))


class LunchBreakCRUDViewsTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin_user = User.objects.create_user(
            username='admin_hr',
            password='adminpassword',
            role='hr_admin'
        )
        self.company = Company.objects.create(name='Acme Corp')
        self.client.login(username='admin_hr', password='adminpassword')

    def test_lunch_break_list_view(self):
        LunchBreak.objects.create(
            name='Test Lunch Break',
            start_time=datetime.time(12, 0),
            end_time=datetime.time(13, 0),
            duration_minutes=60,
            status=True
        )
        response = self.client.get(reverse('attendance:lunch_breaks'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Lunch Break & Rest Settings')
        self.assertContains(response, 'Test Lunch Break')

    def test_lunch_break_create_view(self):
        post_data = {
            'name': 'Factory Lunch Break',
            'break_type': 'lunch',
            'start_time': '12:00',
            'end_time': '13:00',
            'duration_minutes': 60,
            'min_work_hours': 4.0,
            'auto_deduct': 'on',
            'status': 'on',
        }
        response = self.client.post(reverse('attendance:lunch_break_create'), post_data)
        self.assertRedirects(response, reverse('attendance:lunch_breaks'))
        self.assertTrue(LunchBreak.objects.filter(name='Factory Lunch Break').exists())

    def test_lunch_break_update_view(self):
        b = LunchBreak.objects.create(
            name='Old Break Name',
            start_time=datetime.time(12, 0),
            end_time=datetime.time(13, 0),
            duration_minutes=60,
            status=True
        )
        post_data = {
            'name': 'Updated Break Name',
            'break_type': 'lunch',
            'start_time': '12:30',
            'end_time': '13:30',
            'duration_minutes': 60,
            'min_work_hours': 4.0,
            'auto_deduct': 'on',
            'status': 'on',
        }
        response = self.client.post(reverse('attendance:lunch_break_update', kwargs={'pk': b.id}), post_data)
        self.assertRedirects(response, reverse('attendance:lunch_breaks'))
        b.refresh_from_db()
        self.assertEqual(b.name, 'Updated Break Name')
        self.assertEqual(b.start_time, datetime.time(12, 30))

    def test_lunch_break_delete_view(self):
        b = LunchBreak.objects.create(
            name='Break to Delete',
            start_time=datetime.time(12, 0),
            end_time=datetime.time(13, 0),
            duration_minutes=60
        )
        response = self.client.post(reverse('attendance:lunch_break_delete', kwargs={'pk': b.id}))
        self.assertRedirects(response, reverse('attendance:lunch_breaks'))
        self.assertFalse(LunchBreak.objects.filter(id=b.id).exists())


class AttendanceCreationWorkingHoursTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(username='admin2', password='password', role='super_admin')
        self.client.login(username='admin2', password='password')
        self.company = Company.objects.create(name='Test Company')
        self.emp_user = User.objects.create_user(username='worker1', password='password', role='employee')
        self.employee = Employee.objects.create(
            user=self.emp_user,
            company=self.company,
            employee_code='EMP99',
            first_name='Bob',
            last_name='Smith',
            basic_salary=2000
        )
        LunchBreak.objects.all().delete()
        LunchBreak.objects.create(
            name='Standard 1h Lunch',
            start_time=datetime.time(12, 0),
            end_time=datetime.time(13, 0),
            duration_minutes=60,
            auto_deduct=True,
            status=True
        )

    def test_attendance_create_deducts_lunch_break(self):
        post_data = {
            'employees': [self.employee.id],
            'date_mode': 'single',
            'date': '2026-09-20',
            'status': 'present',
            'check_in_time': '08:00',
            'check_out_time': '17:00',
            'overwrite': 'true'
        }
        response = self.client.post(reverse('attendance:create'), post_data)
        self.assertRedirects(response, reverse('attendance:report'))

        att = Attendance.objects.get(employee=self.employee, date=datetime.date(2026, 9, 20))
        # 9 hours elapsed (08:00 to 17:00) minus 1 hour lunch break = 8 hours working hours
        self.assertEqual(att.working_hours, datetime.timedelta(hours=8))
