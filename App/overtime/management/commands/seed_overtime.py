import datetime
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from companies.models import Company
from companies.services import get_default_company
from employees.models import Employee
from accounts.models import User
from overtime.models import OvertimeType, OvertimeRequest


class Command(BaseCommand):
    help = "Seeds initial Overtime Types and realistic sample Overtime records"

    def handle(self, *args, **options):
        company = get_default_company()
        if not company:
            company = Company.objects.first()

        if not company:
            self.stdout.write(self.style.ERROR("No company found. Please run seed data first."))
            return

        admin_user = User.objects.filter(role=User.Role.SUPER_ADMIN).first()

        # 1. Seed Overtime Types
        types_data = [
            {
                'name': 'Normal Day Overtime (1.5x)',
                'rate_multiplier': Decimal('1.50'),
                'description': 'Overtime hours worked exceeding standard working hours on regular workdays.',
                'status': True,
            },
            {
                'name': 'Weekend Overtime (2.0x)',
                'rate_multiplier': Decimal('2.00'),
                'description': 'Work performed on official scheduled weekend rest days.',
                'status': True,
            },
            {
                'name': 'Holiday Overtime (3.0x)',
                'rate_multiplier': Decimal('3.00'),
                'description': 'Overtime during official national public holidays.',
                'status': True,
            },
            {
                'name': 'Night Shift Overtime (1.5x)',
                'rate_multiplier': Decimal('1.50'),
                'description': 'Work performed during nocturnal hours (10:00 PM - 06:00 AM).',
                'status': True,
            },
        ]

        created_types = []
        for td in types_data:
            obj, created = OvertimeType.objects.get_or_create(
                company=company,
                name=td['name'],
                defaults={
                    'rate_multiplier': td['rate_multiplier'],
                    'description': td['description'],
                    'status': td['status'],
                }
            )
            created_types.append(obj)
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created Overtime Type: {obj.name}"))

        # 2. Seed Sample Overtime Records for Active Employees
        employees = Employee.objects.filter(status='active')[:5]
        if not employees.exists():
            self.stdout.write(self.style.WARNING("No active employees found to seed overtime records."))
            return

        today = timezone.localdate()
        ot_samples = [
            (datetime.time(17, 0), datetime.time(20, 0), Decimal('3.00'), 'Project release deployment and testing', OvertimeRequest.Status.APPROVED),
            (datetime.time(17, 30), datetime.time(19, 30), Decimal('2.00'), 'Month-end financial closing support', OvertimeRequest.Status.APPROVED),
            (datetime.time(9, 0), datetime.time(13, 0), Decimal('4.00'), 'Weekend emergency server maintenance', OvertimeRequest.Status.APPROVED),
            (datetime.time(18, 0), datetime.time(21, 0), Decimal('3.00'), 'Urgent client issue escalation', OvertimeRequest.Status.PENDING),
            (datetime.time(17, 0), datetime.time(19, 0), Decimal('2.00'), 'Extra inventory audit shift', OvertimeRequest.Status.REJECTED),
        ]

        seeded_records = 0
        for i, emp in enumerate(employees):
            sample = ot_samples[i % len(ot_samples)]
            ot_type = created_types[i % len(created_types)]
            ot_date = today - datetime.timedelta(days=(i * 2 + 1))

            if not OvertimeRequest.objects.filter(employee=emp, date=ot_date).exists():
                req = OvertimeRequest(
                    employee=emp,
                    overtime_type=ot_type,
                    date=ot_date,
                    start_time=sample[0],
                    end_time=sample[1],
                    hours=sample[2],
                    rate_multiplier=ot_type.rate_multiplier,
                    reason=sample[3],
                    status=sample[4],
                )
                if sample[4] == OvertimeRequest.Status.APPROVED and admin_user:
                    req.approved_by = admin_user
                    req.approved_at = timezone.now()
                elif sample[4] == OvertimeRequest.Status.REJECTED:
                    req.rejection_reason = "Overtime was not pre-approved by department manager."

                req.save()
                seeded_records += 1

        self.stdout.write(self.style.SUCCESS(f"Seeded {seeded_records} overtime records successfully."))
