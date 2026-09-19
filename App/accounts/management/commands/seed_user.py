from django.core.management.base import BaseCommand
from django.utils import timezone
from accounts.models import User
from companies.models import Company, Department, Position
from employees.models import Employee


class Command(BaseCommand):
    help = 'Seeds a super admin user (default username: reak, password: 123456) with company and employee profile'

    def add_arguments(self, parser):
        parser.add_argument('--username', type=str, default='reak', help='Username for the user')
        parser.add_argument('--password', type=str, default='123456', help='Password for the user')
        parser.add_argument('--email', type=str, default='reak@example.com', help='Email for the user')
        parser.add_argument('--role', type=str, default=User.Role.SUPER_ADMIN, help='Role for the user')

    def handle(self, *args, **options):
        username = options['username']
        password = options['password']
        email = options['email']
        role = options['role']

        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                'email': email,
                'first_name': 'Reak',
                'last_name': 'Admin',
                'role': role,
                'is_staff': True,
                'is_superuser': True,
            }
        )

        user.set_password(password)
        user.email = email
        user.role = role
        user.is_staff = True
        user.is_superuser = True
        user.save()

        if created:
            self.stdout.write(self.style.SUCCESS(f"User '{username}' created successfully."))
        else:
            self.stdout.write(self.style.SUCCESS(f"User '{username}' password and superadmin settings updated successfully."))

        # Ensure default company, department, and position exist
        company, _ = Company.objects.get_or_create(
            name='Payroll MGM Inc',
            defaults={
                'email': 'contact@payrollmgm.com',
                'phone': '+1234567890',
                'address': 'Phnom Penh, Cambodia',
                'status': True,
            }
        )

        department, _ = Department.objects.get_or_create(
            company=company,
            name='Executive',
            defaults={'description': 'Executive Management'}
        )

        position, _ = Position.objects.get_or_create(
            company=company,
            department=department,
            name='System Administrator',
            defaults={'description': 'System Administrator'}
        )

        # Create or update Employee profile for the user
        employee, emp_created = Employee.objects.get_or_create(
            user=user,
            defaults={
                'company': company,
                'department': department,
                'position': position,
                'employee_code': f"EMP-{user.pk:04d}",
                'first_name': user.first_name or 'Reak',
                'last_name': user.last_name or 'Admin',
                'gender': 'M',
                'email': user.email,
                'join_date': timezone.now().date(),
                'basic_salary': 5000.00,
                'status': Employee.Status.ACTIVE,
            }
        )

        if emp_created:
            self.stdout.write(self.style.SUCCESS(f"Employee profile for '{username}' created successfully."))
        else:
            self.stdout.write(self.style.SUCCESS(f"Employee profile for '{username}' already exists."))

        self.stdout.write(
            self.style.SUCCESS(
                f"\nSuccessfully seeded user:\n"
                f"  Username: {username}\n"
                f"  Password: {password}\n"
                f"  Role: {role}\n"
                f"  Email: {email}\n"
            )
        )
