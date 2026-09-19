import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
from companies.models import Company, Department, Position
from employees.models import Employee
from attendance.models import EmployeeSchedule


class Command(BaseCommand):
    help = 'Seeds departments, positions, sample employees and workday shift schedules matching reference dashboard.'

    def handle(self, *args, **options):
        company, _ = Company.objects.get_or_create(
            name='Payroll MGM Inc',
            defaults={
                'email': 'contact@payrollmgm.com',
                'phone': '+1234567890',
                'address': 'Phnom Penh, Cambodia',
                'status': True,
            }
        )

        # Create Departments
        dept_marketing, _ = Department.objects.get_or_create(company=company, name='Marketing')
        dept_sales, _ = Department.objects.get_or_create(company=company, name='Sales')
        dept_finance, _ = Department.objects.get_or_create(company=company, name='Finance')
        dept_hr, _ = Department.objects.get_or_create(company=company, name='HR')
        dept_service, _ = Department.objects.get_or_create(company=company, name='Service')
        dept_mgmt, _ = Department.objects.get_or_create(company=company, name='Management')
        dept_tech, _ = Department.objects.get_or_create(company=company, name='Technology')

        # Create Positions
        pos_mkt_off, _ = Position.objects.get_or_create(company=company, department=dept_marketing, name='Marketing Officer')
        pos_sales_exec, _ = Position.objects.get_or_create(company=company, department=dept_sales, name='Sales Executive')
        pos_fin, _ = Position.objects.get_or_create(company=company, department=dept_finance, name='Fin')
        pos_sec_off, _ = Position.objects.get_or_create(company=company, department=dept_hr, name='Security Officer')
        pos_cleaner, _ = Position.objects.get_or_create(company=company, department=dept_hr, name='Cleaner')
        pos_util, _ = Position.objects.get_or_create(company=company, department=dept_service, name='Util I (RWT)')
        pos_ceo, _ = Position.objects.get_or_create(company=company, department=dept_mgmt, name='CEO')
        pos_uiux, _ = Position.objects.get_or_create(company=company, department=dept_tech, name='UI/UX')

        sample_employees = [
            {
                'employee_code': 'EMP-001',
                'first_name': 'Multiple',
                'last_name': 'Overtime',
                'gender': 'M',
                'email': 'overtime@payrollmgm.com',
                'department': dept_marketing,
                'position': pos_mkt_off,
            },
            {
                'employee_code': 'EMP-002',
                'first_name': 'FuFu',
                'last_name': '',
                'gender': 'M',
                'email': 'fufu@payrollmgm.com',
                'department': dept_sales,
                'position': pos_sales_exec,
            },
            {
                'employee_code': 'EMP-003',
                'first_name': 'A plus',
                'last_name': 'nail',
                'gender': 'M',
                'email': 'aplusnail@payrollmgm.com',
                'department': dept_sales,
                'position': pos_sales_exec,
            },
            {
                'employee_code': 'EMP-004',
                'first_name': 'mee',
                'last_name': '',
                'gender': 'M',
                'email': 'mee@payrollmgm.com',
                'department': dept_finance,
                'position': pos_fin,
            },
            {
                'employee_code': 'EMP-005',
                'first_name': 'Thary',
                'last_name': 'Vireak1',
                'gender': 'M',
                'email': 'thary.vireak1@payrollmgm.com',
                'department': dept_hr,
                'position': pos_sec_off,
            },
            {
                'employee_code': 'EMP-006',
                'first_name': 'Van',
                'last_name': 'nuthhhhhhhh',
                'gender': 'F',
                'email': 'vannuth@payrollmgm.com',
                'department': dept_hr,
                'position': pos_cleaner,
            },
            {
                'employee_code': 'EMP-007',
                'first_name': 'Kim',
                'last_name': 'Sreyoun',
                'gender': 'M',
                'email': 'kimsreyoun@payrollmgm.com',
                'department': dept_service,
                'position': pos_util,
            },
            {
                'employee_code': 'EMP-008',
                'first_name': 'Ratha',
                'last_name': '',
                'gender': 'M',
                'email': 'ratha@payrollmgm.com',
                'department': dept_mgmt,
                'position': pos_ceo,
            },
            {
                'employee_code': 'EMP-009',
                'first_name': 'មរតកអភិវឌ្ឍន៍',
                'last_name': '...',
                'gender': 'M',
                'email': 'morotok@payrollmgm.com',
                'department': dept_tech,
                'position': pos_uiux,
            },
            {
                'employee_code': 'EMP-010',
                'first_name': 'January',
                'last_name': '',
                'gender': 'F',
                'email': 'january@payrollmgm.com',
                'department': dept_hr,
                'position': pos_cleaner,
            },
        ]

        today = timezone.now().date()
        start_time_val = datetime.time(8, 0, 0)
        end_time_val = datetime.time(17, 0, 0)

        for emp_data in sample_employees:
            emp, created = Employee.objects.get_or_create(
                employee_code=emp_data['employee_code'],
                defaults={
                    'company': company,
                    'first_name': emp_data['first_name'],
                    'last_name': emp_data['last_name'],
                    'gender': emp_data['gender'],
                    'email': emp_data['email'],
                    'department': emp_data['department'],
                    'position': emp_data['position'],
                    'join_date': today,
                    'basic_salary': 800.00,
                    'status': Employee.Status.ACTIVE,
                }
            )

            # Ensure employee dept, position updated
            emp.department = emp_data['department']
            emp.position = emp_data['position']
            emp.save()

            # Create default Mon-Fri shift (08:00 AM - 05:00 PM, No Work Time 2) & Sat-Sun Off
            for day in range(7):
                is_work = (day < 5)
                EmployeeSchedule.objects.update_or_create(
                    employee=emp,
                    day_of_week=day,
                    defaults={
                        'schedule_type': EmployeeSchedule.ScheduleType.FLEXIBLE,
                        'start_time': start_time_val if is_work else None,
                        'end_time': end_time_val if is_work else None,
                        'is_half_day': False,
                        'is_work_day': is_work,
                        'shift_label': 'No Work Time 2',
                    }
                )

        self.stdout.write(self.style.SUCCESS("Successfully seeded sample employees and shift schedules!"))
