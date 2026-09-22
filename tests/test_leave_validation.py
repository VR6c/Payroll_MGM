import datetime
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from accounts.models import User
from tests.factories import EmployeeFactory, CompanyFactory, UserFactory
from leave.models import LeaveType, LeaveRequest, LeavePeriod
from leave.views import parse_and_validate_leave_periods, check_periods_overlap


class LeaveValidationTestCase(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.user = UserFactory(role='super_admin', is_superuser=True)
        self.user.set_password('password123')
        self.user.save()
        self.employee = EmployeeFactory(company=self.company)
        self.leave_type = LeaveType.objects.create(
            company=self.company,
            name='Annual Leave',
            default_days=15,
            paid=True,
            status=True
        )
        self.client = Client()
        self.client.login(username=self.user.username, password='password123')

    def test_duplicate_dates_in_same_request_fails(self):
        """Two periods for the exact same date (like user screenshot) must fail validation."""
        post_data = {
            'periods-0-start_date': '2026-09-22',
            'periods-0-end_date': '2026-09-22',
            'periods-0-days': '1.0',
            'periods-0-start_time': '',
            'periods-0-end_time': '',
            'periods-1-start_date': '2026-09-22',
            'periods-1-end_date': '2026-09-22',
            'periods-1-days': '1.0',
            'periods-1-start_time': '',
            'periods-1-end_time': '',
        }
        cleaned, err = parse_and_validate_leave_periods(post_data, employee=self.employee)
        self.assertIsNone(cleaned)
        self.assertIn("Duplicate date detected", err)

    def test_overlapping_date_ranges_in_same_request_fails(self):
        """Periods with overlapping date ranges must fail validation."""
        post_data = {
            'periods-0-start_date': '2026-09-20',
            'periods-0-end_date': '2026-09-25',
            'periods-0-days': '6.0',
            'periods-1-start_date': '2026-09-23',
            'periods-1-end_date': '2026-09-28',
            'periods-1-days': '6.0',
        }
        cleaned, err = parse_and_validate_leave_periods(post_data, employee=self.employee)
        self.assertIsNone(cleaned)
        self.assertIn("Overlapping periods detected", err)

    def test_overlapping_hours_on_same_date_fails(self):
        """Periods on same date with overlapping hours must fail validation."""
        post_data = {
            'periods-0-start_date': '2026-09-22',
            'periods-0-end_date': '2026-09-22',
            'periods-0-days': '0.5',
            'periods-0-start_time': '08:00',
            'periods-0-end_time': '12:00',
            'periods-1-start_date': '2026-09-22',
            'periods-1-end_date': '2026-09-22',
            'periods-1-days': '0.5',
            'periods-1-start_time': '10:00',
            'periods-1-end_time': '14:00',
        }
        cleaned, err = parse_and_validate_leave_periods(post_data, employee=self.employee)
        self.assertIsNone(cleaned)
        self.assertIn("Overlapping hours detected", err)

    def test_non_overlapping_hours_on_same_date_passes(self):
        """Periods on same date with non-overlapping hours (e.g. morning and afternoon) must pass."""
        post_data = {
            'periods-0-start_date': '2026-09-22',
            'periods-0-end_date': '2026-09-22',
            'periods-0-days': '0.50',
            'periods-0-start_time': '08:00',
            'periods-0-end_time': '12:00',
            'periods-1-start_date': '2026-09-22',
            'periods-1-end_date': '2026-09-22',
            'periods-1-days': '0.50',
            'periods-1-start_time': '13:00',
            'periods-1-end_time': '17:00',
        }
        cleaned, err = parse_and_validate_leave_periods(post_data, employee=self.employee)
        self.assertIsNone(err)
        self.assertIsNotNone(cleaned)
        self.assertEqual(len(cleaned), 2)
        self.assertEqual(cleaned[0]['start_time'], datetime.time(8, 0))
        self.assertEqual(cleaned[0]['end_time'], datetime.time(12, 0))
        self.assertEqual(cleaned[1]['start_time'], datetime.time(13, 0))
        self.assertEqual(cleaned[1]['end_time'], datetime.time(17, 0))

    def test_end_date_before_start_date_fails(self):
        """End date before start date must fail."""
        post_data = {
            'periods-0-start_date': '2026-09-25',
            'periods-0-end_date': '2026-09-22',
            'periods-0-days': '1.0',
        }
        cleaned, err = parse_and_validate_leave_periods(post_data, employee=self.employee)
        self.assertIsNone(cleaned)
        self.assertIn("cannot be before Start Date", err)

    def test_end_time_before_start_time_fails(self):
        """End time before start time on same date must fail."""
        post_data = {
            'periods-0-start_date': '2026-09-22',
            'periods-0-end_date': '2026-09-22',
            'periods-0-days': '0.5',
            'periods-0-start_time': '14:00',
            'periods-0-end_time': '10:00',
        }
        cleaned, err = parse_and_validate_leave_periods(post_data, employee=self.employee)
        self.assertIsNone(cleaned)
        self.assertIn("must be after Start Time", err)

    def test_collision_with_existing_approved_leave_fails(self):
        """Submitting a request on dates already covered by an approved leave must fail."""
        # Create existing approved leave for employee
        existing_leave = LeaveRequest.objects.create(
            employee=self.employee,
            leave_type=self.leave_type,
            reason="Medical",
            status=LeaveRequest.Status.APPROVED,
            total_days=Decimal('3.0')
        )
        LeavePeriod.objects.create(
            leave_request=existing_leave,
            start_date=datetime.date(2026, 9, 20),
            end_date=datetime.date(2026, 9, 22),
            days=Decimal('3.0')
        )

        # New request attempting to take leave on Sept 22
        post_data = {
            'periods-0-start_date': '2026-09-22',
            'periods-0-end_date': '2026-09-24',
            'periods-0-days': '3.0',
        }
        cleaned, err = parse_and_validate_leave_periods(post_data, employee=self.employee)
        self.assertIsNone(cleaned)
        self.assertIn("Leave conflict", err)
        self.assertIn("conflicts with existing Approved leave request", err)

    def test_edit_own_leave_does_not_self_collide(self):
        """Editing an existing leave should exclude itself from collision check."""
        leave = LeaveRequest.objects.create(
            employee=self.employee,
            leave_type=self.leave_type,
            reason="Vacation",
            status=LeaveRequest.Status.PENDING,
            total_days=Decimal('2.0')
        )
        LeavePeriod.objects.create(
            leave_request=leave,
            start_date=datetime.date(2026, 9, 22),
            end_date=datetime.date(2026, 9, 23),
            days=Decimal('2.0')
        )

        # Edit the same leave request
        post_data = {
            'periods-0-start_date': '2026-09-22',
            'periods-0-end_date': '2026-09-24',
            'periods-0-days': '3.0',
        }
        cleaned, err = parse_and_validate_leave_periods(post_data, employee=self.employee, exclude_leave_id=leave.id)
        self.assertIsNone(err)
        self.assertIsNotNone(cleaned)

    def test_create_view_blocks_duplicate_submission(self):
        """HTTP POST to leave:create with duplicate periods does not save to DB and shows error."""
        initial_count = LeaveRequest.objects.count()
        response = self.client.post(reverse('leave:create'), {
            'employee': self.employee.id,
            'leave_type': self.leave_type.id,
            'status': 'pending',
            'reason': 'Duplicate test',
            'periods-0-start_date': '2026-09-22',
            'periods-0-end_date': '2026-09-22',
            'periods-0-days': '1.0',
            'periods-1-start_date': '2026-09-22',
            'periods-1-end_date': '2026-09-22',
            'periods-1-days': '1.0',
        })
        self.assertEqual(LeaveRequest.objects.count(), initial_count)
        self.assertEqual(response.status_code, 200)

    def test_create_view_saves_hourly_leave_with_times(self):
        """HTTP POST with hourly times properly saves start_time and end_time in LeavePeriod."""
        response = self.client.post(reverse('leave:create'), {
            'employee': self.employee.id,
            'leave_type': self.leave_type.id,
            'status': 'pending',
            'reason': 'Dentist appointment',
            'periods-0-start_date': '2026-09-22',
            'periods-0-end_date': '2026-09-22',
            'periods-0-days': '0.25',
            'periods-0-start_time': '09:00',
            'periods-0-end_time': '11:00',
        })
        self.assertRedirects(response, reverse('leave:my_leaves'))
        leave = LeaveRequest.objects.filter(reason='Dentist appointment').first()
        self.assertIsNotNone(leave)
        self.assertEqual(leave.total_days, Decimal('0.25'))
        period = leave.periods.first()
        self.assertIsNotNone(period)
        self.assertEqual(period.start_time, datetime.time(9, 0))
        self.assertEqual(period.end_time, datetime.time(11, 0))
        self.assertEqual(period.days, Decimal('0.25'))
