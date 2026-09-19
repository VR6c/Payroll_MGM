import factory
from datetime import date, timedelta
from decimal import Decimal
from django.utils import timezone
from accounts.models import User
from companies.models import Company
from employees.models import Employee
from payroll.models import SalaryStructure

class CompanyFactory(factory.django.DjangoModelFactory):
    class Meta: model = Company
    name = factory.Sequence(lambda n: f'Company {n}')
    timezone = 'UTC'
    status = True

class UserFactory(factory.django.DjangoModelFactory):
    class Meta: model = User
    username = factory.Sequence(lambda n: f'user{n}')
    email = factory.LazyAttribute(lambda o: f'{o.username}@test.com')
    role = 'employee'
    password = 'pbkdf2_sha256$1000$static_salt$pbkdf2_hash_value'

class EmployeeFactory(factory.django.DjangoModelFactory):
    class Meta: model = Employee
    user = factory.SubFactory(UserFactory)
    company = factory.SubFactory(CompanyFactory)
    employee_code = factory.Sequence(lambda n: f'EMP{n:04d}')
    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')
    email = factory.LazyAttribute(lambda o: f'{o.first_name.lower()}.{o.last_name.lower()}@test.com')
    join_date = factory.LazyFunction(lambda: date(2020, 1, 1))
    basic_salary = Decimal('5000.00')
    status = 'active'

class SalaryStructureFactory(factory.django.DjangoModelFactory):
    class Meta: model = SalaryStructure
    employee = factory.SubFactory(EmployeeFactory)
    basic_salary = Decimal('5000.00')
    transportation = Decimal('500.00')
    housing = Decimal('1000.00')
    effective_date = factory.LazyFunction(lambda: date(2020, 1, 1))
    status = True
